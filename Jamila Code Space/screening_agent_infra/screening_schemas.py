from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ScreeningDecision(str, Enum):
    """
    Final screening decision for one paper.
    """
    INCLUDE = "include"
    EXCLUDE = "exclude"
    UNCERTAIN = "uncertain"


class ResearchPaper(BaseModel):
    """
    Minimal paper schema expected from the Search Agent.
    This mirrors the Search Agent output, but keeps relevance_score optional
    because raw OpenAlex/search output may not always contain it.
    """
    title: str = Field(..., description="Official title of the paper.")
    abstract: str = Field(default="No abstract available.", description="Paper abstract or fallback text.")
    year: Optional[int] = Field(None, description="Publication year.")
    authors: List[str] = Field(default_factory=list, description="Author names.")
    doi: Optional[str] = Field(None, description="Digital Object Identifier URL.")
    url: Optional[str] = Field(None, description="Landing page or PDF URL.")
    relevance_score: Optional[int] = Field(None, description="Optional score from the Search Agent.")


class SearchAgentOutput(BaseModel):
    """
    Input container for papers coming from the Search Agent.
    """
    papers: List[ResearchPaper] = Field(default_factory=list)


class PaperScreeningResult(BaseModel):
    """
    Structured LLM decision for a single paper.
    """
    print("Result entered")
    decision: ScreeningDecision = Field(..., description="include, exclude, or uncertain.")
    confidence_score: int = Field(..., ge=1, le=10, description="Confidence in the decision from 1 to 10.")
    relevance_score: int = Field(..., ge=1, le=10, description="Topic relevance from 1 to 10.")
    matched_inclusion_criteria: List[str] = Field(
        default_factory=list,
        description="Inclusion criteria that appear to be fulfilled."
    )
    matched_exclusion_criteria: List[str] = Field(
        default_factory=list,
        description="Exclusion criteria that appear to be triggered."
    )
    reasoning: str = Field(
        ...,
        description="Short evidence-based explanation using only title/abstract/metadata."
    )


class ScreenedPaper(BaseModel):
    """
    Combines the original paper metadata with the screening decision.
    """
    paper: ResearchPaper
    screening: PaperScreeningResult


class ScreeningOutput(BaseModel):
    """
    Final output of the Screening Agent.
    """
    print("Output entered")
    included_papers: List[ScreenedPaper] = Field(default_factory=list)
    excluded_papers: List[ScreenedPaper] = Field(default_factory=list)
    uncertain_papers: List[ScreenedPaper] = Field(default_factory=list)
