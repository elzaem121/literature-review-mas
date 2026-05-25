from pydantic import BaseModel, Field
from typing import List, Optional


class FrameworkAnalysis(BaseModel):
    """
    Captures the breakdown of the research topic based on the selected framework.
    All fields are Optional to prevent Validation Errors when the LLM switches frameworks.
    """
    # PICO Framework (Medical/Clinical)
    population: Optional[List[str]] = Field(default=[], description="Target population terms")
    intervention: Optional[List[str]] = Field(default=[], description="Intervention terms")
    comparison: Optional[List[str]] = Field(default=[], description="Comparison terms")
    outcome: Optional[List[str]] = Field(default=[], description="Outcome terms")

    # PECO Framework (CS/Engineering)
    problem: Optional[List[str]] = Field(default=[], description="Target problem terms")
    environment: Optional[List[str]] = Field(default=[], description="Environment or setting terms")

    # PCC Framework (Social Sciences)
    concept: Optional[List[str]] = Field(default=[], description="Core concept terms")
    context: Optional[List[str]] = Field(default=[], description="Context or setting terms")

    # FREE Framework (Humanities/History)
    free_terms: Optional[List[str]] = Field(default=[],
                                            description="Free keywords for humanities without strict framework")


class SearchQuery(BaseModel):
    """
    Schema for capturing the LLM-generated search strategy.
    Incorporates the dynamic framework analysis and the final Boolean queries.
    """
    framework_used: str = Field(..., description="The analytical framework chosen: PICO, PECO, PCC, or FREE.")
    analysis: FrameworkAnalysis = Field(..., description="The conceptual breakdown of the research topic.")
    queries: List[str] = Field(...,
                               description="List of exactly 8 highly precise Boolean search strings (6 strict, 2 broader).")


class ResearchPaper(BaseModel):
    """
    Strict schema representing a single research paper.
    This precise structure is mandatory for the downstream Screening Agent.
    """
    title: str = Field(..., description="The official title of the research paper.")
    abstract: str = Field(..., description="Full abstract of the paper. Use 'No abstract available' if missing.")
    year: int = Field(..., description="The four-digit publication year.")
    authors: List[str] = Field(..., description="List of author names.")
    doi: Optional[str] = Field(None, description="The Digital Object Identifier URL, e.g., https://doi.org/10...")
    url: Optional[str] = Field(None, description="Direct URL to the paper's landing page or PDF.")
    relevance_score: int = Field(..., description="Assessed relevance score ranging from 1 to 10.")


class ScreenedPapers(BaseModel):
    """
    Schema for the final output array containing all processed papers.
    """
    papers: List[ResearchPaper] = Field(..., description="Array of rigorously evaluated and ranked research papers.")