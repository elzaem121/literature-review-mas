# App_Main

## Overview

`streamlit-app.py` is a standalone Streamlit "HITL Orchestrator" that runs the **search** and
**screening** stages directly in the Streamlit process (no FastAPI backend, no LangGraph) and inserts a
human-in-the-loop review step: the reviewer can edit the screening decisions in a data editor before a
countdown (`HITL_TIMEOUT_SECONDS`, default 60 s) auto-submits the original selection. It stops at
"ready for next phase"; document processing and extraction are not part of this app. The FastAPI-backed
UI that runs the full pipeline is the root-level [ui_app.py](../README.md#local-interface--invariants).
Startup notes (German) are in [App_Main_ReadMe.md](./App_Main_ReadMe.md).

## Interface

- `streamlit-app.py:main()` — page entry; dispatches on `AppState` to the `render_*` functions
  (`render_idle`, `render_search_running`, `render_screening_running`, `render_hitl_review`,
  `render_after_hitl`, `render_ready_for_next_phase`, `render_error`).
- State machine: `AppState` (`idle → search_running → screening_running → hitl_review → hitl_submitted →
  ready_for_next_phase → done`, plus `error`), `HitlSubmitSource` (`user_confirmed`,
  `timeout_original_selection`), `HitlPhaseConfig`/`SCREENING_HITL`, `UiInput` (with
  `to_review_protocol()`).
- Adapters: `SearchAgentAdapter(entrypoint=$SEARCH_AGENT_ENTRYPOINT or "search_agent.new_main:main")`
  (tries three call signatures in turn, normalises the result via `normalize_search_output`) and
  `ScreeningAgentAdapter(model_name=$SCREENING_MODEL or "qwen2.5-coder:7b")`.
- Mocks: `mock_search_agent_main`, `mock_screening_agent_main`; an empty search entrypoint selects the mock
  search agent.
- Helpers: `import_callable("module:function")`, `await_if_needed`, `flatten_screening_output`,
  `rebuild_screening_output_from_rows`, `persist_json`, `split_criteria`, `reset_pipeline`.
- Config env vars: `HITL_TIMEOUT_SECONDS`, `SEARCH_AGENT_ENTRYPOINT`, `SCREENING_MODEL`, `MAS_OUTPUT_DIR`
  (default `.mas_runs`).

## Invariants

- The file name `streamlit-app.py` contains a hyphen, so it is run as a script
  (`streamlit run ./App_Main/streamlit-app.py`), never imported as a module.
- Screening classes are imported from `Screening_Agent.screening_agent` / `.screening_schemas` inside a
  `try/except Exception`; on any failure `REAL_SCREENING_AVAILABLE` is `False` and local mock schemas and
  the mock screening agent silently replace them. A green UI run therefore does not prove the real agent
  was used. `Screening_Agent` resolves only when the repo root is on `sys.path`; the documented
  `python -m streamlit` launch from the repo root provides that through the current directory.
- HITL submission is idempotent: `submit_current_hitl` returns immediately when `submitted_at` is already
  set. The timer fragment relies on `st.fragment(run_every=1)`, with a warning when it is unavailable.
- Streamlit session state keys are initialised only through `init_state` (`app_state`, `ui_input`,
  `search_output`, `screening_output`, `validated_screening_output`, `active_hitl`, `last_error`,
  `phase_run_id`, `pipeline_log`).

## Side Effects

- Creates the directory `MAS_OUTPUT_DIR` (default `.mas_runs/`) at import time and writes
  `search_results.json`, `screening_results_agent_raw.json` and `validated_screening_results.json` there.
- Invokes the search agent (LLM + OpenAlex HTTP) and screening agent (LLM) in the Streamlit process; async
  agents are run with `asyncio.run` (or a worker thread when a loop is already running).
- Offers an `st.download_button` for the validated screening JSON. The "Extract Agent" step is only a
  documented extension point (`render_ready_for_next_phase`), not implemented.

## Verification

- No tests. Manual: `PYTHONPATH="$PWD/Screening_Agent:$PWD/App_Main" python -m streamlit run ./App_Main/streamlit-app.py`
  from the repo root (needs Ollama for real screening; with the real agents unavailable it runs on mocks).
