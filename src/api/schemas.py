from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    research_question: str = Field(..., description="The main research question")
    min_year: int = Field(default=2020, description="Minimum publication year")
    inclusion_criteria: List[str] = Field(
        default_factory=list, description="Criteria for accepting papers"
    )
    exclusion_criteria: List[str] = Field(
        default_factory=list, description="Criteria for rejecting papers"
    )
    additional_info: Optional[str] = Field(
        default=None, description="Any extra instructions (e.g., be conservative)"
    )
    target_output_count: int = Field(
        default=25, description="Number of papers to retrieve in search stage"
    )


class ScreeningResults(BaseModel):
    included_papers: List[Dict[str, Any]] = Field(default_factory=list)
    excluded_papers: List[Dict[str, Any]] = Field(default_factory=list)
    uncertain_papers: List[Dict[str, Any]] = Field(default_factory=list)
    failed_papers: List[Dict[str, Any]] = Field(default_factory=list)


class ResearchResponse(BaseModel):
    current_step: str = Field(..., description="e.g., 'search', 'screening', 'completed', 'error'")
    status_message: str = Field(..., description="Human-readable status for the UI spinner")
    raw_papers_count: int = Field(default=0, description="Number of papers found by Search Agent")
    screening_results: Optional[ScreeningResults] = Field(
        default=None, description="Categorized papers from Screening Agent"
    )
    extracted_papers: Optional[List[Dict[str, Any]]] = Field(default=None)
    provenance: Optional[Dict[str, Any]] = Field(
        default=None, description="Models, prompt versions and profile the run started with"
    )
    final_analysis: Optional[Any] = Field(
        default=None, description="Reserved for the Extraction Agent's final synthesis report"
    )
