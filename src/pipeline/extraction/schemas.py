from enum import Enum

from pydantic import BaseModel, Field


class ExtractionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExtractedPaperInfo(BaseModel):
    paper_type: str = Field(
        ...,
        description="Type of the paper, e.g. empirical study, literature review, conceptual paper, theoretical discussion, case study, or mixed-methods study.",
    )
    method: str = Field(..., description="Research method or study type used in the paper.")
    dataset: str = Field(
        ...,
        description="Dataset, data source, participants, corpus, or study material used in the paper. If no empirical dataset exists, write 'no empirical dataset'.",
    )
    task: str = Field(..., description="Main research task or analytical focus of the paper.")
    main_findings: str = Field(
        ..., description="Most important findings based only on the provided text."
    )
    limitations: str = Field(
        ...,
        description="Limitations explicitly mentioned in the provided text. If none are stated, write 'not explicitly specified'.",
    )
    relevance_to_research_question: str = Field(
        ..., description="How the paper relates to the research question."
    )
    confidence: ExtractionConfidence = Field(..., description="Confidence level of the extraction.")
