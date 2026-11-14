# Goldfish Brainstorm Report — Phase 1 (Foundation)

**Target:** `concepts_brief.md` (whole document)
**Mode:** BRAINSTORM · **Date:** 2026-11-14
**Scope rule applied:** the plan (`docs/plan_v2.md`) is frozen; all findings challenge the brief's Phase 1 defaults only. Plan-level ideas are collected under "Backlog candidates" at the end.

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-design` | completed |
| `egm-codebase-details` | completed |
| `egm-zoom-out` | completed |
| `egm-comprehension` | completed |
| `egm-implementation-readiness` | completed |
| `egm-structural` | completed |
| `egm-inventive-catalyst` | completed |

Verified-accurate brief claims (codebase lens, no finding): `maybe_wrap_openai` exists in `tracing.py:26-36` (5.2); the forever-404 poll loop exists at `ui_app.py:144-165` (2.6); the FAISS `-1` edge case exists at `extract_agent/document_processing_node.py:152-157` (4.6); the paper contract gaps exist as described (4.1/3.3); the test defects exist as described (6.2/6.3); `pre_excluded=[]` confirmed at `Orchestration/nodes.py:75` (6.5); `tenacity==9.1.4` is pinned but currently unused (5.3); v1 `job_id` is an API-generated uuid4 (2.1); the `libgomp` caution is right (4.7).

---

## Prioritized Findings (Blockers → Major → Nits → Ideas)

### B1. The "fake-LLM end-to-end run" is undefined: the test profile fakes only the LLM, and the seam it plugs into does not exist in Batch 0 — Severity: Blocker
* **Reviewer Lens:** `egm-design`, `egm-codebase-details`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 5.5, 6.6, 6.1, 1.2, 2.7, Batch 0 narrative
* **Discrepancy Description:** Two intertwined gaps. (a) *Coverage:* a v1 end-to-end run also pages OpenAlex over HTTP (`search_agent/api_client.py:77-133`), downloads real PDFs (`document_processing_node.py:99-111`), parses them with PyMuPDF, and loads `all-MiniLM-L6-v2` — a HuggingFace download on a clean CI runner. The fake LLM keyed by `response_model` covers exactly three call sites and none of this; the smoke check (6.6) and both integration tests (2.7) are therefore network-dependent and non-deterministic, jeopardizing the "CI green" exit criterion. (b) *Sequencing:* the fake LLM is selected at the `get_llm` seam (5.5), which only arrives in Batch 1. In Batch 0 the three clients are constructed independently — `search_agent/agent.py:35-41` (constructor), `Screening_Agent/screening_agent.py:51-54` (constructor), `extract_agent/rag_extraction_main.py:27-33` (**module scope, built at import time**, so a profile set after import can never reach it). "Smoke check green after each commit" (1.2) cannot start true.
* **Rationale & Recommendation:** Prescribe the full test-profile fake surface: (1) fake LLM keyed by `response_model` as written; (2) a stubbed OpenAlex client returning the trimmed committed fixture (extended with `openalex_id`/`pdf_url` per 4.1 and including the two-OpenAlex-IDs-one-DOI case); (3) one or two tiny committed fixture PDFs (2–3 pages, so page-aware chunking is exercised) served from a local path; (4) an explicit decision whether `get_embedder()` under the `test` profile returns real MiniLM (then HF caching in CI is mandatory) or a deterministic 384-dim fake. For Batch 0, pick one: either scope the smoke check down to "graph compiles + unit tests green" and land fake-LLM e2e as the *first* Batch 1 commit (settings + seam before any package move), or prescribe pytest monkeypatching of the three construction sites as declared throwaway scaffolding. Either way, record that `rag_extraction_main.py`'s module-level client must become lazily constructed, or injection can never reach it.

### B2. The `runs` schema cannot reproduce the v1 `/status` contract: per-step progress, field mapping, and update cadence are all unspecified — Severity: Blocker
* **Reviewer Lens:** `egm-codebase-details`, `egm-design`, `egm-comprehension`, `egm-implementation-readiness`, `egm-inventive-catalyst`
* **Affected Scope:** 2.1–2.6, 2.3 especially
* **Discrepancy Description:** v1's background task updates the job record **after every node** with `current_step` and `status_message` (`Backend/main.py:38-56`), and `ResearchResponse` (`Backend/schemas.py:18-24`) carries `current_step`, `status_message`, `raw_papers_count`, `screening_results`, `extracted_papers`, `final_analysis` — it has **no `status` field**. The UI branches on `current_step` values including `completed`/`error` (`ui_app.py:148-164`). The brief's `runs` design holds only the coarse enum (2.2) and `result` jsonb "screening and extraction output" (2.3). Unanswered: where `current_step`/`status_message`/`raw_papers_count` live; whether `runs` is updated per `astream` step (only-at-end silently removes mid-run progress — a behaviour change beyond 4.6); how 2.5's "`status: interrupted`" maps onto a response model without that field; how `failed` maps to v1's `current_step="error"`; who flips `pending → running`.
* **Rationale & Recommendation:** Enumerate the `runs` columns (`id`, `user_id`, `review_id?`, `status`, `current_step`, `status_message`, `result` jsonb, timestamps, provenance — see M12), state that the background runner updates `current_step`/`status_message` per `astream` step exactly as v1 updates `JOBS`, and write out the exact `ResearchResponse` payload for each of the five statuses — including the `failed → current_step="error"` mapping and `interrupted` as a new `current_step` value — then key 2.6's UI terminal check on exactly that set. One mapping table ends the ambiguity and makes "unchanged wire contract" verifiable.

---

### M1. Silent v1 behaviour changes beyond 4.6 are undeclared — the brief needs a behaviour-change register — Severity: Major
* **Reviewer Lens:** all seven lenses converged on this
* **Affected Scope:** 4.1, 4.2, 4.4, 4.6, 5.3, Overview ("unchanged v1 behaviour")
* **Discrepancy Description:** Only 4.6 is flagged, but at least four other defaults change outputs: (a) **4.1** — v1 re-resolves the PDF at ingestion with a *broader* candidate heuristic (`oa_url`, all locations, landing pages — `document_processing_node.py:62-96`) and skips DOI-less papers; using search-time `pdf_url` (`primary_location.pdf_url or best_oa_location.pdf_url`, `api_client.py:106-109`) selects different URLs (different download success rates, possibly different PDF versions) and ingests papers v1 silently dropped — arguably a bigger baseline shift than 4.6. (b) **4.2** — v1 joins all pages and cuts continuous windows (`document_processing_node.py:117-123`); per-page windows move every chunk boundary, so retrieval and extraction inputs differ. Owner-mandated, but still a change. (c) **4.4** — skip-if-exists replaces v1's re-download-every-run. (d) **5.3** — v1 search falls back instantly to a tokenized query on LLM failure (`agent.py:79-86`); three tenacity attempts with backoff change failure-path latency and outcomes.
* **Rationale & Recommendation:** Keep the defaults (they fix real bugs or are mandated), but add one "declared deviations from v1 for the Phase 2a baseline" table containing 4.1, 4.2, 4.4, 4.6, 5.3, and qualify the Overview to "unchanged except the enumerated list". Consider softening 4.1: keep the oa_url-candidate lookup as a *fallback* when the stored `pdf_url` download fails (also reduces the `pdf_unavailable` rate for 3.2). See Idea I1 for making the register testable.

### M2. 5.1's premise is wrong (extraction is already async) and the async port hides an event-loop regression — Severity: Major
* **Reviewer Lens:** `egm-codebase-details`, `egm-design`, `egm-zoom-out`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 5.1, 4.7, 2.7
* **Discrepancy Description:** Extraction already uses `AsyncOpenAI` + `instructor.patch` (`rag_extraction_main.py:27-33`, awaited at line 201); its real defect is **import-time client construction**, which the brief never names. The only sync LLM call site is search. The hidden hazard: today `search_node` is a sync def, so LangGraph runs it in an executor thread and the event loop stays responsive. Once `search_node` becomes `async def` to await `get_llm("search")`, the blocking `requests`-based OpenAlex paging loop (including a blocking `time.sleep(2)` on 429) runs *on* the FastAPI event loop — `/status` polling freezes for the duration of the search. The async scope boundary is also ambiguous: "port the call sites" necessarily drags `run_precise_retrieval_cycle`, `search_node`, and `new_main.main` async.
* **Rationale & Recommendation:** Keep async-only but correct and complete 5.1: (1) search is the only sync LLM call site; (2) extraction's port moves client construction from module scope into call-time `get_llm("extraction")`; (3) enumerate the async boundary — `search_node` becomes `async def`, OpenAlex HTTP stays sync `requests` wrapped in `asyncio.to_thread` (the pattern v1 already uses for download/parse/embed); (4) state explicitly that no HTTP library changes in Phase 1.

### M3. DB access style (sync vs async SQLAlchemy) is an undecided design choice — Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** Batch 2, 4.7, 2.1–2.4
* **Discrepancy Description:** 4.7 adds `psycopg[binary]` but never says whether the engine is sync or async. Run-status updates, upserts, chunk inserts and retrieval all execute inside the async background task / async nodes; sync sessions there block the event loop (same hazard as M2), while the async engine changes every repository signature. The implementer must not choose this alone.
* **Rationale & Recommendation:** Decide and record one of: sync engine with all DB work called via `asyncio.to_thread` from async contexts (simplest, consistent with "simple and robust"), or full async engine (`postgresql+psycopg://` async). Note Alembic runs sync regardless.

