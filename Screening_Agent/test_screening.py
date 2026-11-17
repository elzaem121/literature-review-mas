import json
from pathlib import Path

import pytest

from Screening_Agent.screening_agent import AcademicScreeningAgent
from Screening_Agent.screening_schemas import (
    PaperScreeningResult,
    ResearchPaper,
    ReviewProtocol,
    ScreenedPaper,
    ScreeningDecision,
    ScreeningError,
    format_criteria_list,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_CONFIG_PATH = REPO_ROOT / "Screening_Agent" / "testdaten" / "review_config.json"
SEARCH_RESULTS_PATH = REPO_ROOT / "tests" / "fixtures" / "search_results.json"


def make_paper(title: str, year: int | None = 2024) -> ResearchPaper:
    return ResearchPaper(title=title, abstract="Sample abstract.", year=year)


def make_screened(title: str, decision: ScreeningDecision) -> ScreenedPaper:
    return ScreenedPaper(
        paper=make_paper(title),
        screening=PaperScreeningResult(
            decision=decision,
            confidence_score=8,
            relevance_score=7,
            reasoning="Test reasoning.",
        ),
    )


class TestSchemaLoading:
    def test_load_review_protocol(self):
        protocol = AcademicScreeningAgent.load_review_protocol(REVIEW_CONFIG_PATH)

        assert "social media" in protocol.research_question.lower()
        assert len(protocol.inclusion_criteria) >= 1
        assert protocol.publication_year.min_year == 2020

    def test_load_search_results(self):
        papers = AcademicScreeningAgent.load_search_results(SEARCH_RESULTS_PATH)

        assert len(papers) >= 1
        assert papers[0].title


class TestProtocolFormatting:
    def test_format_criteria_list(self):
        assert format_criteria_list([]) == "None specified."
        assert format_criteria_list(["A", "B"]) == "- A\n- B"

    def test_review_protocol_formatters(self):
        protocol = ReviewProtocol(
            research_question="RQ",
            inclusion_criteria=["Include adolescents"],
            exclusion_criteria=["Exclude adults only"],
        )

        assert "- Include adolescents" in protocol.format_inclusion_criteria()
        assert "- Exclude adults only" in protocol.format_exclusion_criteria()


class TestPublicationYearFilter:
    def test_excludes_papers_before_min_year(self):
        protocol = ReviewProtocol(
            research_question="RQ",
            publication_year={"min_year": 2020},
        )
        papers = [
            make_paper("Old paper", 2018),
            make_paper("Recent paper", 2024),
        ]

        eligible, excluded = AcademicScreeningAgent.apply_publication_year_filter(
            papers, protocol
        )

        assert len(eligible) == 1
        assert eligible[0].title == "Recent paper"
        assert len(excluded) == 1
        assert excluded[0].screening.decision == ScreeningDecision.EXCLUDE

    def test_keeps_papers_without_year_for_llm_review(self):
        protocol = ReviewProtocol(
            research_question="RQ",
            publication_year={"min_year": 2020},
        )
        papers = [make_paper("Unknown year", None)]

        eligible, excluded = AcademicScreeningAgent.apply_publication_year_filter(
            papers, protocol
        )

        assert len(eligible) == 1
        assert excluded == []


class TestBuildScreeningOutput:
    def test_buckets_decisions(self):
        screened = [
            make_screened("Included", ScreeningDecision.INCLUDE),
            make_screened("Excluded", ScreeningDecision.EXCLUDE),
            make_screened("Uncertain", ScreeningDecision.UNCERTAIN),
        ]

        output = AcademicScreeningAgent.build_screening_output(screened)

        assert len(output.included_papers) == 1
        assert len(output.excluded_papers) == 1
        assert len(output.uncertain_papers) == 1

    def test_includes_pre_excluded_and_failed_papers(self):
        screened = [make_screened("Included", ScreeningDecision.INCLUDE)]
        pre_excluded = [make_screened("Too old", ScreeningDecision.EXCLUDE)]
        failed = [ScreeningError(paper=make_paper("Broken"), error="LLM timeout")]

        output = AcademicScreeningAgent.build_screening_output(
            screened,
            failed=failed,
            pre_excluded=pre_excluded,
        )

        assert len(output.included_papers) == 1
        assert len(output.excluded_papers) == 1
        assert len(output.failed_papers) == 1


class TestMainEntryContract:
    def test_screen_file_with_protocol_signature(self):
        import inspect

        signature = inspect.signature(AcademicScreeningAgent.screen_file_with_protocol)
        assert "protocol" in signature.parameters

    def test_review_config_round_trip(self):
        protocol = AcademicScreeningAgent.load_review_protocol(REVIEW_CONFIG_PATH)
        payload = json.loads(REVIEW_CONFIG_PATH.read_text(encoding="utf-8"))

        assert protocol.research_question == payload["research_question"]
        assert protocol.inclusion_criteria == payload["inclusion_criteria"]
