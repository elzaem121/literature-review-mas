from typing import Any, Dict, List, Optional, TypedDict


class PipelineState(TypedDict):
    """
    The shared state for the LangGraph pipeline.
    This acts as the central data storage that passes through all agents.
    """

    # ---------------------------------------------------------
    # 1. INPUTS (From Streamlit via FastAPI)
    # ---------------------------------------------------------
    research_question: str
    min_year: Optional[int]
    inclusion_criteria: Optional[List[str]]
    exclusion_criteria: Optional[List[str]]
    additional_info: Optional[str]
    target_output_count: int

    # ---------------------------------------------------------
    # 2. OUTPUTS (Populated by Agents)
    # ---------------------------------------------------------
    # Filled by SearchAgent
    raw_papers: List[Dict[str, Any]]

    # Filled by Screening Agent (Contains the 4 lists: included, excluded, uncertain, failed)
    screening_results: Dict[str, Any]

    # Filled by Extraction Agent
    extracted_papers: List[Dict[str, Any]]

    # ---------------------------------------------------------
    # 3. UI TRACKING (For Streamlit Progress Bar / Status)
    # ---------------------------------------------------------
    current_step: (
        str  # e.g., "search", "screening", "document_processing", "extraction", "completed"
    )
    status_message: str  # e.g., "Searching OpenAlex for semantic matches..."
