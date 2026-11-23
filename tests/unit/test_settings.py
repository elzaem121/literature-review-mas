from pathlib import Path

import pytest
from pydantic import ValidationError

from src.llm.settings import Settings, get_settings


def test_v1_models_are_the_defaults(monkeypatch: pytest.MonkeyPatch):
    for name in ("SEARCH_MODEL", "SCREENING_MODEL", "EXTRACTION_MODEL", "EMBEDDING_MODEL"):
        monkeypatch.delenv(name, raising=False)

    settings = get_settings()

    assert settings.search_model == "qwen2.5-coder:7b"
    assert settings.screening_model == "qwen2.5-coder:7b"
    assert settings.extraction_model == "qwen2.5-coder:7b"
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"


def test_postgres_is_the_default_backend_and_needs_a_database_url(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("REPOSITORY_BACKEND")

    with pytest.raises(ValidationError, match="DATABASE_URL is required"):
        Settings(_env_file=None)


def test_memory_backend_needs_no_database_url():
    settings = Settings(_env_file=None)

    assert (settings.repository_backend, settings.database_url) == ("memory", None)


def test_unknown_backend_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REPOSITORY_BACKEND", "sqlite")

    with pytest.raises(ValidationError, match="repository_backend"):
        Settings(_env_file=None)


def test_openalex_email_is_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENALEX_EMAIL")

    with pytest.raises(ValidationError, match="openalex_email"):
        Settings(_env_file=None)


def test_empty_env_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "")

    assert Settings(_env_file=None).langsmith_tracing is False


def test_openalex_api_key_is_optional_and_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    assert Settings(_env_file=None).openalex_api_key is None

    monkeypatch.setenv("OPENALEX_API_KEY", "secret")

    assert Settings(_env_file=None).openalex_api_key == "secret"


def test_eval_data_dir_is_optional_and_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    assert Settings(_env_file=None).eval_data_dir is None

    monkeypatch.setenv("EVAL_DATA_DIR", "/data/eval")

    assert Settings(_env_file=None).eval_data_dir == Path("/data/eval")
