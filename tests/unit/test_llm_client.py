import asyncio

import numpy as np
import pytest

from Screening_Agent.screening_schemas import PaperScreeningResult, ScreeningDecision
from src.llm.client import (
    INSTRUCTOR_MAX_RETRIES,
    SDK_MAX_RETRIES,
    get_embedder,
    get_llm,
)
from src.llm.settings import get_settings


def test_unknown_role_raises():
    with pytest.raises(ValueError, match="Unknown LLM role 'router'"):
        get_llm("router")


def test_test_profile_returns_the_fake_llm():
    llm = get_llm("screening")
    messages = [{"role": "user", "content": "Abstract: a plain abstract"}]

    result = asyncio.run(
        llm.chat.completions.create(
            model="any",
            response_model=PaperScreeningResult,
            messages=messages,
            max_retries=INSTRUCTOR_MAX_RETRIES,
        )
    )

    assert result.decision == ScreeningDecision.INCLUDE


def test_local_profile_builds_an_ollama_client_with_sdk_retries(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROFILE", "local")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.invalid:11434/v1")
    get_settings.cache_clear()

    llm = get_llm("extraction")

    assert llm.client.max_retries == SDK_MAX_RETRIES
    assert str(llm.client.base_url).startswith("http://ollama.invalid:11434/v1")


def test_fake_embedder_is_deterministic_and_normalized():
    embedder = get_embedder()

    first = embedder.encode(["alpha", "beta"], convert_to_numpy=True)
    again = embedder.encode(["alpha"], convert_to_numpy=True)

    assert first.shape == (2, 384)
    assert first.dtype == np.float32
    assert np.allclose(first[0], again[0])
    assert not np.allclose(first[0], first[1])
    assert np.allclose(np.linalg.norm(first, axis=1), 1.0, atol=1e-5)
