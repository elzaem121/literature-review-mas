from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def format_criteria_list(criteria: List[str]) -> str:
    if not criteria:
        return "None specified."
    return "\n".join(f"- {item}" for item in criteria)


class ScreeningDecision(str, Enum):
    """
    Final screening decision for one paper.
    """

    INCLUDE = "include"
    EXCLUDE = "exclude"
    UNCERTAIN = "uncertain"


class PublicationYearFilter(BaseModel):
    min_year: Optional[int] = None
    max_year: Optional[int] = None


class ReviewProtocol(BaseModel):
    research_question: str

    inclusion_criteria: List[str] = Field(default_factory=list)

    exclusion_criteria: List[str] = Field(default_factory=list)

    publication_year: PublicationYearFilter = PublicationYearFilter()

    additional_instructions: Optional[str] = None

    def format_inclusion_criteria(self) -> str:
        return format_criteria_list(self.inclusion_criteria)

    def format_exclusion_criteria(self) -> str:
        return format_criteria_list(self.exclusion_criteria)


class ResearchPaper(BaseModel):
    """
    Minimal paper schema expected from the Search Agent.
    This mirrors the Search Agent output, but keeps relevance_score optional
    because raw OpenAlex/search output may not always contain it.
    """

    title: str = Field(..., description="Official title of the paper.")
    abstract: str = Field(
        default="No abstract available.", description="Paper abstract or fallback text."
    )
    year: Optional[int] = Field(None, description="Publication year.")
    authors: List[str] = Field(default_factory=list, description="Author names.")
    doi: Optional[str] = Field(None, description="Digital Object Identifier URL.")
    url: Optional[str] = Field(None, description="Landing page or PDF URL.")
    relevance_score: Optional[int] = Field(
        None, description="Optional score from the Search Agent."
    )
    openalex_id: Optional[str] = Field(None, description="Bare OpenAlex work ID, e.g. W123.")
    pdf_url: Optional[str] = Field(None, description="Open-access PDF URL found at search time.")
    venue: Optional[str] = Field(None, description="Journal or venue name.")


class SearchAgentOutput(BaseModel):
    """
    Input container for papers coming from the Search Agent.
    """

    papers: List[ResearchPaper] = Field(default_factory=list)


class PaperScreeningResult(BaseModel):
    """
    Structured LLM decision for a single paper.
    """

    decision: ScreeningDecision = Field(..., description="include, exclude, or uncertain.")
    confidence_score: int = Field(
        ..., ge=1, le=10, description="Confidence in the decision from 1 to 10."
    )
    relevance_score: int = Field(..., ge=1, le=10, description="Topic relevance from 1 to 10.")
    matched_inclusion_criteria: List[str] = Field(
        default_factory=list, description="Inclusion criteria that appear to be fulfilled."
    )
    matched_exclusion_criteria: List[str] = Field(
        default_factory=list, description="Exclusion criteria that appear to be triggered."
    )
    reasoning: str = Field(
        ..., description="Short evidence-based explanation using only title/abstract/metadata."
    )


class ScreenedPaper(BaseModel):
    """
    Combines the original paper metadata with the screening decision.
    """

    paper: ResearchPaper
    screening: PaperScreeningResult


class ScreeningError(BaseModel):
    paper: ResearchPaper
    error: str


class ScreeningOutput(BaseModel):
    """
    Final output of the Screening Agent.
    """

    included_papers: List[ScreenedPaper] = Field(default_factory=list)
    excluded_papers: List[ScreenedPaper] = Field(default_factory=list)
    uncertain_papers: List[ScreenedPaper] = Field(default_factory=list)
    failed_papers: List[ScreeningError] = Field(default_factory=list)
