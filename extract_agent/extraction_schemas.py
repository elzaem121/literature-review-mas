from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ExtractionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchPaper(BaseModel):
    title: str = Field(..., description="Official title of the paper.")
    abstract: str = Field(default="No abstract available.", description="Paper abstract or fallback text.")
    full_text: Optional[str] = Field(None, description="Full text extracted from a PDF if available.")
    year: Optional[int] = Field(None, description="Publication year.")
    authors: List[str] = Field(default_factory=list, description="Author names.")
    doi: Optional[str] = Field(None, description="Digital Object Identifier URL.")
    url: Optional[str] = Field(None, description="Landing page or PDF URL.")
    relevance_score: Optional[int] = Field(None, description="Optional score from previous agents.")


class ScreeningAgentOutput(BaseModel):
    papers: List[ResearchPaper] = Field(default_factory=list)


class ExtractedPaperInfo(BaseModel):
    paper_type: str = Field(
        ...,
        description="Type of the paper, e.g. empirical study, literature review, conceptual paper, theoretical discussion, case study, or mixed-methods study."
    )
    method: str = Field(
        ...,
        description="Research method or study type used in the paper."
    )
    dataset: str = Field(
        ...,
        description="Dataset, data source, participants, corpus, or study material used in the paper. If no empirical dataset exists, write 'no empirical dataset'."
    )
    task: str = Field(
        ...,
        description="Main research task or analytical focus of the paper."
    )
    main_findings: str = Field(
        ...,
        description="Most important findings based only on the provided text."
    )
    limitations: str = Field(
        ...,
        description="Limitations explicitly mentioned in the provided text. If none are stated, write 'not explicitly specified'."
    )
    relevance_to_research_question: str = Field(
        ...,
        description="How the paper relates to the research question."
    )
    confidence: ExtractionConfidence = Field(
        ...,
        description="Confidence level of the extraction."
    )


class ExtractedPaper(BaseModel):
    paper: ResearchPaper
    extraction: ExtractedPaperInfo


class ExtractionOutput(BaseModel):
    extracted_papers: List[ExtractedPaper] = Field(default_factory=list)