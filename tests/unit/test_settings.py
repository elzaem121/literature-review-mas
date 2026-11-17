import pytest
from pydantic import ValidationError

from src.llm.settings import Settings, get_settings


def test_v1_models_are_the_defaults(monkeypatch: pytest.MonkeyPatch):
    for name in ("SEARCH_MODEL", "SCREENING_MODEL", "EXTRACTION_MODEL", "EMBEDDING_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = get_settings()

    assert settings.search_model == "qwen2.5-coder:7b"
    assert settings.screening_model == "qwen2.5-coder:7b"
    assert settings.extraction_model == "qwen2.5-coder:7b"
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.database_url is None


def test_openalex_email_is_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENALEX_EMAIL")

    with pytest.raises(ValidationError, match="openalex_email"):
        Settings(_env_file=None)


def test_empty_env_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "")

    assert Settings(_env_file=None).langsmith_tracing is False
