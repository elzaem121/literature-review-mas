"""G1: running the same review twice leaves one set of library rows, built once."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Chunk, Paper
from src.db.repository import PostgresRepository

pytestmark = pytest.mark.integration

REQUEST = {
    "research_question": "How do teenagers use social media?",
    "min_year": 2020,
    "inclusion_criteria": ["Studies adolescents"],
    "exclusion_criteria": ["Marketing studies"],
    "additional_info": None,
    "target_output_count": 5,
}


@pytest.fixture
def downloads(fake_surface, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every PDF download the pipeline makes, on top of the fake surface."""
    from src.pipeline.ingestion import node as ingestion_node

    calls: list[str] = []
    download = ingestion_node.download_pdf

    def recording_download(url, path):
        calls.append(url)
        return download(url, path)

    monkeypatch.setattr(ingestion_node, "download_pdf", recording_download)
    return calls


def _run_review(client: TestClient) -> dict:
    job_id = client.post("/start_pipeline", json=REQUEST).json()["job_id"]
    return client.get(f"/status/{job_id}").json()


def _library(sessions: sessionmaker[Session]) -> tuple[list[int], list[tuple[int, int, str]]]:
    with sessions() as session:
        paper_ids = list(session.scalars(select(Paper.id).order_by(Paper.id)))
        chunks = [
            (row.id, row.paper_id, row.text)
            for row in session.execute(select(Chunk.id, Chunk.paper_id, Chunk.text))
        ]
    return paper_ids, sorted(chunks)


def test_the_same_review_twice_keeps_one_paper_and_one_chunk_set(
    repository: PostgresRepository, sessions: sessionmaker[Session], downloads: list[str]
):
    from src.api.main import app

    with TestClient(app) as client:
        first = _run_review(client)
        library_after_first = _library(sessions)
        downloads_after_first = len(downloads)
        second = _run_review(client)

    paper_ids, chunks = library_after_first
    assert first["current_step"] == second["current_step"] == "completed"
    assert len(paper_ids) == 1
    assert chunks, "the first run stored no chunks"
    assert _library(sessions) == library_after_first  # same rows, same chunk ids: nothing rebuilt
    assert len(downloads) == downloads_after_first
    assert first["screening_results"] == second["screening_results"]
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Chunk)) == len(chunks)
