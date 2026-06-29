import asyncio
from typing import Dict, Any

from Orchestration.state import PipelineState
from search_agent.new_main import main as run_search
from Screening_Agent.screening_agent import AcademicScreeningAgent
from Screening_Agent.screening_schemas import ResearchPaper

# 1. IMPORT FIX: Import the actual extraction node we created earlier
# (Note: Ensure the file name matches your actual file structure, e.g., rag_extraction_main)
from extract_agent.rag_extraction_main import extraction_node

# ==========================================
# 🟢 LIVE STATUS NODES (Fast Nodes)
# ==========================================
def pre_search_node(state: PipelineState) -> PipelineState:
    state["current_step"] = "search"
    state["status_message"] = "🕵️ [LIVE] Search Agent is running: Querying OpenAlex..."
    return state


def pre_screening_node(state: PipelineState) -> PipelineState:
    state["current_step"] = "screening"
    state["status_message"] = "⚖️ [LIVE] Screening Agent is running: Analyzing papers against criteria..."
    return state


def pre_document_processing_node(state: PipelineState) -> PipelineState:
    state["current_step"] = "document_processing"
    state["status_message"] = "📄 [LIVE] Document Processing is running: Downloading PDFs and preparing RAG chunks..."
    return state


def pre_extraction_node(state: PipelineState) -> PipelineState:
    state["current_step"] = "extraction"
    state["status_message"] = "📝 [LIVE] Extraction Agent is running: Extracting key data..."
    return state


# ==========================================
# 🔴 HEAVY WORKER NODES (Slow Nodes)
# ==========================================
def search_node(state: PipelineState) -> PipelineState:
    # This takes ~5-10 seconds
    search_results = run_search(
        research_question=state.get("research_question"),
        min_year=state.get("min_year"),
        inclusion_criteria=state.get("inclusion_criteria"),
        exclusion_criteria=state.get("exclusion_criteria"),
        additional_info=state.get("additional_info"),
        target_output_count=state.get("target_output_count", 25)
    )
    state["raw_papers"] = search_results.get("papers", [])
    return state


async def screening_node(state: PipelineState) -> PipelineState:
    # This takes ~40 seconds
    agent = AcademicScreeningAgent(model_name="qwen2.5-coder:7b", max_concurrent_tasks=3)
    raw_papers_list = state.get("raw_papers", [])
    papers_objects = [ResearchPaper(**paper_dict) for paper_dict in raw_papers_list]

    inc_criteria = "\n".join([f"- {i}" for i in state.get("inclusion_criteria") or []]) or "None specified."
    exc_criteria = "\n".join([f"- {i}" for i in state.get("exclusion_criteria") or []]) or "None specified."

    result = await agent.screen_papers(
        papers=papers_objects,
        research_question=state.get("research_question"),
        inclusion_criteria=inc_criteria,
        exclusion_criteria=exc_criteria,
        additional_instructions=state.get("additional_info"),
        pre_excluded=[]
    )

    state["screening_results"] = {
        "included_papers": [p.model_dump() for p in result.included_papers],
        "excluded_papers": [p.model_dump() for p in result.excluded_papers],
        "uncertain_papers": [p.model_dump() for p in result.uncertain_papers],
        "failed_papers": [p.model_dump() for p in result.failed_papers],
    }
    return state

# 2. REMOVAL FIX: The placeholder extraction_node has been deleted from here,
# since we are now importing the real one from its own file above.
