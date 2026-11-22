"""The in-memory repository keeps the behaviour of `PostgresRepository` that the unit tests use."""

import uuid

import pytest

from src.db.memory_repository import InMemoryRepository
from src.db.records import NewChunk

DIMENSIONS = 384


def _unit_vector(position: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[position] = 1.0
    return vector


def _paper(repository: InMemoryRepository, **overrides) -> int:
    fields = {
        "openalex_id": "W1",
        "doi": "https://doi.org/10.1000/ABC",
        "title": "A paper",
        "year": 2022,
        "authors": ["Ada Lovelace"],
        "venue": None,
        "pdf_url": None,
    } | overrides
    return repository.upsert_paper(**fields)


def test_run_lifecycle_merges_payloads_and_marks_unfinished_runs_interrupted():
    repository = InMemoryRepository()
    run_id = repository.create_run("Q", {"min_year": 2020}, {"profile": "test"})
    other_id = repository.create_run("Q2", {}, {})
    assert repository.get_run(run_id).status == "pending"

    repository.start_run(run_id)
    repository.update_run_step(run_id, "search", "Searching", {"raw_papers_count": 5})
    repository.update_run_step(run_id, "screening", "Screening", {"screening_results": {"a": 1}})
    run = repository.get_run(run_id)
    assert run.status == "running"
    assert (run.current_step, run.status_message) == ("screening", "Screening")
    assert run.result == {
        "provenance": {"profile": "test"},
        "raw_papers_count": 5,
        "screening_results": {"a": 1},
    }

    repository.mark_unfinished_interrupted()
    repository.finish_run(other_id, "completed", "done")
    assert repository.get_run(run_id).status == "interrupted"
    assert repository.get_run(other_id).status == "completed"
    assert repository.get_run(other_id).finished_at is not None
    assert repository.get_run(uuid.uuid4()) is None


def test_payloads_that_jsonb_would_reject_fail_here_too():
    repository = InMemoryRepository()
    run_id = repository.create_run("Q", {}, {})

    with pytest.raises(TypeError):
        repository.update_run_step(run_id, "search", "x", {"bad": object()})


def test_upsert_merges_by_openalex_id_or_doi_and_the_first_openalex_id_wins():
    repository = InMemoryRepository()

    first = _paper(repository, openalex_id="W1", doi="10.1000/abc")
    same_id = _paper(repository, openalex_id="W1")
    same_doi = _paper(repository, openalex_id="W2", doi="https://doi.org/10.1000/ABC")
    other = _paper(repository, openalex_id="W3", doi=None)

    assert first == same_id == same_doi
    assert other != first
    assert repository.get_paper(first).openalex_id == "W1"
    assert repository.get_paper(first).doi == "10.1000/abc"


def test_upsert_fills_in_a_doi_and_other_fields_that_appear_later():
    repository = InMemoryRepository()
    paper_id = _paper(repository, doi=None, year=None)

    _paper(repository, doi="https://dx.doi.org/10.1000/ABC", year=2021, venue="Nature")

    paper = repository.get_paper(paper_id)
    assert (paper.doi, paper.year, paper.venue) == ("10.1000/abc", 2021, "Nature")


def test_replace_chunks_replaces_the_set_and_marks_the_paper_chunked():
    repository = InMemoryRepository()
    paper_id = _paper(repository)
    old = [NewChunk(1, 0, "old", _unit_vector(0)), NewChunk(1, 1, "older", _unit_vector(1))]
    new = [NewChunk(1, 0, "page one", _unit_vector(2))]

    repository.replace_chunks(paper_id, old, "model-a", "v1")
    repository.replace_chunks(paper_id, new, "model-b", "v1")

    assert repository.get_paper(paper_id).ingestion_status == "chunked"
    assert repository.search_chunks(paper_id, _unit_vector(2), 10) == ["page one"]


def test_is_chunked_needs_the_status_the_embedding_model_and_the_chunker_version():
    repository = InMemoryRepository()
    paper_id = _paper(repository)
    assert not repository.is_chunked(paper_id, "m", "v1")

    repository.replace_chunks(paper_id, [NewChunk(1, 0, "t", _unit_vector(0))], "m", "v1")
    assert repository.is_chunked(paper_id, "m", "v1")
    assert not repository.is_chunked(paper_id, "other", "v1")
    assert not repository.is_chunked(paper_id, "m", "v2")

    repository.set_paper_status(paper_id, "failed", "boom")
    assert not repository.is_chunked(paper_id, "m", "v1")


def test_set_paper_status_stores_the_error_and_rejects_unknown_statuses():
    repository = InMemoryRepository()
    paper_id = _paper(repository)

    repository.set_paper_status(paper_id, "failed", "boom")
    assert repository.get_paper(paper_id).last_error == "boom"
    repository.set_paper_status(paper_id, "downloaded")
    assert repository.get_paper(paper_id).last_error is None
    with pytest.raises(ValueError, match="Unknown ingestion status 'broken'"):
        repository.set_paper_status(paper_id, "broken")


def test_search_chunks_returns_the_closest_chunks_of_that_paper_only():
    repository = InMemoryRepository()
    paper_id = _paper(repository)
    other_id = _paper(repository, openalex_id="W2", doi=None)
    repository.replace_chunks(
        paper_id,
        [
            NewChunk(1, 0, "far", _unit_vector(0)),
            NewChunk(1, 1, "near", _unit_vector(5)),
            NewChunk(2, 2, "middle", [0.5 if i in (5, 0) else 0.0 for i in range(DIMENSIONS)]),
        ],
        "m",
        "v1",
    )
    repository.replace_chunks(other_id, [NewChunk(1, 0, "other", _unit_vector(5))], "m", "v1")

    assert repository.search_chunks(paper_id, _unit_vector(5), 2) == ["near", "middle"]
    assert repository.search_chunks(paper_id, _unit_vector(5), 10) == ["near", "middle", "far"]
    assert repository.search_chunks(999, _unit_vector(5), 5) == []
