import os

import pytest

from src.db.repository import get_repository
from src.llm.fake import (
    fake_download_pdf,
    fake_execute_retrieval,
    fake_pdf_url,
    set_fake_answers,
)
from src.llm.settings import Settings, get_settings
from tests.fakes import default_registry

# Tracing wraps the graph nodes at import time, which reads the settings: give that import a
# valid, tracing-off environment that a developer's shell or `.env` cannot change.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ.setdefault("OPENALEX_EMAIL", "tests@example.invalid")
os.environ.setdefault("REPOSITORY_BACKEND", "memory")


@pytest.fixture(autouse=True)
def test_profile(monkeypatch: pytest.MonkeyPatch):
    """Run every test on the `test` profile with the memory repository and a dummy email, no `.env`.

    Unit tests never see a database; only the integration tests select the postgres backend.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("PROFILE", "test")
    monkeypatch.setenv("REPOSITORY_BACKEND", "memory")
    monkeypatch.setenv("OPENALEX_EMAIL", "tests@example.invalid")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    get_repository.cache_clear()
    set_fake_answers(default_registry())
    yield
    get_settings.cache_clear()
    get_repository.cache_clear()


@pytest.fixture
def fake_surface(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Replace OpenAlex and the PDF download with fixtures, and write PDFs to a temp dir."""
    from src.pipeline.ingestion import node as ingestion_node
    from src.pipeline.search.api_client import OpenAlexClient

    monkeypatch.setattr(OpenAlexClient, "execute_retrieval", fake_execute_retrieval)
    monkeypatch.setattr(ingestion_node, "get_openalex_pdf_url", fake_pdf_url)
    monkeypatch.setattr(ingestion_node, "download_pdf", fake_download_pdf)
    monkeypatch.setenv("PDF_DIR", str(tmp_path))
    get_settings.cache_clear()
