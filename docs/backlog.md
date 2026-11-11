# Backlog

Findings from the EGM bootstrap (2026-11-10). No code has been changed for these yet.

> Phases refer to `docs/plan_v2.md` (section 10).

| # | Finding | Where | Status | Phase (plan_v2) |
|---|---|---|---|---|
| 1 | Screening tests are broken: 3 of 11 fail. Two need `Screening_Agent/review_config.json`, but the checked-in fixture is `Screening_Agent/testdaten/review_config.json`. The third fails because the tests import `screening_schemas` flat while `screening_agent.py` imports `Screening_Agent.screening_schemas`, so Pydantic sees two different `ResearchPaper` classes. Collection also fails without `PYTHONPATH=..`. | `Screening_Agent/test_screening.py`, `Screening_Agent/screening_agent.py` | Open | Phase 1: fix the fixture path and the imports with the new package layout |
| 2 | `search_agent/archiv/app.py` imports `AcademicSearchAgent`, which no longer exists (the class is `UniversalAcademicSearchAgent`), so it cannot run. Nothing imports it. | `search_agent/archiv/app.py` | Open | Phase 1 |
| 3 | `extract_agent/rag_extraction_main.py` has no script entry point (its `INPUT_FILE`/`OUTPUT_FILE` lines are commented out), yet `extract_agent/README.md` still lists `python rag_extraction_main.py` as a step and names "Qwen3" (code default is `qwen2.5-coder:7b`). | `extract_agent/rag_extraction_main.py`, `extract_agent/README.md` | Open | Phase 1 |
| 4 | `CLAUDE.md` described the two Streamlit apps the wrong way round (`ui_app.py` is the backend-polling frontend; `App_Main/streamlit-app.py` is the in-process HITL app with mock fallback). | `CLAUDE.md` | Fixed; `CLAUDE.md` is now tracked (removed from `.gitignore`), commit pending | n/a |
| 5 | `search_agent/new_main.py` falls back to a hard-coded OpenAlex contact email when `OPENALEX_EMAIL` is unset. | `search_agent/new_main.py` | Open | Phase 1: move to settings/env |
| 6 | Update model references in READMEs after the model benchmark. The contracts and READMEs state `qwen2.5-coder:7b` as the default; plan_v2 section 7 says the default will be a general instruct model chosen after the Phase 2 benchmark (provisional default until then: `qwen3:8b`). | `README.md`, `CLAUDE.md`, `Orchestration/README.md`, `Screening_Agent/README.md`, `search_agent/README.md`, `extract_agent/README.md`, `App_Main/README.md`, `deploy/NOTES.md` | Open | Phase 2, after the model benchmark |
