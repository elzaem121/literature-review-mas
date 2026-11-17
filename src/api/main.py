import uuid
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, HTTPException

# Import the request and response schemas
from src.api.schemas import ResearchRequest, ResearchResponse, ScreeningResults

# Import the compiled LangGraph workflow
from src.graph.graph import app as workflow_app
from src.llm.settings import get_settings
from src.llm.tracing import root_trace

# Fail at startup, not mid-run, when required settings (e.g. OPENALEX_EMAIL) are missing
get_settings()

# Initialize the FastAPI application
app = FastAPI(
    title="MAS Literature Review API",
    description="API bridging Streamlit and the LangGraph Multi-Agent System asynchronously",
    version="2.0.0",
)

# ---------------------------------------------------------
# 💾 IN-MEMORY JOB STORAGE
# ---------------------------------------------------------
# Here we store the live status of each pipeline run.
# In a real production app, this would be Redis or a Database.
JOBS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------
# ⚙️ BACKGROUND TASK ENGINE
# ---------------------------------------------------------
async def run_graph_in_background(job_id: str, initial_state: dict):
    """
    This function runs independently in the background.
    It uses astream() to capture the state AFTER EVERY AGENT finishes.
    """
    try:
        # workflow_app.astream() yields the state step-by-step!
        async with root_trace(job_id):
            async for step_result in workflow_app.astream(initial_state):
                # Extract the node name (e.g., 'search_agent', 'screening_agent')
                node_name = list(step_result.keys())[0]
                latest_state = step_result[node_name]

                # Update our global job tracker with the latest progression
                JOBS[job_id]["current_step"] = latest_state.get(
                    "current_step", JOBS[job_id]["current_step"]
                )
                JOBS[job_id]["status_message"] = latest_state.get(
                    "status_message", JOBS[job_id]["status_message"]
                )

                # If new data is generated, save it to the job tracker
                if "raw_papers" in latest_state:
                    JOBS[job_id]["raw_papers_count"] = len(latest_state["raw_papers"])
                if "screening_results" in latest_state:
                    JOBS[job_id]["screening_results"] = latest_state["screening_results"]
                if "extracted_papers" in latest_state:
                    JOBS[job_id]["extracted_papers"] = latest_state["extracted_papers"]
                if "final_analysis" in latest_state:
                    JOBS[job_id]["final_analysis"] = latest_state["final_analysis"]

    except Exception as e:
        JOBS[job_id]["current_step"] = "error"
        JOBS[job_id]["status_message"] = f"Pipeline failed: {str(e)}"


# ---------------------------------------------------------
# 🚀 ENDPOINT 1: START THE PIPELINE
# ---------------------------------------------------------
@app.post("/start_pipeline")
async def start_pipeline(request: ResearchRequest, background_tasks: BackgroundTasks):
    """
    Receives the request, creates a Job ID, hands the work to the background,
    and IMMEDIATELY returns the Job ID to Streamlit.
    """
    job_id = str(uuid.uuid4())

    # Initialize the job safely
    JOBS[job_id] = {
        "current_step": "initialized",
        "status_message": "Pipeline initialized, adding to background tasks...",
        "raw_papers_count": 0,
        "screening_results": None,
        "extracted_papers": None,
        "final_analysis": None,
    }

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
    background_tasks.add_task(run_graph_in_background, job_id, initial_state)

    return {"job_id": job_id, "status_message": "Pipeline started in background"}


# ---------------------------------------------------------
# 📡 ENDPOINT 2: POLL FOR STATUS
# ---------------------------------------------------------
@app.get("/status/{job_id}", response_model=ResearchResponse)
async def get_status(job_id: str):
    """
    Streamlit will hit this endpoint every second to get live updates.
    """
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found. It might have expired.")

    job_data = JOBS[job_id]

    # Safely map the raw dictionary back to our Pydantic schema
    screening_obj = None
    if job_data.get("screening_results"):
        sd = job_data["screening_results"]
        screening_obj = ScreeningResults(
            included_papers=sd.get("included_papers", []),
            excluded_papers=sd.get("excluded_papers", []),
            uncertain_papers=sd.get("uncertain_papers", []),
            failed_papers=sd.get("failed_papers", []),
        )

    return ResearchResponse(
        current_step=job_data["current_step"],
        status_message=job_data["status_message"],
        raw_papers_count=job_data.get("raw_papers_count", 0),
        screening_results=screening_obj,
        extracted_papers=job_data.get("extracted_papers"),
        final_analysis=job_data.get("final_analysis"),
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check for the compose and CI health probe."""
    return {"status": "ok"}


# Root endpoint
@app.get("/")
def read_root():
    return {"message": "MAS Literature Review API is running in Async Mode!"}
