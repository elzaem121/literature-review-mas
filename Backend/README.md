# Backend

## Overview

FastAPI service that bridges the Streamlit frontend and the LangGraph pipeline in
[Orchestration](../Orchestration/README.md). A client starts a run with one POST, receives a
`job_id` immediately, and polls a GET endpoint while the pipeline runs as a FastAPI background task.
Run state lives in a module-level in-memory dictionary.

## Interface

- `Backend/main.py:app` — `FastAPI(title="MAS Literature Review API", version="2.0.0")`; the ASGI target
  (`uvicorn Backend.main:app`).
- `POST /start_pipeline` (`start_pipeline`) — body `ResearchRequest`; creates a UUID `job_id`, seeds
  `JOBS[job_id]`, schedules `run_graph_in_background`, returns
  `{"job_id", "status_message"}`.
- `GET /status/{job_id}` (`get_status`) — `response_model=ResearchResponse`; HTTP 404 when the `job_id` is
  not in `JOBS`.
- `GET /` (`read_root`) — health-check message.
- `Backend/main.py:run_graph_in_background(job_id, initial_state)` — iterates
  `workflow_app.astream(initial_state)` and copies per-node state into `JOBS[job_id]`.
- `Backend/main.py:JOBS` — `Dict[str, Dict[str, Any]]`, the job registry.
- `Backend/schemas.py` — Pydantic models:
  - `ResearchRequest` (`research_question` required; `min_year=2020`, `inclusion_criteria`,
    `exclusion_criteria`, `additional_info`, `target_output_count=25`).
  - `ScreeningResults` (`included_papers`, `excluded_papers`, `uncertain_papers`, `failed_papers`, each
    `List[Dict[str, Any]]`).
  - `ResearchResponse` (`current_step`, `status_message`, `raw_papers_count`, `screening_results`,
    `extracted_papers`, `final_analysis`).

## Invariants

- `JOBS` is process-local and unpersisted: a restart (or `--reload`) drops every job, and a poll for a
  lost job returns 404 `"Job not found. It might have expired."` (`Backend/main.py:get_status`).
- The `initial_state` built in `start_pipeline` must contain exactly the input fields of
  `Orchestration.state.PipelineState`; the keys are mapped by hand from `ResearchRequest`.
- A job reaches a terminal state only via `current_step == "completed"` (set by the extraction node) or
  `"error"` (set in the `except` block of `run_graph_in_background`). The frontend relies on these two
  strings.
- `final_analysis` is initialised to `None` and copied through if a node ever emits it, but no node in
  the graph currently sets it (`Backend/schemas.py:ResearchResponse.final_analysis` is described as reserved).
- Per-node updates are read as `step_result[list(step_result.keys())[0]]`, i.e. the code assumes each
  `astream` chunk contains exactly one node.
- `Backend/__init__.py` is empty; `Backend` is imported as a package from the repo root.

## Side Effects

- Mutates the module-level `JOBS` dictionary from a background task.
- Executes the whole pipeline in-process, which triggers the network and disk effects of every stage
  (OpenAlex HTTP calls, LLM calls to the Ollama endpoint, PDF downloads into `pdfs_auto/`).
- Wraps each run in `tracing.root_trace(job_id)`, which emits a LangSmith trace only when
  `LANGSMITH_API_KEY` is set.
- Exceptions inside the pipeline are swallowed into `JOBS[job_id]` (`current_step="error"`,
  `status_message="Pipeline failed: ..."`) rather than raised.

## Verification

- No tests exist for this package. Smoke test: `uvicorn Backend.main:app --reload` from the repo root, then
  `curl http://127.0.0.1:8000/`.