### M4. Paper upsert (3.1) is not implementable as written: two unique keys, no merge rule, incomplete normalization — Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-zoom-out`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 3.1, 2.7
* **Discrepancy Description:** Postgres `ON CONFLICT` targets one constraint; with `doi` and `openalex_id` both unique and the key varying per paper, a single upsert statement cannot work. Unresolved cases: (a) second OpenAlex record sharing a DOI — keep or overwrite the stored `openalex_id`? (b) a paper first stored DOI-less (keyed by `openalex_id`) later reappearing *with* a DOI — the DOI-keyed insert finds no conflict on `doi`, then violates `unique(openalex_id)` and errors. DOI normalization also omits `http://dx.doi.org/`, which v1 strips (`document_processing_node.py:65`).
* **Rationale & Recommendation:** Prescribe the algorithm, not just the key: SELECT by normalized DOI OR `openalex_id`, then INSERT or UPDATE, in one transaction (single-writer pipeline, no race); merge rule "first-seen `openalex_id` wins, `doi` is filled in when it appears"; normalization strips both prefixes and lowercases. Add both collision cases to the duplicate-run integration test (the two-IDs-one-DOI fixture is already required by `phase1_inputs.md` §3 but named nowhere in 2.7).

### M5. Chunk idempotency is not guaranteed: "re-attempt non-chunked" can duplicate chunk sets, and the skip rule has no identity key — Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-comprehension`, `egm-implementation-readiness`, `egm-inventive-catalyst`
* **Affected Scope:** 3.2, 4.2, 3.7, exit criterion "one chunk set per paper"
* **Discrepancy Description:** If a process dies mid-chunking (status still `downloaded`, some chunk rows inserted), the next run's re-attempt appends a second partial set — the exit test fails in exactly the crash case the restart machinery targets. Also ambiguous: does "non-`chunked`" include `pdf_unavailable` and `failed` (re-hit the URL every run)? And "chunked" under *which parameters* — when the embedder changes (Phase 2a, planned) or chunking changes (2b overlap), `chunked` papers are stale yet skipped, with no data recording chunk-set identity.
* **Rationale & Recommendation:** Two sentences in the design: (1) chunk insertion and `ingestion_status='chunked'` happen in one transaction, and any re-attempt first `DELETE FROM chunks WHERE paper_id=...` in that same transaction — "one chunk set" true by construction; (2) store a `chunker_version` constant next to `embedding_model` and make the skip condition `chunked AND embedding_model = settings AND chunker_version = CURRENT`, so the 2a re-embed and 2b re-chunk are a one-constant bump that the next run reconciles, and the exit test survives unmodified. Also state which statuses are re-attempted.

