from typing import Any

import pytest
import requests

from eval.harness import ollama_check
from eval.harness.ollama_check import (
    OllamaCheckError,
    check_models,
    is_infrastructure_error,
    native_root,
    precheck_models,
)

BASE_URL = "http://localhost:11434/v1"
TAGS = {
    "models": [
        {"name": "qwen2.5-coder:7b", "digest": "aaa111"},
        {"name": "llama3:latest", "digest": "bbb222"},
    ]
}


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._payload


@pytest.fixture
def requested(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve `TAGS` for every request and record the requested URLs."""
    urls: list[str] = []

    def fake_get(url: str, timeout: float) -> FakeResponse:
        urls.append(url)
        return FakeResponse(TAGS)

    monkeypatch.setattr(ollama_check.requests, "get", fake_get)
    return urls


def test_the_native_root_is_the_base_url_without_its_v1_suffix():
    assert native_root("http://localhost:11434/v1") == "http://localhost:11434"
    assert native_root("http://localhost:11434/v1/") == "http://localhost:11434"
    assert native_root("http://cluster:8080") == "http://cluster:8080"


def test_the_digest_of_every_model_comes_from_the_native_tags_endpoint(requested: list[str]):
    digests = check_models(["qwen2.5-coder:7b", "llama3"], BASE_URL)

    assert digests == {"qwen2.5-coder:7b": "aaa111", "llama3": "bbb222"}
    assert requested == ["http://localhost:11434/api/tags"]


def test_a_model_that_is_not_pulled_is_named_with_the_command_to_pull_it(requested: list[str]):
    with pytest.raises(OllamaCheckError) as error:
        check_models(["qwen2.5-coder:7b", "mistral:7b"], BASE_URL)

    assert str(error.value) == "Ollama model 'mistral:7b' is not pulled (ollama pull mistral:7b)"


@pytest.mark.parametrize(
    "failure",
    [requests.ConnectionError("refused"), requests.Timeout("slow")],
)
def test_an_unreachable_server_is_reported_with_its_url(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
):
    def fake_get(url: str, timeout: float) -> FakeResponse:
        raise failure

    monkeypatch.setattr(ollama_check.requests, "get", fake_get)

    with pytest.raises(OllamaCheckError) as error:
        check_models(["qwen2.5-coder:7b"], BASE_URL)

    assert str(error.value) == "Ollama is not reachable at http://localhost:11434"


def test_an_error_status_counts_as_unreachable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        ollama_check.requests, "get", lambda url, timeout: FakeResponse({}, status_code=502)
    )

    with pytest.raises(OllamaCheckError, match="not reachable"):
        check_models(["qwen2.5-coder:7b"], BASE_URL)


@pytest.fixture
def posted(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Answer every generate request with a token and record what was posted."""
    requests_made: list[dict[str, Any]] = []

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> FakeResponse:
        requests_made.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"response": "Hi"})

    monkeypatch.setattr(ollama_check.requests, "post", fake_post)
    return requests_made


def test_the_precheck_sends_each_model_a_one_token_request_and_returns_the_digests(
    requested: list[str], posted: list[dict[str, Any]]
):
    digests = precheck_models(["qwen2.5-coder:7b", "llama3"], BASE_URL)

    assert digests == {"qwen2.5-coder:7b": "aaa111", "llama3": "bbb222"}
    assert [request["url"] for request in posted] == ["http://localhost:11434/api/generate"] * 2
    assert [request["json"]["model"] for request in posted] == ["qwen2.5-coder:7b", "llama3"]
    for request in posted:
        assert request["json"]["stream"] is False
        assert request["json"]["options"] == {"num_predict": 1}
        assert request["timeout"] == ollama_check.LOAD_TIMEOUT_S


def test_the_precheck_stops_at_a_model_that_is_not_pulled_before_generating_anything(
    requested: list[str], posted: list[dict[str, Any]]
):
    with pytest.raises(OllamaCheckError, match="'mistral:7b' is not pulled"):
        precheck_models(["qwen2.5-coder:7b", "mistral:7b"], BASE_URL)

    assert posted == []


def test_a_model_that_cannot_load_is_named_with_ollamas_own_message(
    requested: list[str], monkeypatch: pytest.MonkeyPatch
):
    def fake_post(url: str, json: dict[str, Any], timeout: float) -> FakeResponse:
        if json["model"] == "llama3":
            return FakeResponse({"error": "model requires more system memory"}, status_code=500)
        return FakeResponse({"response": "Hi"})

    monkeypatch.setattr(ollama_check.requests, "post", fake_post)

    with pytest.raises(OllamaCheckError) as error:
        precheck_models(["qwen2.5-coder:7b", "llama3"], BASE_URL)

    assert str(error.value) == (
        "Ollama model 'llama3' did not answer a one-token request: "
        "model requires more system memory"
    )


def test_an_error_response_without_a_message_is_reported_by_its_status(
    requested: list[str], monkeypatch: pytest.MonkeyPatch
):
    class NotJson(FakeResponse):
        def json(self) -> Any:
            raise ValueError("not json")

    monkeypatch.setattr(
        ollama_check.requests, "post", lambda url, json, timeout: NotJson({}, status_code=502)
    )

    with pytest.raises(OllamaCheckError, match="'qwen2.5-coder:7b' did not answer.*HTTP 502"):
        precheck_models(["qwen2.5-coder:7b"], BASE_URL)


def test_a_model_that_times_out_while_loading_is_named(
    requested: list[str], monkeypatch: pytest.MonkeyPatch
):
    def fake_post(url: str, json: dict[str, Any], timeout: float) -> FakeResponse:
        raise requests.Timeout("read timed out")

    monkeypatch.setattr(ollama_check.requests, "post", fake_post)

    with pytest.raises(OllamaCheckError, match="'qwen2.5-coder:7b' did not answer.*timed out"):
        precheck_models(["qwen2.5-coder:7b"], BASE_URL)


@pytest.mark.parametrize(
    "text",
    [
        "Connection error.",
        "Request timed out.",
        "[Errno 61] Connection refused",
        "CONNECTION ERROR",
    ],
)
def test_error_texts_that_point_at_the_infrastructure_are_recognised(text: str):
    assert is_infrastructure_error(text)


@pytest.mark.parametrize(
    "text", ["", "1 validation error for PaperScreeningResult", "Simulated LLM API error"]
)
def test_other_error_texts_are_not_infrastructure_errors(text: str):
    assert not is_infrastructure_error(text)
