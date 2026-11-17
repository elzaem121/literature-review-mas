import os

import pytest

from src.llm.fake import (
    fake_download_pdf,
    fake_execute_retrieval,
    fake_pdf_url,
    set_fake_answers,
)
from src.llm.settings import Settings, get_settings
from tests.fakes import default_registry

# Tracing wraps the graph nodes at import time, so a developer's key must never reach tests.
os.environ.pop("LANGSMITH_API_KEY", None)


@pytest.fixture(autouse=True)
def test_profile(monkeypatch: pytest.MonkeyPatch):
    """Run every test on the `test` profile, with a dummy OpenAlex email and no `.env` file."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("PROFILE", "test")
    monkeypatch.setenv("OPENALEX_EMAIL", "tests@example.invalid")
    get_settings.cache_clear()
    set_fake_answers(default_registry())
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_surface(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Replace OpenAlex and the PDF download with fixtures, and write PDFs to a temp dir."""
    from src.pipeline.ingestion import node as ingestion_node
    from src.pipeline.search.api_client import OpenAlexClient

    monkeypatch.setattr(OpenAlexClient, "execute_retrieval", fake_execute_retrieval)
    monkeypatch.setattr(ingestion_node, "get_openalex_pdf_url", fake_pdf_url)
    monkeypatch.setattr(ingestion_node, "download_pdf", fake_download_pdf)
    monkeypatch.setattr(ingestion_node, "PDF_DIR", tmp_path)