### M6. Retry stacking: tenacity lands on top of four existing retry layers — Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-codebase-details`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 5.3, 5.1
* **Discrepancy Description:** Unless the brief says otherwise, these coexist: tenacity (3 attempts, backoff) at the seam; the screening agent's hand-rolled loop (`max_retries=2` with sleeps, `screening_agent.py:213-239`); Instructor's validation retries; the OpenAI SDK's own default `max_retries=2` on connection errors/429; and the OpenAlex client's unbounded 429 sleep loop. Worst case: 6+ LLM attempts per screened paper with compounding backoff on a fanless laptop, and search's instant fallback becomes fallback-after-three-backoffs (see M1d). Where tenacity wraps (patched client method? per node? call sites?) is unstated.
* **Rationale & Recommendation:** Simplest option consistent with the owner's preference: drop tenacity for the LLM path and set `AsyncOpenAI(max_retries=3)` inside `get_llm`; alternatively, specify the exact tenacity-wrapped function and set the inner SDK `max_retries=0`. Either way: state Instructor's `max_retries` per role, and state that the screening agent's hand-rolled loop is removed in the port (or kept, with the doubled-attempt consequence accepted). Also question 429 handling at all — local Ollama never emits 429.

### M7. Integration-test mechanism (2.7): CI cannot restart a service container, "same test code" is false, and the CI integration stage deviates from the frozen plan — Severity: Major
* **Reviewer Lens:** `egm-zoom-out`, `egm-design`, `egm-comprehension`, `egm-implementation-readiness`, `egm-structural`
* **Affected Scope:** 2.7, 6.7, exit criteria; structural cross-check against plan §8–9
* **Discrepancy Description:** (a) GitHub Actions service containers cannot practically be restarted mid-job; the brief concedes this parenthetically, then claims "same test code locally and in CI". (b) Restarting the API *process* from pytest (subprocess, port wait, health poll) is a classic flaky-CI generator; after Batch 2 the API holds no state, so a restart is fully simulated in-process (tear down the app, build a second instance on the same DSN, assert completed runs survive and pending/running turn `interrupted`) — and a `TestClient` "restart" would *not* exercise the lifespan marking, so the mechanism must be stated either way. (c) Plan §8 says CI runs *only* lint and unit tests with the fake LLM; §9's pipeline has no integration stage — the brief's Postgres-service CI stage is a deviation from the frozen plan that needs explicit owner sign-off, and Batch 0's "lint + unit tests" and 6.7's four stages describe two different CIs.
* **Rationale & Recommendation:** Decide one mechanism and write it down: preferred — in-process restart simulation as the standard integration test (runs anywhere Postgres is reachable), plus the literal API+Postgres `docker compose restart` check as a small local script run at phase exit and recorded in the exit checklist; if integration tests stay in CI, provision Postgres via the same compose file (runners have Docker), not a second service-container config, and mark the plan deviation for sign-off. Make Batch 0 and 6.7 describe the same CI with its per-batch growth points (see M10).

