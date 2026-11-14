# Backlog

Findings from the EGM bootstrap (2026-11-10, items 1-6), deferred ideas (from 2026-11-13, items 7-14), and plan-level candidates from the Phase 1 brainstorm Goldfish review (2026-11-14, `docs/reviews/phase1_brainstorm_goldfish.md`, items 15-31). No code has been changed for these yet.

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
| 15 | Migrate the OpenAlex client from `requests` to async `httpx` once the Phase 1 behaviour freeze lifts; removes the `asyncio.to_thread` wrapper around search. | search | Deferred | Phase 2b or later |
| 16 | Record raw OpenAlex responses as versioned fixtures/cassettes so search evals replay against a fixed API snapshot (complements #10, which covers model responses). | eval, search | Deferred | Phase 2a |
| 17 | Structured JSON logging has no owning phase: plan section 5.1 lists it as cross-cutting, but v1 is `print()` throughout and no phase checklist owns the switch. | cross-cutting | Open | assign in a phase design |
| 18 | Retention/cleanup for `runs.result` jsonb once Phase 2b's `screenings`/`extractions` tables hold the data; slim or stream the status payload when Phase 3 SSE replaces polling. | API, data model | Deferred | Phase 2b / Phase 3 |
| 19 | External-ID mapping table for papers, only if DOI/OpenAlex-ID duplicates are measured to be common; re-confirms the review's drop decision. | data model | Deferred | after measurement |
| 20 | Readiness-grade `/health` (database connectivity check) for the Kubernetes probes; Phase 1 adds only a trivial 200. | API | Deferred | Phase 4 |
| 21 | Reconnectable run-progress endpoint (SSE); the `runs` per-step columns (`current_step`, `status_message`) feed it directly. | API | Deferred | Phase 3 |
| 22 | Postgres backup/restore procedure once the library has value; no phase owns it. | operations | Deferred | Phase 4 or later |
| 23 | Garbage collection of orphaned PDFs: old title-keyed v1 files and files left behind by merged/re-keyed papers. | ingestion | Deferred | Phase 2b or later |
| 24 | Vendor or pin the MiniLM model artifact (image layer or local cache) to remove the HuggingFace runtime dependency from live runs. | deploy, CI | Deferred | Phase 2a / Phase 4 |
| 25 | Concurrent-run safety: `/start_pipeline` allows overlapping runs whose paper upserts race; advisory locks or a per-review queue. | API, data model | Deferred | after v1.0 (single user until then) |
| 26 | Plan-wording amendment after the freeze lifts: section 5.4's `docs/` layout should also list `backlog.md`, `eval_notes.md` and `reviews/`. | `docs/plan_v2.md` | Open | end of Phase 1 |
| 27 | Keep the golden characterization transcript beyond Phase 1 as a standing mechanics-regression harness next to the eval harness. | tests | Deferred | Phase 2a |
| 28 | A `pages` table or raw page-text storage for Phase 2b's full-paper-context experiment; possibly never needed while the chunk page-partition invariant holds. | data model | Deferred | Phase 2b design |
| 29 | Generalize run-level provenance into a queryable `run_configs` table for the eval harness. | data model, eval | Deferred | Phase 2a design input |
| 30 | A reusable stub OpenAI-compatible server for optional "live-shaped" smoke tests beyond the in-process fake LLM. | tests | Deferred | when needed |
| 31 | Promote the local compose restart check into a nightly CI job if restart regressions ever appear. | CI | Deferred | when needed |
