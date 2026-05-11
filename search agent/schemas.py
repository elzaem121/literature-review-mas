from pydantic import BaseModel, Field
from typing import List, Optional

class SearchQuery(BaseModel):
    """
    Schema for capturing the LLM-generated expanded search queries.
    This guarantees the model returns a clean list of strings.
    """
    queries: List[str] = Field(..., description="List of 3 to 5 expanded academic search queries.")

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