### M8. Nobody writes `reviews` in Phase 1 — its writer, `runs.review_id`, and the criteria payload are undefined, and 3.5's shape claim is false — Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-zoom-out`, `egm-codebase-details`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 3.5, 3.8, 2.1, 2.3, Batch 2
* **Discrepancy Description:** The migration creates `reviews`, 3.5 fixes `criteria`'s shape, but the plan defers "the endpoint creates a reviews row" to Phase 2b — so the brief must say whether `/start_pipeline` inserts a `reviews` row now and whether `runs.review_id` exists/is NOT NULL, or where a run's question and criteria live otherwise. Separately, 3.5's "exactly what v1's state carries today" is false: it omits `additional_info` (carried by `ResearchRequest` and `PipelineState`, consumed by search expansion at `new_main.py:57-59` and screening at `Orchestration/nodes.py:74`), and it renames v1's `target_output_count` (search fetch size, default 25) to `target_included`, which in the frozen plan is Loop 1's count of included papers with retrievable PDFs (default 10) — a semantically different number Phase 2b would misread.
* **Rationale & Recommendation:** Simplest consistent choice: `/start_pipeline` inserts a `reviews` row (question + criteria) and `runs.review_id` is a NOT NULL FK from day one, matching 3.8's no-backfill logic; otherwise declare `reviews` created-but-empty and store the request on `runs`. Fix 3.5: add `additional_info`, and keep the key `target_output_count` (or document the rename and semantic mapping explicitly).

### M9. Batch 1 commit plan is underspecified — and as written it reintroduces the rejected package-by-package migration — Severity: Major
* **Reviewer Lens:** `egm-zoom-out`, `egm-design`, `egm-comprehension`, `egm-implementation-readiness`, `egm-inventive-catalyst`
* **Affected Scope:** 1.2, 1.3, 6.2, Alternatives Weighed
* **Discrepancy Description:** "One commit per ported package plus one deletion commit, smoke green after each commit" is the 6+-step hybrid migration the Alternatives section rejects, demoted to commit granularity — with dual module identity during the hybrid (root `tracing.py` and `src/llm/tracing.py` importable simultaneously: exactly the duplicate-`ResearchPaper` class of bug 6.2 fixes). If the per-commit plan stays, only one order satisfies rule 1.3 (leaves first: `tracing` → pipeline packages → `graph` → `api`+`ui` → deletion), each old module must become a re-export shim, and the brief must pin: whether each package commit simultaneously rewires onto `get_llm`/async or packages move verbatim first; which commit moves tests to `tests/` (pin to the screening commit, or collection breaks mid-batch); which commit updates `Dockerfile.backend` CMD, `Dockerfile.frontend`, `.dockerignore`, compose, READMEs; whether the duplicate `ResearchPaper` (search vs screening schema) is unified or moved as-is (behaviour preservation argues as-is).
* **Rationale & Recommendation:** Two coherent options — pick one explicitly: (a) *zoom-out's*: collapse Batch 1 to one move-and-rewrite state (one or two commits: move+imports, then deletions), green at batch end — the owner constraint requires a runnable system per *batch*, not per commit — and delete rule 1.3 as having nothing left to govern; or (b) keep per-package commits but write the full ordered commit list with named shim files and the Docker/test touchpoints. Option (a) is simpler and avoids dual-identity bugs; (b) gives finer-grained safety. Batch 2 also needs internal checkpoints either way: commit A = compose + schema + `runs` replaces the `JOBS` dict (FAISS untouched); commit B = ingestion/pgvector + exit tests.

### M10. Coverage gaps: five plan-§10 / inputs items have no decision, so the Goals claim of full coverage is false — Severity: Major
* **Reviewer Lens:** `egm-structural`, `egm-comprehension`, `egm-inventive-catalyst`
* **Affected Scope:** Working hypothesis, sections 1, 5, 6, Goals
* **Discrepancy Description:** Missing from the tables entirely: (a) correcting `CLAUDE.md`/`README.md` for the new layout (plan §10 item 3); (b) the eval-inputs copy — "the eval snapshot location" is undefined in both plan and brief (exact destination paths, and where the retrieval date is recorded; note both source files are named `search_results.json` and the *full* files are the snapshot, unlike 6.3's trimmed fixture); (c) the node-level fake-LLM tests for screening and extraction that `phase1_inputs.md` §6 requires (6.6's e2e smoke is not them); (d) the two-OpenAlex-IDs-one-DOI exit fixture (inputs §3/A11 — see M4); (e) **prompts**: plan §5.4 mandates versioned prompt files in `src/llm/prompts/`, and 3.6 builds on `prompt_version`, but the brief never schedules moving v1's inline prompts (`agent.py:50-62`, `rag_extraction_main.py:72-199`, screening) or defines where `prompt_version` values come from. Dockerfile/compose disposition is also absent from 1.1 (see M9). Additionally the batch-to-decision mapping is only implicit (2.6 is a behaviour change, so Batch 2 not Batch 1; 4.1's schema change — Batch 1 or 2?; when CI gains stages; `src/db/` absent from the 1.1 map).
* **Rationale & Recommendation:** Add rows: 1.5 (docs correction, deletion-commit slot), 6.x (eval snapshot path + retrieval-date format), 6.x (node-level fake tests and their batch), extend 2.7 (duplicate-DOI fixture), 5.x (prompts: move byte-identical into `src/llm/prompts/` with `PROMPT_VERSION = "v1"` per role in Batch 1 — zero behaviour change — or an explicit deferral with a placeholder convention like `v1-inline`). Add a "Batch" column to the decision tables and a short checklist-to-decision mapping under Goals.

