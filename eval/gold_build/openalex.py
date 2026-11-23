"""OpenAlex lookups for the pool build: single works by id or DOI."""

from typing import Any

import requests

from src.llm.settings import get_settings
from src.pipeline.search.api_client import OpenAlexClient

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT_S = 20
NOT_FOUND = 404


def fetch_work(reference: str) -> dict[str, Any] | None:
    """One work by OpenAlex id (`W123`) or DOI URL; None if OpenAlex does not know it."""
    settings = get_settings()
    headers = (
        {"Authorization": f"Bearer {settings.openalex_api_key}"}
        if settings.openalex_api_key
        else {}
    )
    try:
        response = requests.get(
            f"{OPENALEX_WORKS_URL}/{reference}",
            params={"mailto": settings.openalex_email},
            headers=headers,
            timeout=REQUEST_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"OpenAlex is not reachable for {reference}: {exc}") from exc
    if response.status_code == NOT_FOUND:
        return None
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"OpenAlex returned HTTP {response.status_code} for {reference}")
    return response.json()


def openalex_client() -> OpenAlexClient:
    """The pipeline's OpenAlex client, built from the settings."""
    settings = get_settings()
    return OpenAlexClient(email=settings.openalex_email, api_key=settings.openalex_api_key)
