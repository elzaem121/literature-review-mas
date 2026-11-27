"""Checks against Ollama's native API; this is not an LLM client, it only asks for one token."""

import re
from collections.abc import Iterable
from typing import Literal

import requests

REQUEST_TIMEOUT_S = 10
# The first request to a model has to load it into memory, which takes much longer than a listing.
LOAD_TIMEOUT_S = 300
PROBE_PROMPT = "Hello"
OPENAI_SUFFIX = "/v1"
LATEST_TAG = ":latest"
NUM_CTX_PARAMETER = re.compile(r"^num_ctx\s+(\d+)\s*$", re.MULTILINE)
OLLAMA_DEFAULT = "ollama_default"
INFRASTRUCTURE_ERROR_MARKERS = ("connection error", "timed out", "connection refused")


class OllamaCheckError(RuntimeError):
    """Ollama is unreachable, or a configured model is not pulled or cannot answer."""


def native_root(base_url: str) -> str:
    """The server root of an OpenAI-compatible base URL: the URL without its trailing `/v1`."""
    return base_url.rstrip("/").removesuffix(OPENAI_SUFFIX)


def check_models(models: Iterable[str], base_url: str) -> dict[str, str]:
    """Return the Ollama digest of each configured model, or fail naming what is wrong."""
    root = native_root(base_url)
    try:
        response = requests.get(f"{root}/api/tags", timeout=REQUEST_TIMEOUT_S)
        response.raise_for_status()
        pulled = {entry["name"]: entry["digest"] for entry in response.json()["models"]}
    except requests.RequestException as exc:
        raise OllamaCheckError(f"Ollama is not reachable at {root}") from exc
    digests: dict[str, str] = {}
    for tag in models:
        name = tag if ":" in tag else f"{tag}{LATEST_TAG}"
        if name not in pulled:
            raise OllamaCheckError(f"Ollama model '{tag}' is not pulled (ollama pull {tag})")
        digests[tag] = pulled[name]
    return digests


def precheck_models(models: Iterable[str], base_url: str) -> dict[str, str]:
    """Check the models are pulled, then make each answer a one-token request; return digests."""
    digests = check_models(models, base_url)
    root = native_root(base_url)
    for tag in digests:
        _answer_one_token(root, tag)
    return digests


def configured_context_length(tag: str, base_url: str) -> int | Literal["ollama_default"]:
    """The `num_ctx` that the model's Modelfile sets, or "ollama_default" when it sets none."""
    try:
        response = requests.post(
            f"{native_root(base_url)}/api/show", json={"model": tag}, timeout=REQUEST_TIMEOUT_S
        )
    except requests.RequestException as exc:
        raise OllamaCheckError(f"cannot read the settings of Ollama model '{tag}': {exc}") from exc
    if response.status_code >= 400:
        raise OllamaCheckError(
            f"cannot read the settings of Ollama model '{tag}': {_error_detail(response)}"
        )
    match = NUM_CTX_PARAMETER.search(response.json().get("parameters") or "")
    return int(match.group(1)) if match else OLLAMA_DEFAULT


def _answer_one_token(root: str, tag: str) -> None:
    """Make one model load and generate a single token, so a model that cannot load is caught."""
    try:
        response = requests.post(
            f"{root}/api/generate",
            json={
                "model": tag,
                "prompt": PROBE_PROMPT,
                "stream": False,
                "options": {"num_predict": 1},
            },
            timeout=LOAD_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise OllamaCheckError(
            f"Ollama model '{tag}' did not answer a one-token request: {exc}"
        ) from exc
    if response.status_code >= 400:
        raise OllamaCheckError(
            f"Ollama model '{tag}' did not answer a one-token request: {_error_detail(response)}"
        )


def _error_detail(response: requests.Response) -> str:
    """Ollama's own error message from an error response, else the status code."""
    try:
        return str(response.json()["error"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {response.status_code}"


def is_infrastructure_error(error_text: str) -> bool:
    """Whether a failed call's error text points at Ollama or the network, not at the model."""
    lowered = error_text.lower()
    return any(marker in lowered for marker in INFRASTRUCTURE_ERROR_MARKERS)
