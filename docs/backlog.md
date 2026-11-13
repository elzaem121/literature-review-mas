# Backlog

Findings from the EGM bootstrap (2026-11-10, items 1-6) and deferred ideas (from 2026-11-13, items 7 onward). No code has been changed for these yet.

> Phases refer to `docs/plan_v2.md` (section 10).

| # | Finding | Where | Status | Phase (plan_v2) |
|---|---|---|---|---|
| 1 | Screening tests are broken: 3 of 11 fail. Two need `Screening_Agent/review_config.json`, but the checked-in fixture is `Screening_Agent/testdaten/review_config.json`. The third fails because the tests import `screening_schemas` flat while `screening_agent.py` imports `Screening_Agent.screening_schemas`, so Pydantic sees two different `ResearchPaper` classes. Collection also fails without `PYTHONPATH=..`. | `Screening_Agent/test_screening.py`, `Screening_Agent/screening_agent.py` | Open | Phase 1: fix the fixture path and the imports with the new package layout |
| 2 | `search_agent/archiv/app.py` imports `AcademicSearchAgent`, which no longer exists (the class is `UniversalAcademicSearchAgent`), so it cannot run. Nothing imports it. | `search_agent/archiv/app.py` | Open | Phase 1 |
| 3 | `extract_agent/rag_extraction_main.py` has no script entry point (its `INPUT_FILE`/`OUTPUT_FILE` lines are commented out), yet `extract_agent/README.md` still lists `python rag_extraction_main.py` as a step and names "Qwen3" (code default is `qwen2.5-coder:7b`). | `extract_agent/rag_extraction_main.py`, `extract_agent/README.md` | Open | Phase 1 |
| 4 | `CLAUDE.md` described the two Streamlit apps the wrong way round (`ui_app.py` is the backend-polling frontend; `App_Main/streamlit-app.py` is the in-process HITL app with mock fallback). | `CLAUDE.md` | Fixed; `CLAUDE.md` is now tracked (removed from `.gitignore`), commit pending | n/a |
| 5 | `search_agent/new_main.py` falls back to a hard-coded OpenAlex contact email when `OPENALEX_EMAIL` is unset. | `search_agent/new_main.py` | Open | Phase 1: move to settings/env |
| 6 | Update model references in READMEs after the model benchmark. The contracts and READMEs state `qwen2.5-coder:7b` as the default; plan_v2 section 7 keeps the v1 models through Phase 1 and switches only after the Phase 2a benchmark. | `README.md`, `CLAUDE.md`, `Orchestration/README.md`, `Screening_Agent/README.md`, `search_agent/README.md`, `extract_agent/README.md`, `App_Main/README.md`, `deploy/NOTES.md` | Open | Phase 2a, after the model benchmark |
| 7 | Domain disambiguation: run a quick OpenAlex search, count `primary_topic.subfield`, and if results are mixed, let the user pick a subfield with example titles; then filter the search by it. | search, chat UI | Moved to plan_v2 (2026-11-13): section 5.2 step 4, Phase 2b filter, Phase 3 Should | Phase 2b search / Phase 3 UI |
| 8 | Multi-user and authentication: private reviews and chats per user, ownership checks on every `thread_id` and `review_id` endpoint, reassign rows created under the seeded `local` user. Removed from plan_v2 (single user until v1.0). | API, data model | Deferred | after v1.0 |
| 9 | Re-extraction queue: re-run extraction for `missing` fields when the model or prompt version changes. | extraction | Deferred | after Phase 2b |
| 10 | Replay recorded model responses in CI (keyed by model, prompt version and input) to test the eval harness and scoring without live models. | eval, CI | Deferred | after Phase 2a |
| 11 | Prompt-injection handling for paper text that goes into prompts and into shared extractions. | screening, extraction | Deferred | before multi-user (#8) |
| 12 | Reuse library papers before searching OpenAlex: retrieve candidates from the library and screen them for the new review first. | pipeline | Deferred | after v1.0 |
| 13 | Screening history and PRISMA counts: keep screening decisions across re-runs and count papers per stage (year prefilter, each search iteration). | data model, screening log | Deferred | after v1.0 |
| 14 | Bootstrap docs are wrong in two places: `CLAUDE.md` lists `extract_agent.py`, `extraction_agent.py` and `extraction_main.py`, which do not exist; `README.md:240-241` says `SCREENING_MODEL` overrides the screening model, but `Orchestration/nodes.py:62` hardcodes it. | `CLAUDE.md`, `README.md` | Open | Phase 1 |
