"""Truncation check (G7): does Ollama cut extraction prompts short?

`python -m eval.harness.truncation_check` extracts the extraction-gold paper with the most retrieved
text and compares the prompt tokens Ollama reports with the model family's own tokenizer count.
"""

import argparse
import asyncio
from pathlib import Path
from typing import Any

from eval.harness.adapters.phase1 import Phase1Adapter, extraction_messages, reported_prompt_tokens
from eval.harness.data_dir import data_dir
from eval.harness.gold import DEFAULT_GOLD_DIR, load_extraction_gold, load_pool
from eval.harness.ollama_check import check_models
from eval.harness.records import RetrievedChunk
from eval.harness.run import paper_info, verified_pages
from eval.harness.topics import TOPICS_DIR, load_topic
from src.llm.settings import get_settings

DEFAULT_TOKENIZER = "Qwen/Qwen2.5-Coder-7B-Instruct"
TRUNCATION_TOLERANCE = 0.05


def retrieved_characters(chunks: list[RetrievedChunk]) -> int:
    """The number of characters of retrieved text that go into one extraction prompt."""
    return sum(len(chunk.text) for chunk in chunks)


def largest_paper(retrieval: dict[str, list[RetrievedChunk]]) -> str:
    """The paper key with the most retrieved characters."""
    if not retrieval:
        raise ValueError("no extraction-gold paper to check")
    return max(retrieval, key=lambda key: retrieved_characters(retrieval[key]))


def is_truncated(reported_tokens: int, tokenizer_tokens: int) -> bool:
    """Truncation: Ollama reports fewer prompt tokens than the tokenizer, beyond the tolerance."""
    return reported_tokens < tokenizer_tokens * (1 - TRUNCATION_TOLERANCE)


def tokenizer_prompt_tokens(messages: list[dict[str, str]], tokenizer_id: str) -> int:
    """Count the chat-templated prompt tokens with the model family's Hugging Face tokenizer."""
    from transformers import AutoTokenizer  # slow to import, so only the real check pays for it

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_id)
    encoded = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    return len(encoded["input_ids"])


async def check_truncation(
    data_root: Path,
    tokenizer_id: str = DEFAULT_TOKENIZER,
    *,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    topics_dir: Path = TOPICS_DIR,
) -> dict[str, Any]:
    """Run one extraction call on the largest gold paper and compare the two token counts."""
    settings = get_settings()
    check_models([settings.extraction_model], settings.ollama_base_url)
    adapter = Phase1Adapter()
    papers = {paper.paper_key: paper for paper in load_extraction_gold(gold_dir)}
    retrieval = {
        key: adapter.retrieve(key, verified_pages(data_root, paper))
        for key, paper in papers.items()
    }
    key = largest_paper(retrieval)
    gold = papers[key]
    pool_paper = next(p for p in load_pool(gold_dir, gold.topic_id) if p.paper_key == key)
    topic = load_topic(gold.topic_id, topics_dir)
    messages = extraction_messages(paper_info(pool_paper), retrieval[key], topic.research_question)
    reported = await reported_prompt_tokens(messages)
    expected = tokenizer_prompt_tokens(messages, tokenizer_id)
    return {
        "paper_key": key,
        "retrieved_characters": retrieved_characters(retrieval[key]),
        "ollama_prompt_tokens": reported,
        "tokenizer": tokenizer_id,
        "tokenizer_prompt_tokens": expected,
        "truncated": is_truncated(reported, expected),
    }


def main(argv: list[str] | None = None) -> int:
    """Command line entry point; prints both token counts and the verdict."""
    parser = argparse.ArgumentParser(
        description="Check whether Ollama truncates extraction prompts."
    )
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(check_truncation(data_dir(), args.tokenizer))
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    for name, value in result.items():
        print(f"{name}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
