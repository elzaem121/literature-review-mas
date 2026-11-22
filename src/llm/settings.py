"""Application settings, validated once at startup from the environment and `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration of the system; the only place that reads the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    profile: Literal["local", "test"] = "local"
    ollama_base_url: str = "http://localhost:11434/v1"
    search_model: str = "qwen2.5-coder:7b"
    screening_model: str = "qwen2.5-coder:7b"
    extraction_model: str = "qwen2.5-coder:7b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    repository_backend: Literal["memory", "postgres"] = "postgres"
    database_url: str | None = None
    openalex_email: str
    openalex_api_key: str | None = None
    langsmith_tracing: bool = False
    pdf_dir: Path = Path("pdfs_auto")

    @model_validator(mode="after")
    def _require_database_url_for_postgres(self) -> Self:
        if self.repository_backend == "postgres" and not self.database_url:
            raise ValueError("DATABASE_URL is required when REPOSITORY_BACKEND is 'postgres'")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the validated settings; raises a pydantic error if a required value is missing."""
    return Settings()
