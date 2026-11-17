"""G2: finished runs survive a restart; unfinished runs become `interrupted` (design 2a.7)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Review, Run, User
from src.db.repository import PostgresRepository, get_repository
from src.pipeline.search.api_client import OpenAlexClient

pytestmark = pytest.mark.integration

REQUEST = {
    "research_question": "How do teenagers use social media?",
    "min_year": 2020,
    "inclusion_criteria": ["Studies adolescents"],
    "exclusion_criteria": ["Marketing studies"],
    "additional_info": None,
    "target_output_count": 5,
}


def _start_and_finish_run(client: TestClient) -> str:
    """Start a run; the TestClient returns only after the background task has finished."""
    response = client.post("/start_pipeline", json=REQUEST)
    assert response.status_code == 200
    return response.json()["job_id"]


def _new_unfinished_run(repository: PostgresRepository, *, started: bool) -> str:
    run_id = repository.create_run("Unfinished question", {}, {})
    if started:
        repository.start_run(run_id)
    return str(run_id)


@pytest.fixture
def api_app(repository: PostgresRepository, fake_surface):
    from src.api.main import app

    return app


def test_completed_run_survives_a_restart_and_unfinished_runs_are_interrupted(
    api_app, repository: PostgresRepository
):
    with TestClient(api_app) as first_instance:
        job_id = _start_and_finish_run(first_instance)
        before_restart = first_instance.get(f"/status/{job_id}").json()
    assert before_restart["current_step"] == "completed"
    assert len(before_restart["extracted_papers"]) == 2
    running_id = _new_unfinished_run(repository, started=True)
    pending_id = _new_unfinished_run(repository, started=False)

    get_repository.cache_clear()  # a new process builds its own repository on the same database
    with TestClient(api_app) as second_instance:
        after_restart = second_instance.get(f"/status/{job_id}").json()
        interrupted = [
            second_instance.get(f"/status/{id_}").json() for id_ in (running_id, pending_id)
        ]
        unknown = second_instance.get(f"/status/{uuid.uuid4()}")
        malformed = second_instance.get("/status/not-a-job-id")

    assert after_restart == before_restart
    for response in interrupted:
        assert response["current_step"] == "interrupted"
        assert "start a new run" in response["status_message"]
    assert unknown.status_code == 404
    assert malformed.status_code == 404


def test_start_pipeline_stores_review_run_and_provenance(
    api_app, repository: PostgresRepository, sessions: sessionmaker[Session]
):
    with TestClient(api_app) as client:
        job_id = _start_and_finish_run(client)

    with sessions() as session:
        run = session.get(Run, uuid.UUID(job_id))
        review = session.get(Review, run.review_id)
        local_user = session.scalar(select(User).where(User.email == "local@localhost"))
        assert run.status == "completed"
        assert run.finished_at is not None
        assert run.user_id == review.user_id == local_user.id
        assert review.question == REQUEST["research_question"]
        assert review.criteria == {
            "inclusion": ["Studies adolescents"],
            "exclusion": ["Marketing studies"],
            "min_year": 2020,
            "target_output_count": 5,
            "additional_info": None,
        }
        assert run.result["provenance"]["profile"] == "test"
        assert run.result["provenance"]["models"]["screening"] == "qwen2.5-coder:7b"
        assert run.result["provenance"]["prompt_versions"]["extraction"] == "v1"
        assert run.result["raw_papers_count"] == 5


def test_failed_run_reports_error_with_the_failure_message(
    api_app, monkeypatch: pytest.MonkeyPatch
):
    def failing_retrieval(*_args, **_kwargs):
        raise RuntimeError("OpenAlex is down")

    monkeypatch.setattr(OpenAlexClient, "execute_retrieval", failing_retrieval)

    with TestClient(api_app) as client:
        job_id = _start_and_finish_run(client)
        response = client.get(f"/status/{job_id}").json()

    assert response["current_step"] == "error"
    assert response["status_message"].startswith("Pipeline failed:")
    assert "OpenAlex is down" in response["status_message"]
