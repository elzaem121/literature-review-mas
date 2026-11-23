import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval.harness import truncation_check
from eval.harness.adapters import phase1
from eval.harness.adapters.phase1 import reported_prompt_tokens
from eval.harness.records import RetrievedChunk
from eval.harness.truncation_check import (
    check_truncation,
    is_truncated,
    largest_paper,
    retrieved_characters,
    tokenizer_prompt_tokens,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "eval"
MESSAGES = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]


def chunk(text: str) -> RetrievedChunk:
    return RetrievedChunk(paper_key="W", field="method", rank=1, page=1, ordinal=0, text=text)


def test_the_largest_paper_is_the_one_with_the_most_retrieved_characters():
    retrieval = {
        "small": [chunk("ab")],
        "large": [chunk("abc"), chunk("de")],
        "mid": [chunk("abcd")],
    }

    assert retrieved_characters(retrieval["large"]) == 5
    assert largest_paper(retrieval) == "large"


def test_there_must_be_a_paper_to_check():
    with pytest.raises(ValueError, match="no extraction-gold paper to check"):
        largest_paper({})


@pytest.mark.parametrize(
    ("reported", "expected", "truncated"),
    [
        (2050, 10800, True),
        (949, 1000, True),
        (950, 1000, False),
        (1000, 1000, False),
        (1060, 1000, False),
    ],
)
def test_truncation_means_ollama_reports_over_five_percent_fewer_tokens(
    reported: int, expected: int, truncated: bool
):
    assert is_truncated(reported, expected) is truncated


def test_the_tokenizer_count_is_the_length_of_the_templated_input_ids(
    monkeypatch: pytest.MonkeyPatch,
):
    seen: dict = {}

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, tokenizer_id: str) -> "FakeTokenizer":
            seen["id"] = tokenizer_id
            return cls()

        def apply_chat_template(self, messages: list, tokenize: bool, add_generation_prompt: bool):
            seen.update(messages=messages, tokenize=tokenize, generation=add_generation_prompt)
            return {"input_ids": list(range(7)), "attention_mask": [1] * 7}

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoTokenizer=FakeTokenizer))

    assert tokenizer_prompt_tokens(MESSAGES, "Qwen/Qwen2.5-Coder-7B-Instruct") == 7
    assert seen == {
        "id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "messages": MESSAGES,
        "tokenize": True,
        "generation": True,
    }


def test_the_reported_count_is_the_prompt_tokens_of_the_completion(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[dict] = []

    async def create_with_completion(**kwargs):
        calls.append(kwargs)
        return None, SimpleNamespace(usage=SimpleNamespace(prompt_tokens=2050))

    llm = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create_with_completion=create_with_completion)
        )
    )
    monkeypatch.setattr(phase1, "get_llm", lambda role: llm)

    assert asyncio.run(reported_prompt_tokens(MESSAGES)) == 2050
    assert calls[0]["messages"] == MESSAGES
    assert calls[0]["model"] == "qwen2.5-coder:7b"
    assert calls[0]["temperature"] == 0


def test_the_check_extracts_the_largest_gold_paper_and_compares_the_two_counts(
    monkeypatch: pytest.MonkeyPatch,
):
    checked: list[list[str]] = []
    sent: list[list[dict]] = []

    async def reported(messages: list[dict]) -> int:
        sent.append(messages)
        return 100

    monkeypatch.setattr(truncation_check, "check_models", lambda m, url: checked.append(m) or {})
    monkeypatch.setattr(truncation_check, "reported_prompt_tokens", reported)
    monkeypatch.setattr(truncation_check, "tokenizer_prompt_tokens", lambda m, hf_id: 400)

    result = asyncio.run(
        check_truncation(
            FIXTURES / "data",
            "some/tokenizer",
            gold_dir=FIXTURES / "gold",
            topics_dir=FIXTURES / "topics",
        )
    )

    assert checked == [["qwen2.5-coder:7b"]]
    assert result["paper_key"] == "WA1"
    assert result["retrieved_characters"] > 0
    assert result["tokenizer"] == "some/tokenizer"
    assert (result["ollama_prompt_tokens"], result["tokenizer_prompt_tokens"]) == (100, 400)
    assert result["truncated"] is True
    assert "Social Media Use and Everyday Identity Work Among Teenagers" in sent[0][1]["content"]
