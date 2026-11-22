"""G1: two OpenAlex records that share a DOI are one library paper."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Chunk, Paper
from src.db.repository import PostgresRepository

pytestmark = pytest.mark.integration

REQUEST = {
    "research_question": "How do teenagers use social media?",
    "min_year": 2020,
    "inclusion_criteria": ["Studies adolescents"],
    "exclusion_criteria": [],
    "target_output_count": 5,
}


def test_the_fixture_pair_with_one_doi_merges_into_one_paper_with_one_chunk_set(
    repository: PostgresRepository, sessions: sessionmaker[Session], fake_surface
):
    from src.api.main import app

    with TestClient(app) as client:
        job_id = client.post("/start_pipeline", json=REQUEST).json()["job_id"]
        status = client.get(f"/status/{job_id}").json()

    included = status["screening_results"]["included_papers"]
    assert [paper["paper"]["openalex_id"] for paper in included] == [
        "W9000000001",
        "W9000000005",
    ]
    with sessions() as session:
        papers = session.scalars(select(Paper)).all()
        chunk_keys = session.execute(select(Chunk.paper_id, Chunk.ordinal)).all()
    assert [(p.openalex_id, p.doi, p.ingestion_status) for p in papers] == [
        ("W9000000001", "10.1000/fixture.shared.1", "chunked")
    ]
    assert len(chunk_keys) == len(set(chunk_keys))
    assert {paper_id for paper_id, _ in chunk_keys} == {papers[0].id}
    assert included[0]["retrieved_chunks_by_field"] == included[1]["retrieved_chunks_by_field"]
