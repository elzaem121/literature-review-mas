from unittest.mock import Mock

import pytest
import requests
from streamlit.testing.v1 import AppTest

JOB_ID = "11111111-1111-1111-1111-111111111111"


def _response(status_code: int, body: dict | None = None) -> Mock:
    response = Mock(status_code=status_code)
    response.json.return_value = body or {}
    return response


def _run_ui(monkeypatch: pytest.MonkeyPatch, status_responses: list[Mock]) -> AppTest:
    """Submit the form against a stubbed backend that answers polls from `status_responses`."""
    monkeypatch.setattr(requests, "post", Mock(return_value=_response(200, {"job_id": JOB_ID})))
    polls = Mock(side_effect=status_responses)
    monkeypatch.setattr(requests, "get", polls)
    app = AppTest.from_file("src/ui/app.py", default_timeout=10)
    app.run()
    app.sidebar.text_area[0].input("How do teenagers use social media?")
    app.sidebar.button[0].click()
    app.run()
    assert polls.call_count == len(status_responses), "polling did not stop at the terminal state"
    return app


def test_polling_stops_on_404_with_a_start_new_run_message(monkeypatch: pytest.MonkeyPatch):
    app = _run_ui(monkeypatch, [_response(404)])

    assert "start a new run" in app.error[0].value


def test_polling_stops_on_interrupted_and_shows_the_message(monkeypatch: pytest.MonkeyPatch):
    interrupted = {"current_step": "interrupted", "status_message": "Interrupted. Start a new run."}

    app = _run_ui(monkeypatch, [_response(200, interrupted)])

    assert app.warning[0].value == "Interrupted. Start a new run."


def test_polling_continues_while_running_then_stops_on_error(monkeypatch: pytest.MonkeyPatch):
    running = {"current_step": "search", "status_message": "Searching"}
    failed = {"current_step": "error", "status_message": "Pipeline failed: boom"}

    app = _run_ui(monkeypatch, [_response(200, running), _response(200, failed)])

    assert app.error[0].value == "Pipeline failed: boom"
