import asyncio
import json
from pathlib import Path

from Orchestration.nodes import screening_node

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _state() -> dict:
    papers = json.loads((FIXTURES / "search_results.json").read_text(encoding="utf-8"))["papers"]
    return {
        "research_question": "How do teenagers use social media?",
        "inclusion_criteria": ["Studies adolescents"],
        "exclusion_criteria": ["Marketing studies"],
        "additional_info": None,
        "raw_papers": papers,
    }


def test_sentinels_split_the_fixture_papers_into_the_four_buckets():
    result = asyncio.run(screening_node(_state()))["screening_results"]

    assert [p["paper"]["openalex_id"] for p in result["included_papers"]] == [
        "W9000000001",
        "W9000000005",
    ]
    assert [p["paper"]["openalex_id"] for p in result["excluded_papers"]] == ["W9000000002"]
    assert [p["paper"]["openalex_id"] for p in result["uncertain_papers"]] == ["W9000000003"]
    assert [p["paper"]["openalex_id"] for p in result["failed_papers"]] == ["W9000000004"]


def test_a_failing_llm_call_is_reported_not_retried_by_hand():
    result = asyncio.run(screening_node(_state()))["screening_results"]

    assert "Simulated LLM API error" in result["failed_papers"][0]["error"]
