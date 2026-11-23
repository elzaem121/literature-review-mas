"""Checks against Ollama's native API; this is not an LLM client and generates no text."""

from collections.abc import Iterable

import requests

REQUEST_TIMEOUT_S = 10
OPENAI_SUFFIX = "/v1"
LATEST_TAG = ":latest"
INFRASTRUCTURE_ERROR_MARKERS = ("connection error", "timed out", "connection refused")


class OllamaCheckError(RuntimeError):
    """Ollama is unreachable or a configured model is not pulled."""


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


def is_infrastructure_error(error_text: str) -> bool:
    """Whether a failed call's error text points at Ollama or the network, not at the model."""
    lowered = error_text.lower()
    return any(marker in lowered for marker in INFRASTRUCTURE_ERROR_MARKERS)
