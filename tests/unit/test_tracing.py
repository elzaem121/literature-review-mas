import pytest

from src.llm import tracing
from src.llm.settings import get_settings


@pytest.mark.parametrize(("switch", "expected"), [("true", True), ("false", False)])
def test_tracing_follows_the_langsmith_tracing_setting(
    monkeypatch: pytest.MonkeyPatch, switch: str, expected: bool
):
    monkeypatch.setattr(tracing, "_LANGSMITH_AVAILABLE", True)
    monkeypatch.setenv("LANGSMITH_TRACING", switch)
    get_settings.cache_clear()

    assert tracing.tracing_enabled() is expected


def test_an_api_key_alone_does_not_enable_tracing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(tracing, "_LANGSMITH_AVAILABLE", True)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.setenv("LANGSMITH_API_KEY", "key")
    get_settings.cache_clear()

    assert tracing.tracing_enabled() is False
