import pytest

from src.db.models import Run
from src.db.repository import normalize_doi
from src.llm.prompts import extraction, screening, search


@pytest.fixture
def api():
    """The API module; imported after the test profile is set, since import reads the settings."""
    from src.api import main

    return main


def _run(status: str, **result) -> Run:
    return Run(
        status=status,
        current_step="screening",
        status_message="Screening papers",
        result={"provenance": {}, **result},
    )


@pytest.mark.parametrize("status", ["pending", "running"])
def test_unfinished_runs_report_their_stored_step_and_partial_payload(api, status: str):
    run = _run(status, raw_papers_count=5)

    response = api.compose_status(run)

    assert (response.current_step, response.status_message) == ("screening", "Screening papers")
    assert response.raw_papers_count == 5
    assert response.screening_results is None


def test_completed_run_returns_the_full_payload(api):
    run = _run(
        "completed",
        raw_papers_count=5,
        screening_results={"included_papers": [{"paper": {"title": "A"}}]},
        extracted_papers=[{"paper": {"title": "A"}}],
    )

    response = api.compose_status(run)

    assert response.current_step == "completed"
    assert len(response.screening_results.included_papers) == 1
    assert response.extracted_papers == [{"paper": {"title": "A"}}]


def test_failed_run_reports_error_with_the_stored_message(api):
    run = _run("failed")
    run.status_message = "Pipeline failed: boom"

    response = api.compose_status(run)

    assert (response.current_step, response.status_message) == ("error", "Pipeline failed: boom")


def test_interrupted_run_tells_the_user_to_start_a_new_run(api):
    response = api.compose_status(_run("interrupted"))

    assert response.current_step == "interrupted"
    assert response.status_message == api.INTERRUPTED_MESSAGE
    assert "start a new run" in api.INTERRUPTED_MESSAGE


def test_payload_holds_only_the_fields_a_step_produced(api):
    state = {"raw_papers": [{}, {}], "current_step": "search", "status_message": "x"}

    assert api.build_payload(state) == {"raw_papers_count": 2}
    assert api.build_payload({"extracted_papers": []}) == {"extracted_papers": []}


def test_provenance_records_models_prompt_versions_and_profile(api):
    provenance = api.build_provenance()

    assert provenance == {
        "models": {
            "search": "qwen2.5-coder:7b",
            "screening": "qwen2.5-coder:7b",
            "extraction": "qwen2.5-coder:7b",
        },
        "prompt_versions": {
            "search": search.PROMPT_VERSION,
            "screening": screening.PROMPT_VERSION,
            "extraction": extraction.PROMPT_VERSION,
        },
        "profile": "test",
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://doi.org/10.1000/ABC", "10.1000/abc"),
        ("http://doi.org/10.1000/abc", "10.1000/abc"),
        ("https://dx.doi.org/10.1000/abc", "10.1000/abc"),
        ("http://dx.doi.org/10.1000/ABC", "10.1000/abc"),
        ("10.1000/ABC", "10.1000/abc"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_doi(raw: str | None, expected: str | None):
    assert normalize_doi(raw) == expected
