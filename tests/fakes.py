"""Canned fake-LLM answers for the pipeline's response models, registered by tests/conftest.py."""

from extract_agent.extraction_schemas import ExtractedPaperInfo, ExtractionConfidence
from Screening_Agent.screening_schemas import PaperScreeningResult, ScreeningDecision
from search_agent.schemas import AcademicQueryExpansionSchema
from src.llm.fake import Messages, Registry

FAIL_SENTINEL = "[FAKE:FAIL]"
EXCLUDE_SENTINEL = "[FAKE:EXCLUDE]"
UNCERTAIN_SENTINEL = "[FAKE:UNCERTAIN]"


def _screen(messages: Messages) -> PaperScreeningResult:
    prompt = messages[-1]["content"]
    if FAIL_SENTINEL in prompt:
        raise RuntimeError("Simulated LLM API error")
    if EXCLUDE_SENTINEL in prompt:
        decision, relevance = ScreeningDecision.EXCLUDE, 2
    elif UNCERTAIN_SENTINEL in prompt:
        decision, relevance = ScreeningDecision.UNCERTAIN, 5
    else:
        decision, relevance = ScreeningDecision.INCLUDE, 8
    return PaperScreeningResult(
        decision=decision,
        confidence_score=8,
        relevance_score=relevance,
        reasoning=f"Fake screening decision: {decision.value}.",
    )


def default_registry() -> Registry:
    """Canned answers for the three wired roles; screening answers via sentinels in the prompt."""
    return {
        AcademicQueryExpansionSchema: AcademicQueryExpansionSchema(
            synthetic_abstract=(
                "Social media use among adolescents shapes identity, peer relations and wellbeing."
            ),
            mandatory_entities=["social media", "adolescents", "wellbeing"],
        ),
        PaperScreeningResult: _screen,
        ExtractedPaperInfo: ExtractedPaperInfo(
            paper_type="qualitative interview study",
            method="semi-structured interviews",
            dataset="interviews with adolescents",
            task="how adolescents experience social media",
            main_findings="Adolescents use social media to negotiate identity and belonging.",
            limitations="not explicitly specified",
            relevance_to_research_question="Directly addresses the research question.",
            confidence=ExtractionConfidence.MEDIUM,
        ),
    }
