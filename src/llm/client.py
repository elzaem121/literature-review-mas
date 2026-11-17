"""The only place LLM and embedding clients are built."""

from functools import lru_cache
from typing import Any

import instructor
from instructor.core.client import AsyncInstructor
from openai import AsyncOpenAI

from src.llm.fake import FakeEmbedder, FakeLLM, default_registry
from src.llm.settings import get_settings
from src.llm.tracing import maybe_wrap_openai

WIRED_ROLES = ("search", "screening", "extraction")
OLLAMA_API_KEY = "local-ollama-key"
SDK_MAX_RETRIES = 3
INSTRUCTOR_MAX_RETRIES = 2


def get_llm(role: str) -> AsyncInstructor | FakeLLM:
    """Return the Instructor-patched async client for a role (unknown roles raise)."""
    if role not in WIRED_ROLES:
        raise ValueError(f"Unknown LLM role '{role}'; expected one of {WIRED_ROLES}")
    settings = get_settings()
    if settings.profile == "test":
        return FakeLLM(default_registry())
    client = AsyncOpenAI(
        base_url=settings.ollama_base_url, api_key=OLLAMA_API_KEY, max_retries=SDK_MAX_RETRIES
    )
    return instructor.from_openai(maybe_wrap_openai(client), mode=instructor.Mode.JSON)


def get_embedder() -> Any:
    """Return the embedder: MiniLM in-process on `local`, a deterministic fake on `test`."""
    settings = get_settings()
    if settings.profile == "test":
        return FakeEmbedder()
    return _load_sentence_transformer(settings.embedding_model)


@lru_cache
def _load_sentence_transformer(model_name: str) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)
