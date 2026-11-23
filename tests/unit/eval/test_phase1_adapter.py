import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import openai
import pytest

from eval.harness.adapters import ADAPTERS, get_adapter, phase1
from eval.harness.adapters.phase1 import (
    RETRIEVAL_FIELDS,
    Phase1Adapter,
    extraction_messages,
    v1_status,
)
from eval.harness.gold import load_page_text
from eval.harness.ollama_check import is_infrastructure_error
from eval.harness.records import SCORED_FIELDS, RetrievedChunk
from eval.harness.topics import Topic, load_topic
from src.llm.fake import get_fake_answers, set_fake_answers
from src.pipeline.extraction.schemas import ExtractedPaperInfo
from src.pipeline.ingestion.chunking import chunk_pages
from src.pipeline.ingestion.retrieval import FIELD_QUERIES, RETRIEVAL_TOP_K

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
EVAL_FIXTURES = FIXTURES / "eval"
PAPER = {"title": "Study", "openalex_id": "WA1", "year": 2023}


@pytest.fixture
def topic() -> Topic:
    return load_topic("ta_mini", EVAL_FIXTURES / "topics")


@pytest.fixture
def pages() -> list[str]:
    return load_page_text(EVAL_FIXTURES / "data", "WA1").pages


def run[T](coroutine: Any) -> T:
    return asyncio.run(coroutine)


@pytest.mark.parametrize(
    "value",
    [
        "not specified",
        "Not specified",
        "  NOT SPECIFIED  ",
        "not specified in the chunks",
        "not explicitly specified",
        "Not explicitly specified.",
        "not mentioned",
        "not stated",
        "no empirical dataset",
        "No empirical dataset",
        "",
        "   ",
    ],
)
def test_v1_absence_phrases_and_an_empty_value_are_not_found(value: str):
    assert v1_status(value) == "not_found"


@pytest.mark.parametrize(
    "value",
    [
        "semi-structured interviews",
        "Interviews with twenty adolescents",
        "No empirical dataset was collected, but a corpus of 40 papers was read",
        "The authors do not state a specific limitation, but note the small sample",
    ],
)
def test_any_other_v1_value_is_found(value: str):
    assert v1_status(value) == "found"


def test_the_retrieval_field_keys_are_exactly_the_pipelines_and_cover_the_scored_fields():
    assert set(RETRIEVAL_FIELDS) == set(FIELD_QUERIES)
    assert sorted(RETRIEVAL_FIELDS.values()) == sorted(SCORED_FIELDS)


def test_the_registry_returns_a_fresh_phase1_adapter_and_rejects_other_names():
    assert list(ADAPTERS) == ["phase1"]
    assert isinstance(get_adapter("phase1"), Phase1Adapter)
    with pytest.raises(
        ValueError, match="Unknown adapter 'phase9'; expected one of \\['phase1'\\]"
    ):
        get_adapter("phase9")


def test_the_provenance_names_the_models_prompts_and_retrieval_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("SCREENING_MODEL", "other-model:1b")

    provenance = Phase1Adapter().provenance()

    assert provenance == {
        "models": {
            "search": "qwen2.5-coder:7b",
            "screening": "other-model:1b",
            "extraction": "qwen2.5-coder:7b",
        },
        "prompt_versions": {"search": "v1", "screening": "v1", "extraction": "v1"},
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "chunker_version": "v1",
        "retrieval_top_k": 5,
        "concurrency": 3,
    }


def test_search_returns_the_papers_the_abstract_and_the_fallback_flag(fake_surface, topic: Topic):
    record = run(Phase1Adapter().search(topic))

    assert [paper["openalex_id"] for paper in record.papers][0] == "W9000000001"
    assert record.synthetic_abstract.startswith("Social media use among adolescents")
    assert record.fallback_used is False


def test_screen_maps_all_four_buckets_in_input_order(topic: Topic):
    papers = json.loads((FIXTURES / "search_results.json").read_text("utf-8"))["papers"]

    records = run(Phase1Adapter().screen(papers, topic))

    assert [(r.paper_key, r.decision) for r in records] == [
        ("W9000000001", "include"),
        ("W9000000002", "exclude"),
        ("W9000000003", "uncertain"),
        ("W9000000004", "failed"),
        ("W9000000005", "include"),
    ]
    included, failed = records[0], records[3]
    assert included.reasoning == "Fake screening decision: include."
    assert included.error is None
    assert "Simulated LLM API error" in failed.error
    assert failed.reasoning == ""


def test_screen_stops_when_the_node_does_not_return_every_paper(
    monkeypatch: pytest.MonkeyPatch, topic: Topic
):
    async def lossy_node(state: dict) -> dict:
        result = {key: [] for key in ("excluded_papers", "uncertain_papers", "failed_papers")}
        return {"screening_results": {**result, "included_papers": []}}

    monkeypatch.setattr(phase1, "screening_node", lossy_node)

    with pytest.raises(ValueError, match="returned records for \\[\\], expected \\['WA1'\\]"):
        run(Phase1Adapter().screen([PAPER], topic))