### M11. Alembic/pgvector mechanics and the migration runner are unspecified — Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-comprehension`
* **Affected Scope:** Batch 2, 4.7, 2.7, 6.7, 3.8
* **Discrepancy Description:** Missing concrete decisions: the first migration must `CREATE EXTENSION IF NOT EXISTS vector`; autogenerate does not emit `pgvector.sqlalchemy.Vector` without configuration; the Postgres image must be pgvector-enabled (`pgvector/pgvector:pgXX`) in compose *and* CI — plain `postgres` fails; nobody is named to run `alembic upgrade head` (API entrypoint, one-shot compose service, pytest session fixture, manual command?) even though compose, the integration tests, CI, and the restart test all need a migrated schema; and nobody seeds the `local` user that 3.8's NOT NULL columns require (an Alembic data migration is the natural answer).
* **Rationale & Recommendation:** One short "migrations" paragraph in the design: pinned image, extension statement location, Vector-type handling in migration files, the chosen runner per environment, and the user-seed data migration.

### M12. Provenance convention (3.6) has no Phase 1 carrier — and Phase 2a, not 2b, is when that bites — Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`, `egm-zoom-out`, `egm-structural`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 3.6, 2.3; owner constraint "prepare model and prompt provenance"
* **Discrepancy Description:** 3.6 fixes `model`/`prompt_version`/`created_at` for "every LLM-output table", then notes Phase 1 only has `runs.result` — without giving `runs` any of those fields. Phase 2a switches models while results still live in `runs.result`: baseline and candidate-model runs become indistinguishable rows, and the 2b backfill into `screenings`/`extractions` cannot be data-preserving because provenance was never captured. Also, "current row = latest created_at" solves a problem Phase 1 doesn't have (runs are append-only by construction) — the view rule is 2b design smuggled in.
* **Rationale & Recommendation:** Shape `runs.result` as an envelope from day one: `{"provenance": {"models": {role: name}, "prompt_versions": {role: v}, "profile": ...}, "screening": ..., "extraction": ...}` written at run start from the resolved Settings object (~10 lines), or equivalent columns on `runs`. Defer the latest-`created_at` view rule to the 2b design where its tables exist. Depends on M10(e) for `prompt_version` values.

### M13. 6.4 drops three tests to kill one — Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** 6.4, 6.2
* **Discrepancy Description:** Only `test_screening_main_calls_protocol_helper` (`test_screening.py:143-148`) reads the source of the deleted `screening_main.py`. The class's other two tests — `test_screen_file_with_protocol_signature` (137-141, targets `screening_agent.py`, which is *moved*, not deleted) and `test_review_config_round_trip` (150-156, pure fixture round-trip that passes once 6.2 fixes the path) — remain valid. The stated rationale is factually wrong for two of the three.
* **Rationale & Recommendation:** Drop only the one source-text test; keep the other two.

