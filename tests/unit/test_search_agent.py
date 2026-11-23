import asyncio
import json

import pytest

from src.llm.fake import FIXTURES_DIR, fake_execute_retrieval, get_fake_answers, set_fake_answers
from src.pipeline.search.agent import UniversalAcademicSearchAgent, format_openalex_work
from src.pipeline.search.api_client import OpenAlexClient
from src.pipeline.search.schemas import AcademicQueryExpansionSchema

QUERY = "social media and adolescents"
FIRST_FIXTURE_PAPER = {
    "title": "Social Media Use and Everyday Identity Work Among Teenagers",
    "abstract": (
        "Teenagers use social media every day to negotiate identity and peer relations. "
        "This interview study describes how adolescents experience wellbeing and belonging online."
    ),
    "year": 2023,
    "authors": ["Alice Example", "Bob Sample"],
    "doi": "https://doi.org/10.1000/fixture.shared.1",
    "url": "https://openalex.org/W9000000001",
    "relevance_score": 0,
    "openalex_id": "W9000000001",
    "pdf_url": "https://fixtures.invalid/pdf/1.pdf",
    "venue": "Journal of Fixture Studies",
}


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> UniversalAcademicSearchAgent:
    monkeypatch.setattr(OpenAlexClient, "execute_retrieval", fake_execute_retrieval)
    return UniversalAcademicSearchAgent(openalex_email="tests@example.invalid", model_name="fake")


def _run_cycle(agent: UniversalAcademicSearchAgent, **kwargs) -> dict:
    return asyncio.run(agent.run_precise_retrieval_cycle(QUERY, **kwargs))


def test_cycle_returns_the_synthetic_abstract_and_no_fallback(agent):
    result = _run_cycle(agent)

    expected_abstract = get_fake_answers()[AcademicQueryExpansionSchema].synthetic_abstract
    assert result["synthetic_abstract"] == expected_abstract
    assert result["fallback_used"] is False
    assert result["papers"][0] == FIRST_FIXTURE_PAPER


def test_cycle_marks_the_fallback_and_searches_with_the_raw_query(agent):
    def failing_expansion(messages):
        raise RuntimeError("Simulated LLM timeout")

    registry = dict(get_fake_answers())
    registry[AcademicQueryExpansionSchema] = failing_expansion
    set_fake_answers(registry)

    result = _run_cycle(agent)

    assert result["fallback_used"] is True
    assert result["synthetic_abstract"] == QUERY
    assert len(result["papers"]) > 0


def test_cycle_still_prunes_papers_to_the_target_count(agent):
    assert len(_run_cycle(agent, target_output_count=2)["papers"]) == 2


def test_format_openalex_work_matches_the_search_output_for_a_fixture_work(agent):
    work = json.loads((FIXTURES_DIR / "openalex_works.json").read_text(encoding="utf-8"))[0]

    assert format_openalex_work(work, agent.openalex_client) == FIRST_FIXTURE_PAPER


def test_format_openalex_work_handles_a_work_with_missing_fields(agent):
    work = {"doi": "https://doi.org/10.1000/sparse", "title": None}

    assert format_openalex_work(work, agent.openalex_client) == {
        "title": "",
        "abstract": "",
        "year": None,
        "authors": [],
        "doi": "https://doi.org/10.1000/sparse",
        "url": "https://doi.org/10.1000/sparse",
        "relevance_score": 0,
        "openalex_id": None,
        "pdf_url": None,
        "venue": None,
    }
