"""Library behaviour of the repository on Postgres: run payloads, paper upsert, chunks."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Chunk, Paper
from src.db.repository import NewChunk, PostgresRepository

pytestmark = pytest.mark.integration

DIMENSIONS = 384


def _unit_vector(position: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[position] = 1.0
    return vector


def _paper(repository: PostgresRepository, **overrides) -> int:
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


def test_update_run_step_merges_payload_fields_into_the_result(repository: PostgresRepository):
    run_id = repository.create_run("Q", {}, {"profile": "test"})
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


def test_get_run_returns_none_for_an_unknown_id(repository: PostgresRepository):
    assert repository.get_run(uuid.uuid4()) is None


def test_upsert_stores_one_paper_for_a_repeated_openalex_id(repository: PostgresRepository):
    first = _paper(repository)
    second = _paper(repository)

    assert first == second


def test_upsert_merges_two_openalex_records_sharing_a_doi(
    repository: PostgresRepository, sessions: sessionmaker[Session]
):
    first = _paper(repository, openalex_id="W1", doi="10.1000/abc")
    second = _paper(repository, openalex_id="W2", doi="https://doi.org/10.1000/ABC")

    with sessions() as session:
        papers = session.scalars(select(Paper)).all()
    assert first == second
    assert [(paper.openalex_id, paper.doi) for paper in papers] == [("W1", "10.1000/abc")]


def test_upsert_fills_in_a_doi_that_appears_later(repository: PostgresRepository):
    paper_id = _paper(repository, doi=None)

    again = _paper(repository, doi="https://dx.doi.org/10.1000/ABC", venue="Nature")

    assert again == paper_id
    with_doi = _paper(repository, openalex_id="W9", doi="10.1000/abc")
    assert with_doi == paper_id


def test_replace_chunks_leaves_one_chunk_set_and_marks_the_paper_chunked(
    repository: PostgresRepository, sessions: sessionmaker[Session]
):
    paper_id = _paper(repository)
    old = [NewChunk(1, 0, "old", _unit_vector(0)), NewChunk(1, 1, "older", _unit_vector(1))]
    new = [NewChunk(1, 0, "page one", _unit_vector(2)), NewChunk(2, 1, "page two", _unit_vector(3))]

    repository.replace_chunks(paper_id, old, "model-a", "v1")
    repository.replace_chunks(paper_id, new, "model-b", "v1")

    with sessions() as session:
        chunks = session.scalars(select(Chunk).order_by(Chunk.ordinal)).all()
        paper = session.get(Paper, paper_id)
    assert [(c.page, c.ordinal, c.text, c.embedding_model) for c in chunks] == [
        (1, 0, "page one", "model-b"),
        (2, 1, "page two", "model-b"),
    ]
    assert paper.ingestion_status == "chunked"


def test_failed_chunk_replacement_keeps_the_previous_chunks(
    repository: PostgresRepository, sessions: sessionmaker[Session]
):
    paper_id = _paper(repository)
    repository.replace_chunks(paper_id, [NewChunk(1, 0, "kept", _unit_vector(0))], "m", "v1")
    duplicate_ordinals = [
        NewChunk(1, 0, "a", _unit_vector(1)),
        NewChunk(1, 0, "b", _unit_vector(2)),
    ]

    with pytest.raises(IntegrityError):
        repository.replace_chunks(paper_id, duplicate_ordinals, "m", "v1")

    with sessions() as session:
        texts = session.scalars(select(Chunk.text)).all()
    assert texts == ["kept"]


def test_search_chunks_returns_the_closest_chunks_of_that_paper_only(
    repository: PostgresRepository,
):
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