### M14. Deletion list 1.1 names three files that do not exist — Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** 1.1
* **Discrepancy Description:** `extract_agent/` contains no `extract_agent.py`, `extraction_agent.py`, or `extraction_main.py` (CLAUDE.md's legacy list is stale on this too). The four real dead scripts (`auto_pdf_downloader.py`, `add_full_text_from_pdfs.py`, `rag_chunker.py`, `rag_retriever.py`) are covered, so coverage is complete — but a fully prescriptive design handed to an AI coder must not contain phantom paths.
* **Rationale & Recommendation:** Replace the sublist with the four real filenames. Also extend the 1.1 table with: Modify rows for `Dockerfile.backend` (CMD at line 24), `Dockerfile.frontend`, `docker-compose.yml`, `.dockerignore`; explicit rows for `Screening_Agent/testdaten/review_config.json` (→ `tests/fixtures/`), `Screening_Agent/review_config_Evaluation.json` (delete), and the per-package READMEs; and note that `rag_extraction_main.py`'s script/CLI portion (the `sys.path`/`__package__` workaround) is stripped on move.

### M15. Packaging and tooling config are missing: no decision on the `src/` import root, pyproject, pytest config, or CI files — Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** 1.1–1.3, 6.2, 6.7
* **Discrepancy Description:** The repo has no `pyproject.toml`, pytest config, ruff config, conftest, or `.github/`. "Import from `src/`" leaves open: `from src.pipeline...` as a plain package (affects the Dockerfile CMD `src.api.main:app`), an installed package (`pip install -e .`), or pytest `pythonpath` only (breaks the Docker runtime path). 6.2's "collection without PYTHONPATH" is unachievable without picking one; every Batch 1 commit depends on the choice. Related: `Screening_Agent/` and `extract_agent/` lack `__init__.py` today (implicit namespace packages), which matters for Batch 0 collection *before* the move.
* **Rationale & Recommendation:** Specify in the design: the import-root convention and matching Dockerfile CMD; `pyproject.toml` contents (metadata, pytest `markers = ["integration"]`, default `addopts = "-m 'not integration'"`, ruff section); that Batch 0 creates `pyproject.toml` + `tests/conftest.py` + `.github/workflows/ci.yml`; and the Batch 0 packaging fix (`__init__.py` or `importmode=importlib`).

### M16. `/health` does not exist, and CI's heavy-dependency costs are unplanned — Severity: Major
* **Reviewer Lens:** `egm-codebase-details`, `egm-zoom-out`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 6.6, 6.7, 4.7
* **Discrepancy Description:** v1 exposes only `GET /` (`Backend/main.py:136-138`); 6.6 has CI check `/health` but no batch adds it — as written the CI step fails. Also unplanned: `pip install` pulls torch (~1.5–2 GB) via sentence-transformers and the e2e test downloads MiniLM (~90 MB) from HF every run without caching; the image build repeats the torch install; the compose-up check needs a dummy `OLLAMA_BASE_URL` and should bring up only backend + postgres, not the Streamlit frontend.
* **Rationale & Recommendation:** Add one line to a batch: "`GET /health` added (trivial 200, or 200 + DB ping — pick one)"; CI caches pip and `~/.cache/huggingface`, uses buildx layer caching, sets a dummy Ollama URL; decide whether CI's e2e uses the real embedder (cache mandatory) or the fake from B1(4).

### M17. Retrieval has no home: 1.4 omits the plan's `retrieval` stage and the `extract_agent` file split is unmapped — Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-codebase-details`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 1.1, 1.4, 4.5
* **Discrepancy Description:** The frozen plan's canonical stage list is search → screening → ingestion → **retrieval** → extraction → store; 1.4's submodules omit retrieval. `document_processing_node.py` mixes ingestion (download/parse/chunk/embed) with retrieval (`FIELD_QUERIES`, top-5 per field, lines 136-162), and 1.1 maps its files to "`ingestion/` + `extraction/`" with no function-level assignment. Undecided: does the Phase 1 ingestion node still perform retrieval and put `retrieved_chunks_by_field` into state (preserving the v1 graph shape), or does extraction query pgvector itself?
* **Rationale & Recommendation:** Decide and write: Phase 1 keeps the v1 node shape — ingestion persists chunks, then runs per-field pgvector retrieval and fills state exactly as v1 did; retrieval code lives in a named file (e.g. `src/pipeline/ingestion/retrieval.py`); the subgraph split is Phase 2b. List the target file for each function in `document_processing_node.py`.

---

### N1. 4.2 micro-decisions: `ordinal` scope, empty pages, page tails, page numbering — Severity: Nit
* **Reviewer Lens:** `egm-codebase-details`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** 4.2
* **Discrepancy Description:** Unstated: is `ordinal` per page or per paper (per-paper reads more naturally for the exit check and 2b evidence links); are whitespace-only pages skipped; are sub-1200-char page tails kept as short chunks; pages 1-based (they feed user-facing evidence in 2b)?
* **Rationale & Recommendation:** Four one-word decisions in 4.2's default.

### N2. `runs.result` will duplicate all retrieved chunk texts — Severity: Nit
* **Reviewer Lens:** `egm-design`, `egm-zoom-out`, `egm-implementation-readiness`
* **Affected Scope:** 2.3
* **Discrepancy Description:** `document_processing_node` embeds `retrieved_chunks_by_field` into the paper dicts in-place (lines 213-218), so a verbatim `result` carries ≤25×1200 chars per paper — the same text as `chunks` — re-serialized on every 1 s poll (~0.5–1 MB per 20-paper run).
* **Rationale & Recommendation:** Acceptable and required for the unchanged status payload — but say so explicitly, define `result` as exactly the terminal `GET /status` payload, and note it as the thing 2b's tables eliminate.

### N3. Ingestion-status enum is larger than its own policy — Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** 3.2, 4.4
* **Discrepancy Description:** The policy treats every non-`chunked` state identically, and 4.4's file-exists check already encodes "downloaded" on disk, so `downloaded`/`failed` vs `pending` carry no behavioural weight.
* **Rationale & Recommendation:** Shrink to `pending | chunked | pdf_unavailable` + `last_error` text, or keep five and state the extra states are observability-only.

### N4. Enum representation: native Postgres enums vs text + CHECK — Severity: Nit
* **Reviewer Lens:** `egm-comprehension`, `egm-zoom-out`, `egm-structural`
* **Affected Scope:** 2.2, 3.2, 3.4
* **Discrepancy Description:** Unstated, and it affects every later enum migration. Related: 3.4's values (`included`) rename v1's buckets (`include`) while claiming to mirror them, and the enum "fixed now" should create zero DDL — no `screenings` table exists until 2b.
* **Rationale & Recommendation:** text + CHECK as the "simple option", stated once; 3.4 becomes a documented convention line for 2b (no type, no column, no migration), with the rename acknowledged.

### N5. 5.4's unused roles are untestable config — Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** 5.4
* **Discrepancy Description:** Nothing reads `router`/`summary`/`judge`; `get_llm("router")` behaviour is undefined. Adding a settings field later is a one-line diff.
* **Rationale & Recommendation:** Wire exactly `search`, `screening`, `extraction` (+ embedder); `get_llm` raises on unknown roles. Keep the role *names* as a documented list, not config entries.

### N6. Ruff in Batch 0 lints code Batch 1 moves or deletes — Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** 6.1, 6.7
* **Discrepancy Description:** Lint-fix churn on files about to be moved/deleted is wasted work and noisy diffs.
* **Rationale & Recommendation:** Batch 0 CI = unit tests only; add the ruff gate in Batch 1 when code lands in `src/`. (If ruff stays in Batch 0, scope it to the new files.)

### N7. `venue` column contradicts the brief's own 4.3 reasoning, and is new code, not a carried field — Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`, `egm-codebase-details`
* **Affected Scope:** 3.3, 4.3, 4.1
* **Discrepancy Description:** 4.3 rejects a reserved `section` column because later nullable columns are cheap; 3.3 adds `venue` for Phase 3 with the opposite logic. The live search path never computes the venue (only the bypassed gatekeeper does, `agent.py:115-127`), so "search carries it" means new extraction code in the formatting loop plus a wider `ResearchPaper`.
* **Rationale & Recommendation:** The asymmetry is defensible (venue must be captured at search time or backfilled later) — own it in the rationale, list the search-output change in 4.1's contract set, and note it is new behaviour-neutral code. `authors` is free (already captured, `agent.py:173-177`).

### N8. Paper-contract ripple: consumers must change together — Severity: Nit
* **Reviewer Lens:** `egm-comprehension`, `egm-structural`
* **Affected Scope:** 4.1, 3.3
* **Discrepancy Description:** `phase1_inputs.md` names the consumers (`Backend/schemas.py`, `ui_app.py`, `screening_schemas.ResearchPaper`); the brief covers only producer and ingestion. Adding required fields to `ResearchPaper` breaks screening on old fixture data.
* **Rationale & Recommendation:** Extend 4.1 to name the consumer updates and state the new fields are optional-with-default on the Pydantic model.

### N9. Small unstated literals and paths — Severity: Nit
* **Reviewer Lens:** `egm-comprehension`, `egm-implementation-readiness`, `egm-structural`
* **Affected Scope:** 3.8, 4.4, 5.6, 6.2, 6.3, 6.8, 2.7
* **Discrepancy Description / Recommendation (one line each):**
  * Seeded user's literal email (e.g. `local@localhost`) — name it (3.8). Also: `new_main.py:16` hardcodes a personal email as the OpenAlex contact fallback; confirm settings *removes* the hardcoded default.
  * PDF volume: 4.4 says "the pdfs volume"; compose calls it `pdfs_auto` — use the real name or state the rename. Add a named Postgres data volume (the restart test needs it; compose has none today).
  * "Skip download when the file exists": a zero-byte/partial file from a killed run is never repaired — make it "exists and starts with `%PDF`" (v1 already checks magic bytes).
  * Ollama URL defaults: `host.docker.internal:11434` in compose vs `localhost:11434` native — name both in 5.6; extend `.env.example` with all new settings.
  * 6.2's "fix the fixture path" — the file the test names (`review_config.json`) does not exist; only `testdaten/review_config.json` does. Say which way (move/rename vs repoint), and give the Batch 0 fixture path that survives the Batch 1 move.
  * 6.8 explanations: name the destination (commit messages, PR descriptions, or a `docs/` file).
  * A `Makefile`/`justfile` (`make test` / `make integration` / `make up`) — one checklist line keeps the AI sessions reproducible.

### N10. Document-structure nits — Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** Alternatives Weighed, Goals/Non-Goals, 4.7, 6.8, 5.6
* **Discrepancy Description / Recommendation:**
  * The first two Alternatives entries lack decision numbers (both resolve to 1.2); attribution phrasing is inconsistent — unify.
  * Missing Alternatives entry: the external-ID mapping table explicitly rejected in `phase1_inputs.md` §3 (belongs next to 3.1).
  * 5.6's "everything the review flagged gets one home" is untraceable — itemize against the flagged call sites, at least naming the hardcoded model at `Orchestration/nodes.py:62`.
  * Non-Goals hedge "section labels (Phase 2b or dropped)" vs 4.3's firm "dropped" — align.
  * 4.7 (project-wide dependencies) sits under "Ingestion and chunks"; 6.8 is a process rule under "Tests and CI" — move to a small "Dependencies" / "Working agreements" note.

---

## Ideas (inventive transforms, Phase 1-sized)

### I1. Golden characterization transcript (makes M1's register testable)
Batch 0 runs while v1 still exists: capture one stubbed fake-LLM end-to-end run's final state JSON as a committed artifact. After Batches 1 and 2, the same test diffs against it with an explicit allow-list of the declared deviations (M1). Unintended behaviour change then fails CI instead of surfacing in the Phase 2a baseline. Cost: fixture maintenance and a deliberate regeneration step per intended change. (Depends on resolving B1's Batch 0 sequencing — if the e2e moves to early Batch 1, capture the transcript there, before any package port.) — `egm-inventive-catalyst`

