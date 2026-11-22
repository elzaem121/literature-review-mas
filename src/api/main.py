import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException

from src.api.schemas import ResearchRequest, ResearchResponse, ScreeningResults
from src.db.models import Run
from src.db.repository import get_repository
from src.graph.graph import app as workflow_app
from src.llm.prompts import extraction as extraction_prompts
from src.llm.prompts import screening as screening_prompts
from src.llm.prompts import search as search_prompts
from src.llm.settings import get_settings
from src.llm.tracing import root_trace

# Fail at startup, not mid-run, when required settings (e.g. OPENALEX_EMAIL) are missing
get_settings()

INTERRUPTED_MESSAGE = "This run was interrupted by a restart. Please start a new run."


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """On process start, mark runs that were still unfinished (their process died) interrupted."""
    await asyncio.to_thread(get_repository().mark_unfinished_interrupted)
    yield


# Initialize the FastAPI application
app = FastAPI(
    title="MAS Literature Review API",
    description="API bridging Streamlit and the LangGraph Multi-Agent System asynchronously",
    version="2.0.0",
    lifespan=lifespan,
)


def build_provenance() -> dict[str, Any]:
    """Describe the models, prompt versions and profile a run starts with, from the settings."""
    settings = get_settings()
    return {
        "models": {
            "search": settings.search_model,
            "screening": settings.screening_model,
            "extraction": settings.extraction_model,
        },
        "prompt_versions": {
            "search": search_prompts.PROMPT_VERSION,
            "screening": screening_prompts.PROMPT_VERSION,
            "extraction": extraction_prompts.PROMPT_VERSION,
        },
        "profile": settings.profile,
    }


def build_payload(latest_state: dict[str, Any]) -> dict[str, Any]:
    """Pick the result fields a graph step produced, as v1 stored them per step."""
    payload: dict[str, Any] = {}
    if "raw_papers" in latest_state:
        payload["raw_papers_count"] = len(latest_state["raw_papers"])
    for field in ("screening_results", "extracted_papers", "final_analysis"):
        if field in latest_state:
            payload[field] = latest_state[field]
    return payload


# ---------------------------------------------------------
# ⚙️ BACKGROUND TASK ENGINE
# ---------------------------------------------------------
async def run_graph_in_background(run_id: uuid.UUID, initial_state: dict):
    """
    This function runs independently in the background.
    It uses astream() to capture the state AFTER EVERY AGENT finishes.
    """
    repository = get_repository()
    status_message = initial_state["status_message"]
    try:
        await asyncio.to_thread(repository.start_run, run_id)
        # workflow_app.astream() yields the state step-by-step!
        async with root_trace(str(run_id)):
            async for step_result in workflow_app.astream(initial_state):
                # Extract the node name (e.g., 'search_agent', 'screening_agent')
                node_name = list(step_result.keys())[0]
                latest_state = step_result[node_name]
                status_message = latest_state.get("status_message", status_message)

                # Persist the latest progression and any new data on the run row
                await asyncio.to_thread(
                    repository.update_run_step,
                    run_id,
                    latest_state.get("current_step", "initialized"),
                    status_message,
                    build_payload(latest_state),
                )
        await asyncio.to_thread(repository.finish_run, run_id, "completed", status_message)
    except Exception as e:
        await asyncio.to_thread(repository.finish_run, run_id, "failed", f"Pipeline failed: {e}")


def parse_job_id(job_id: str) -> uuid.UUID | None:
    """Return the run id for a job id string, or None if it is not a UUID (so no run has it)."""
    try:
        return uuid.UUID(job_id)
    except ValueError:
        return None


def compose_status(run: Run) -> ResearchResponse:
    """Build v1's `ResearchResponse` from a stored run (the status mapping of the design)."""
    current_step, status_message = run.current_step, run.status_message
    if run.status == "completed":
        current_step = "completed"
    elif run.status == "failed":
        current_step = "error"
    elif run.status == "interrupted":
        current_step, status_message = "interrupted", INTERRUPTED_MESSAGE

    screening_obj = None
    if run.result.get("screening_results"):
        sd = run.result["screening_results"]
        screening_obj = ScreeningResults(
            included_papers=sd.get("included_papers", []),
            excluded_papers=sd.get("excluded_papers", []),
            uncertain_papers=sd.get("uncertain_papers", []),
            failed_papers=sd.get("failed_papers", []),
        )

    return ResearchResponse(
        current_step=current_step,
        status_message=status_message,
        raw_papers_count=run.result.get("raw_papers_count", 0),
        screening_results=screening_obj,
        extracted_papers=run.result.get("extracted_papers"),
        provenance=run.result.get("provenance"),
        final_analysis=run.result.get("final_analysis"),
    )


# ---------------------------------------------------------
# 🚀 ENDPOINT 1: START THE PIPELINE
# ---------------------------------------------------------
@app.post("/start_pipeline")
async def start_pipeline(request: ResearchRequest, background_tasks: BackgroundTasks):
    """
    Receives the request, stores a review and a run (the run id is the Job ID), hands the work
    to the background, and IMMEDIATELY returns the Job ID to Streamlit.
    """
    criteria = {
        "inclusion": request.inclusion_criteria,
        "exclusion": request.exclusion_criteria,
        "min_year": request.min_year,
        "target_output_count": request.target_output_count,
        "additional_info": request.additional_info,
    }
    run_id = await asyncio.to_thread(
        get_repository().create_run, request.research_question, criteria, build_provenance()
    )

    initial_state = {
        "research_question": request.research_question,
        "min_year": request.min_year,
        "inclusion_criteria": request.inclusion_criteria,
        "exclusion_criteria": request.exclusion_criteria,
        "additional_info": request.additional_info,
        "target_output_count": request.target_output_count,
        "current_step": "initialized",
        "status_message": "Starting search...",
    }

    # Send the heavy lifting to the background
    background_tasks.add_task(run_graph_in_background, run_id, initial_state)

    return {"job_id": str(run_id), "status_message": "Pipeline started in background"}


# ---------------------------------------------------------
# 📡 ENDPOINT 2: POLL FOR STATUS
# ---------------------------------------------------------
@app.get("/status/{job_id}", response_model=ResearchResponse)
async def get_status(job_id: str):
    """
    Streamlit will hit this endpoint every second to get live updates.
    """
    run_id = parse_job_id(job_id)
    run = await asyncio.to_thread(get_repository().get_run, run_id) if run_id else None
    if run is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return compose_status(run)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check for the compose and CI health probe."""
    return {"status": "ok"}


# Root endpoint
@app.get("/")
def read_root():
    return {"message": "MAS Literature Review API is running in Async Mode!"}