def test_screen_passes_the_rendered_criteria_to_the_node(
    monkeypatch: pytest.MonkeyPatch, topic: Topic
):
    seen: dict = {}

    async def spy(state: dict) -> dict:
        seen.update(state)
        return {"screening_results": {}}

    monkeypatch.setattr(phase1, "screening_node", spy)

    with pytest.raises(KeyError):
        run(Phase1Adapter().screen([PAPER], topic))

    assert seen["research_question"] == "How do teenagers use social media?"
    assert seen["inclusion_criteria"] == [check.yes for check in topic.checks]
    assert seen["exclusion_criteria"] == [check.no for check in topic.checks]
    assert seen["additional_info"] is None
    assert seen["raw_papers"] == [PAPER]


def test_retrieve_gives_every_chunk_its_page_ordinal_and_rank(pages: list[str]):
    chunks = Phase1Adapter().retrieve("WA1", pages)

    by_ordinal = {chunk.ordinal: chunk for chunk in chunk_pages(pages)}
    assert {chunk.field for chunk in chunks} == set(SCORED_FIELDS)
    for chunk in chunks:
        source = by_ordinal[chunk.ordinal]
        assert (chunk.paper_key, chunk.page, chunk.text) == ("WA1", source.page, source.text)
    for field in SCORED_FIELDS:
        ranks = [chunk.rank for chunk in chunks if chunk.field == field]
        assert ranks == list(range(1, len(ranks) + 1))
        assert len(ranks) <= RETRIEVAL_TOP_K


def test_a_retrieved_text_that_appears_on_two_pages_maps_to_the_first(pages: list[str]):
    chunks = Phase1Adapter().retrieve("WX", ["same text", "same text"])

    assert {(chunk.page, chunk.ordinal) for chunk in chunks} == {(1, 0)}


def test_retrieve_rejects_a_paper_without_text():
    with pytest.raises(ValueError, match="paper WX has no extractable text"):
        Phase1Adapter().retrieve("WX", ["   ", ""])


def test_extract_maps_the_scored_fields_and_keeps_the_raw_answer(topic: Topic, pages: list[str]):
    adapter = Phase1Adapter()

    output = run(adapter.extract(PAPER, adapter.retrieve("WA1", pages), topic))

    assert output.error is None
    assert [(f.field, f.status) for f in output.fields] == [
        ("method", "found"),
        ("dataset", "found"),
        ("task", "found"),
        ("main_findings", "found"),
        ("limitations", "not_found"),
    ]
    assert output.fields[0].value == "semi-structured interviews"
    assert output.fields[0].paper_key == "WA1"
    assert output.raw["limitations"] == "not explicitly specified"
    assert output.raw["paper_type"] == "qualitative interview study"


def test_extract_sends_the_pipelines_messages_for_the_retrieved_chunks(
    topic: Topic, pages: list[str]
):
    sent: list[list[dict]] = []
    answers = get_fake_answers()
    canned = answers[ExtractedPaperInfo]

    def capture(messages: list[dict]) -> ExtractedPaperInfo:
        sent.append(messages)
        return canned

    set_fake_answers({**answers, ExtractedPaperInfo: capture})
    adapter = Phase1Adapter()
    chunks = adapter.retrieve("WA1", pages)

    run(adapter.extract(PAPER, chunks, topic))

    assert sent == [extraction_messages(PAPER, chunks, topic.research_question)]


def test_extraction_messages_put_each_fields_chunks_in_rank_order(topic: Topic):
    chunks = [
        RetrievedChunk(paper_key="WA1", field="method", rank=2, page=1, ordinal=1, text="SECOND"),
        RetrievedChunk(paper_key="WA1", field="method", rank=1, page=1, ordinal=0, text="FIRST"),
        RetrievedChunk(paper_key="WA1", field="task", rank=1, page=2, ordinal=2, text="TASKTEXT"),
    ]

    user_prompt = extraction_messages(PAPER, chunks, topic.research_question)[1]["content"]

    assert user_prompt.index("FIRST") < user_prompt.index("SECOND")
    assert "TASKTEXT" in user_prompt
    assert "Study" in user_prompt


def test_a_failed_extraction_call_is_kept_as_an_error_not_raised(topic: Topic, pages: list[str]):
    def refuse(messages: list[dict]) -> ExtractedPaperInfo:
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://localhost/v1"))

    set_fake_answers({**get_fake_answers(), ExtractedPaperInfo: refuse})
    adapter = Phase1Adapter()

    output = run(adapter.extract(PAPER, adapter.retrieve("WA1", pages), topic))

    assert output.fields == []
    assert output.raw is None
    assert output.error == "APIConnectionError: Connection error."
    assert is_infrastructure_error(output.error)


def test_an_error_that_is_not_an_llm_failure_is_not_swallowed(topic: Topic, pages: list[str]):
    def bug(messages: list[dict]) -> ExtractedPaperInfo:
        raise KeyError("a programming error")

    set_fake_answers({**get_fake_answers(), ExtractedPaperInfo: bug})
    adapter = Phase1Adapter()

    with pytest.raises(KeyError):
        run(adapter.extract(PAPER, adapter.retrieve("WA1", pages), topic))