### I2. Provenance envelope in `runs.result`
See M12 — ~10 lines, makes the 2b migration a mechanical unpack and makes every 2a run self-describing. — `egm-inventive-catalyst`

### I3. Zero overlap is secretly a feature: the partition invariant
With no overlap and per-page windows, concatenating a paper's chunks in `(page, ordinal)` order reconstructs each page's text exactly — so the 2b overlap experiment needs no re-download or re-parse: reconstruct pages from the DB, re-slice, re-embed (minutes of MiniLM time on the M4). Lock it in with (a) a unit test asserting `"".join(chunks of page) == page_text` at ingestion (also catches chunking bugs free; document it as Phase-1-only, retired when overlap arrives), and (b) optionally `char_start`/`char_end` columns — redundant today, not derivable the day overlap exists, and they give sub-page evidence highlighting without a migration. The test is the must; the columns the nice-to-have. — `egm-inventive-catalyst`

### I4. `chunker_version` reconciliation key
See M5(2) — one column and one constant turn the duplicate-run exit test into a permanent regression test surviving every future chunking/embedding change. — `egm-inventive-catalyst`

### I5. Table-driven fake LLM for mixed screening buckets
Type-keying is de-facto role-keying (the three roles use distinct response models), so 5.5 mostly works as written. The residual gap: one canned `PaperScreeningResult` gives every fixture paper the same decision, so integration tests cannot shape mixed buckets. Let the registry value be an instance *or* a `Callable[[messages], instance]` matching sentinel tokens in fixture abstracts (e.g. `[FAKE:INCLUDE]`). If all-included suffices for the exit tests, keep the plain instance — but at minimum the canned screening decision must be "include", or ingestion/extraction are never exercised in the e2e run. Decide in the design, not during implementation. — `egm-inventive-catalyst`, `egm-implementation-readiness`

