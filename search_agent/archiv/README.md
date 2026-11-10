# search_agent/archiv

## Overview

Archived, non-functional Streamlit front end for an earlier version of the search agent. It is not
imported by the pipeline, and it cannot run as-is: it imports a class that no longer exists. Kept for
reference only; the live entry point is [search_agent](../README.md) (`new_main.py`).

## Interface

- `app.py` — top-level Streamlit script (no functions). It reads a research question and minimum year
  from the sidebar and calls `AcademicSearchAgent(model_name="qwen2.5-coder:7b").run_pipeline(
  user_query=..., min_year=...)` via `asyncio.run`, then renders the results with `pandas`.

## Invariants

- `app.py` does `from agent import AcademicSearchAgent`, but `search_agent/agent.py` now only defines
  `UniversalAcademicSearchAgent` (with `run_precise_retrieval_cycle`, no `run_pipeline`), so the script
  raises `ImportError` today.
- No other module imports from this directory.

## Side Effects

- None at import time apart from Streamlit page configuration (`st.set_page_config`).
- When executed it would call the local LLM and OpenAlex through the agent it imports.

## Verification

- No tests. Do not use this script to verify changes to the search stage.