---

## Backlog candidates (plan-level — for `docs/backlog.md`, not Phase 1)

1. Migrate the OpenAlex client from `requests` to async `httpx` once the behaviour-change freeze lifts (removes the `to_thread` wrapper). (design, readiness)
2. Cap the OpenAlex 429 retry loop — `api_client.py:86-89` can spin indefinitely today; the plan defers this to Phase 2b. (codebase)
3. Record raw OpenAlex responses as versioned fixtures/cassettes so Phase 2a search evals replay against a fixed API snapshot. (design, comprehension, readiness)
4. Assign structured JSON logging to a phase — plan §5.1 lists it as cross-cutting but no phase checklist owns it; v1 is `print()` throughout. (codebase)
5. Retention/cleanup policy for `runs.result` jsonb once 2b's tables arrive; slim/stream the status payload when Phase 3 SSE replaces polling. (zoom-out, design)
6. External-ID mapping table for papers, only if duplicates are measured to be common (re-confirming the Stage 8 drop). (zoom-out, structural)
7. Readiness-grade `/health` (DB connectivity) for the Phase 4 probes. (codebase)
8. Reconnectable run-progress endpoint (SSE, Phase 3) — B2's per-node progress columns feed it directly. (codebase, readiness)
9. Postgres backup/restore step once the library has value — no phase owns it. (comprehension)
10. Garbage collection of orphaned PDFs (old title-keyed v1 files; merged/re-keyed papers). (comprehension)
11. Vendor/pin the MiniLM artifact (image layer or local cache) to remove the HF runtime dependency. (readiness)
12. Concurrent-run safety: `/start_pipeline` allows overlapping runs whose upserts race — advisory locks or a per-review queue. (readiness)
13. Plan-wording amendments after the freeze lifts, if the brief keeps integration tests in CI: plan §8 "CI runs only lint and unit tests" and §9's pipeline. Also plan §5.4's `docs/` layout should list `backlog.md`, `eval_notes.md`, `reviews/`. (structural)
14. Keep the golden characterization transcript (I1) beyond Phase 1 as a standing mechanics-regression harness next to the eval harness. (inventive)
15. A `pages` table / raw page text storage for 2b's full-paper-context experiment — possibly never needed while I3's reconstruction property holds. (inventive)
16. Run-level provenance generalized to a queryable `run_configs` table for the eval harness (Phase 2a design input). (inventive)
17. A reusable stub OpenAI-compatible server for optional "live-shaped" smoke tests beyond the in-process fake. (design)
18. Promote the local compose restart check into a nightly CI job if restart regressions ever appear. (zoom-out)
