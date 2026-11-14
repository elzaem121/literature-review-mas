# Phase 1 — Foundation (Design Brainstorm Brief)

* **Author:** Mohamed Elsayed
* **Date:** 2026-11-14
* **Status:** revised after the Goldfish review (`docs/reviews/phase1_brainstorm_goldfish.md`); all findings folded in, owner rulings R1–R5 applied

## Overview

Phase 1 moves the v1 literature-review pipeline into a new `src/` layout, replaces the
in-memory job dict and per-paper FAISS indexes with Postgres + pgvector, and adds settings,
a single `get_llm(role)` seam, repaired tests, and CI. Behaviour and models stay those of
v1 (`qwen2.5-coder:7b` on local Ollama, `all-MiniLM-L6-v2` in-process), **except the six
declared deviations in the register below** — each fixes a defect or is owner-mandated, and
each is recorded for the Phase 2a baseline. Constraints fixed by the owner: Claude writes
all code and the design is fully prescriptive; migration in batches that each leave the
system runnable; restart and duplicate-run tests use the fake LLM; chunks are page-aware
with ordinals from Phase 1; overlap is measured in Phase 2b; prefer simple, well-tested
options over clever ones.

## Owner rulings (from the review iteration)

* **R1 (B1):** Batch 0's check is "graph compiles + unit tests green". The first Batch 1
  commit builds settings + `get_llm` + the full fake surface before any package moves; the
  fake end-to-end smoke run starts there. No throwaway monkeypatching in Batch 0.
* **R2 (M7):** CI stays inside the frozen plan: lint + unit tests (fake LLM) + image
  build. Integration tests run locally (in-process restart simulation against Postgres)
  via a documented command and at phase exit; the literal `docker compose restart` check
  is a small local script in the exit checklist.
* **R3 (M9):** Batch 1 is one move-and-rewrite state in three commits (seam, move,
  delete), green after each commit; the hard requirement is a runnable system at batch
  end. No per-package commit sequence, no re-export shims.
* **R4 (M3):** Sync SQLAlchemy engine; database work is called via `asyncio.to_thread`
  from async contexts. Alembic runs sync as usual.
* **R5 (M8):** `POST /start_pipeline` inserts a `reviews` row (question + criteria), and
  `runs.review_id` is a NOT NULL foreign key from day one.

## Batch plan

Each batch ends with a green test run; Batch 1 commits are also individually green.

* **Batch 0 — Safety net.** Repair the screening tests in place: repoint the fixture to
  the existing `Screening_Agent/testdaten/review_config.json`, fix the duplicate
  `screening_schemas` import, drop only the one source-text test
  (`test_screening_main_calls_protocol_helper`), keep the other two tests of its class,
  and make collection work via a temporary `conftest.py` path shim (removed in Batch 1).
  Commit a trimmed `tests/fixtures/search_results.json` (3–5 papers, including two
  OpenAlex IDs sharing one DOI, with `openalex_id`/`pdf_url` fields). Create
  `pyproject.toml` (pytest config: `markers = ["integration"]`,
  `addopts = "-m 'not integration'"`; ruff config present, not yet gating),
  `.github/workflows/ci.yml` (unit tests only for now), and a `Makefile`
  (`up`, `migrate`, `test`, `integration`). Copy the gitignored eval inputs
  (`Screening_Agent/search_results.json`, `extract_agent/search_results.json`) to
  `eval/snapshots/v1/` with an `eval/snapshots/v1/README.md` recording their retrieval
  date. Check: unit tests green in CI.
* **Batch 1 — Seam, then layout.**
  * *Commit 1a (seam):* `src/llm/` with settings, `get_llm(role)`, `get_embedder()`,
    `tracing.py` (moved), and `prompts/` (v1 prompts moved byte-identical into versioned
    files, `PROMPT_VERSION = "v1"` per role). Rewire the three client call sites in place
    (search constructor, screening constructor, extraction's module-level client becomes
    lazy via `get_llm`). Port `search_node` to async with OpenAlex HTTP wrapped in
    `asyncio.to_thread`. Build the full test-profile fake surface (section 5) and the
    fake end-to-end smoke test; capture the golden transcript (section 6).
  * *Commit 1b (move):* move the live packages into `src/` (verbatim plus imports), move
    tests to `tests/`, update `Dockerfile.backend` (CMD → `src.api.main:app`),
    `Dockerfile.frontend`, `docker-compose.yml`, `.dockerignore`; add `GET /health`
    (plain 200); turn on the ruff CI gate for `src/` and `tests/`.
  * *Commit 1c (delete):* delete the legacy modules and per-package READMEs; correct
    `CLAUDE.md` and `README.md` for the new layout.
* **Batch 2 — Postgres.**
  * *Commit 2a (runs):* docker-compose gains `pgvector/pgvector:pg17` with a named data
    volume; Alembic migrations (extension, tables, seeded `local` user); `runs` replaces
    the `JOBS` dict with the per-step update rule and status mapping (section 2);
    `/start_pipeline` inserts the `reviews` row (R5); UI stop rules; restart integration
    test.
  * *Commit 2b (ingestion):* paper upsert, page-aware chunking into pgvector with
    `chunker_version`, per-field retrieval from pgvector; remove `faiss-cpu`; duplicate-run
    and duplicate-DOI integration tests; the page-partition unit test; CI compose-up
    `/health` check after image build.

## Proposed defaults per open sub-decision

Each default carries a one-line rationale and its batch. All were challenged by the
Goldfish review; this revision reflects the findings.

### 1. Migration of v1 code into `src/`

| # | Decision | Default | Rationale | Batch |
| --- | --- | --- | --- | --- |
| 1.1 | Module disposition | **Delete:** `App_Main/` (whole dir), `search_agent/main.py`, `search_agent/archiv/`, `extract_agent/{auto_pdf_downloader,add_full_text_from_pdfs,rag_chunker,rag_retriever}.py`, `Screening_Agent/screening_main.py`, `Screening_Agent/review_config_Evaluation.json`, `export_graph.py`, per-package READMEs. **Move:** `Orchestration/` → `src/graph/`, `Backend/` → `src/api/`, `search_agent/{agent,api_client,schemas,new_main}` → `src/pipeline/search/`, `Screening_Agent/{screening_agent,screening_schemas}` → `src/pipeline/screening/`, `extract_agent/document_processing_node.py` → `src/pipeline/ingestion/` (split: `node.py` orchestration, `pdf.py` resolve/download/parse, `chunking.py`, `retrieval.py`), `extract_agent/{rag_extraction_main,extraction_schemas}.py` → `src/pipeline/extraction/` (CLI/`sys.path` scaffolding stripped on move), `ui_app.py` → `src/ui/app.py`, `tracing.py` → `src/llm/tracing.py`, `Screening_Agent/testdaten/review_config.json` → `tests/fixtures/`. **Modify:** `Dockerfile.backend` (CMD, line 24), `Dockerfile.frontend`, `docker-compose.yml`, `.dockerignore`, `CLAUDE.md`, `README.md`. **New:** `src/db/` (models, migrations) | The live graph's imports define what moves; everything else is dead weight; phantom filenames from the stale legacy list are removed (M14) | 1 |
| 1.2 | Batch shape | Three batches as in the batch plan; Batch 1 = three commits (seam, move, delete), each green | R3: one move-and-rewrite state avoids the dual-module-identity bugs of a package-by-package hybrid | all |
| 1.3 | Import root | `src` is a regular package: imports are `from src.pipeline.search import ...`, uvicorn target is `src.api.main:app`, pytest runs from the repo root with `pythonpath = ["."]`; no editable install | Zero-config, matches the plan's literal layout, one convention for code, tests, and Docker (M15) | 1 |
| 1.4 | `pipeline/` submodules | `search`, `screening`, `ingestion` (with `retrieval.py` inside), `extraction`; the `store` module and the retrieval/ingestion node split arrive in Phase 2b | Phase 1 keeps the v1 node shape: the ingestion node persists chunks, then runs per-field retrieval and fills `retrieved_chunks_by_field` in state exactly as v1 did (M17) | 1 |

### 2. Restart behaviour without a checkpointer

| # | Decision | Default | Rationale | Batch |
| --- | --- | --- | --- | --- |
| 2.1 | `runs` columns | `id` uuid PK (returned as `job_id`), `user_id` FK NOT NULL, `review_id` FK NOT NULL (R5), `status` text + CHECK, `current_step` text, `status_message` text, `result` jsonb, `created_at`, `updated_at`, `finished_at` | The columns v1's wire contract and the restart test actually need (B2) | 2a |
| 2.2 | Status enum | `pending → running → completed \| failed`, plus `interrupted` set only at startup; the background task flips `pending → running` when it starts | Smallest set distinguishing "crashed mid-run" from "finished" | 2a |
| 2.3 | Per-step updates | The runner updates `current_step`, `status_message` and the payload fields in `result` after every `astream` step, exactly as v1 updates `JOBS`; `result` is defined as exactly the `GET /status` payload (so it duplicates retrieved chunk text until Phase 2b's tables replace it — accepted, N2) | Mid-run progress is part of the v1 contract, not an optional extra (B2) | 2a |
| 2.4 | Status → response mapping | `GET /status/{job_id}` composes v1's `ResearchResponse` (which has no `status` field): `pending`/`running` → stored `current_step`/`status_message` + partial payload; `completed` → `current_step="completed"` + full payload; `failed` → `current_step="error"`, message `"Pipeline failed: ..."`; `interrupted` → `current_step="interrupted"` (new value), message telling the user to start a new run; unknown id → 404 | One mapping table makes "unchanged wire contract" verifiable (B2) | 2a |
| 2.5 | Startup marking | FastAPI lifespan runs `UPDATE runs SET status='interrupted' WHERE status IN ('pending','running')` | Single statement, no scanning logic | 2a |
| 2.6 | UI polling | `ui_app.py` stops polling on HTTP 404 and on `current_step ∈ {completed, error, interrupted}` | Fixes the forever-404 loop; keyed on exactly the terminal set from 2.4 | 2a |
| 2.7 | Integration tests | pytest `integration` marker, run locally (`make integration`) against docker-compose Postgres, fake LLM. Restart test: simulate in-process — tear down the app, build a second instance on the same DSN, invoke the lifespan, assert completed runs survive and `pending`/`running` rows turn `interrupted`. Duplicate-run and duplicate-DOI tests use the committed fixture. The literal API+Postgres `docker compose restart` check is a local script run at phase exit | R2: stays inside the frozen plan's CI scope; in-process simulation is deterministic where a subprocess restart is flaky (M7) | 2 |
| 2.8 | Provenance envelope | `result` starts with `{"provenance": {"models": {role: name}, "prompt_versions": {role: v}, "profile": ...}}`, written at run start from the resolved settings | Phase 2a compares models while results still live in `runs.result`; without this, baseline and candidate runs are indistinguishable (M12, I2) | 2a |

### 3. Data model

| # | Decision | Default | Rationale | Batch |
| --- | --- | --- | --- | --- |
| 3.1 | Paper upsert algorithm | Normalization: lowercase, strip `https://doi.org/`, `http://doi.org/`, `https://dx.doi.org/`, `http://dx.doi.org/`. In one transaction: SELECT by normalized DOI OR `openalex_id`; then INSERT or UPDATE. Merge rule: first-seen `openalex_id` wins; `doi` is filled in when it first appears. Both unique columns stay (`doi` nullable). No single `ON CONFLICT` statement — two unique keys cannot share one | Handles both collision cases: two OpenAlex records sharing a DOI, and a paper stored DOI-less that later reappears with one (M4) | 2b |
| 3.2 | Ingestion status | `papers.ingestion_status`: `pending, downloaded, chunked, pdf_unavailable, failed` + `last_error` text. Policy: a later run re-attempts every non-`chunked` status; the extra states are observability-only. Skip condition for `chunked`: `embedding_model` matches settings AND `chunker_version` is current | Re-attempt-on-next-run cannot wedge a paper; the version key makes the 2a re-embed and 2b re-chunk a one-constant bump (M5, I4, N3) | 2b |
| 3.3 | Chunk idempotency | Chunk insertion and `ingestion_status='chunked'` commit in one transaction; any re-attempt first deletes the paper's existing chunks in that same transaction | "One chunk set per paper" is then true by construction, even after a mid-chunking crash (M5) | 2b |
| 3.4 | BibTeX fields | `papers.authors` jsonb (ordered display names — already captured by search) and `papers.venue` text. Venue is **new, behaviour-neutral code** in the search formatting loop (`primary_location.source.display_name`); it must be captured at search time or backfilled later, which is why it gets a column now while `section` does not (N7) | Needed for Phase 3 BibTeX; the asymmetry with 4.3 is deliberate and owned | 1 (search output), 2a (columns) |
| 3.5 | Screening decision values | v1's literal strings `include, exclude, uncertain` plus the `failed` bucket — recorded as a documented convention for Phase 2b; no table, no column, no DDL in Phase 1 | Mirroring v1 means using v1's actual strings, not renamed ones (N4) | 2b (convention only) |
| 3.6 | `reviews.criteria` shape | jsonb mirroring v1's `ResearchRequest`: `{"inclusion": [str], "exclusion": [str], "min_year": int, "target_output_count": int, "additional_info": str\|null}`. `target_output_count` keeps its v1 name and meaning (search fetch size, default 25); the plan's `target_included` (Loop 1's included-paper count) is a different number arriving in Phase 2b | The earlier draft omitted `additional_info` and renamed `target_output_count` into a semantically different Phase 2b term (M8) | 2a |
| 3.7 | Provenance convention | Every stored LLM output carries `model`, `prompt_version`, `created_at`. Phase 1's only carrier is the `runs.result` envelope (2.8). The "current row = latest `created_at`" view rule is deferred to the Phase 2b design, where its tables exist | Fix the convention now, build the view where it has something to view (M12) | 2a |
| 3.8 | Vector column | `chunks.embedding vector(384)`, `embedding_model` text, `chunker_version` text; no index in Phase 1; trigger for HNSW: >100k chunks or p95 per-paper retrieval >200 ms | A few thousand chunks scan fine; the trigger is measurable | 2a (DDL), 2b (use) |
| 3.9 | `user_id` | NOT NULL on `reviews` and `runs`, filled with the seeded `local` user (`email = "local@localhost"`), created by an Alembic data migration | D3; NOT NULL from day one avoids a backfill migration (M11, N9) | 2a |
| 3.10 | Enum representation | text columns + CHECK constraints, no native Postgres enum types | Altering a CHECK is one migration; altering a native enum is a headache — the simple option (N4) | 2 |
| 3.11 | Migrations | Compose uses `pgvector/pgvector:pg17` with a named data volume (CI's unit tests need no database at all). The first migration runs `CREATE EXTENSION IF NOT EXISTS vector`; migration files import `pgvector.sqlalchemy.Vector` explicitly. Runner: `make migrate` (`alembic upgrade head`) locally and in compose usage; the integration-test session fixture runs it; the API does **not** auto-migrate (the plan gives Phase 4 the migrations-before-API mechanism) | Every consumer of a migrated schema is named; plain `postgres` images fail on the extension (M11) | 2a |

### 4. Ingestion and chunks

| # | Decision | Default | Rationale | Batch |
| --- | --- | --- | --- | --- |
| 4.1 | Paper contract | Add `openalex_id`, `pdf_url`, `venue` to the search output schema; fields are optional-with-default on `ResearchPaper` so old fixtures keep validating; consumers updated together: `Backend/schemas.py`, `ui_app.py`, `screening_schemas.ResearchPaper` | Removes the DOI-only re-lookup that silently skips DOI-less papers; the ripple is named, not implied (N8) | 1 |
| 4.2 | PDF resolution | Ingestion downloads the stored search-time `pdf_url` first; on failure it falls back to v1's broader candidate lookup (`oa_url`, all locations) before marking `pdf_unavailable` | Softens the behaviour change and lowers the `pdf_unavailable` rate (M1a) | 2b |
| 4.3 | Chunking | Per page: 1200-character windows within each page, no overlap. `page` 1-based, `ordinal` per paper, whitespace-only pages skipped, sub-1200 page tails kept as short chunks | Page-aware evidence is a Phase 1 must; the four micro-decisions are stated, not left to the implementer (N1) | 2b |
| 4.4 | Partition invariant | A unit test asserts at ingestion that concatenating a page's chunks reconstructs the page text exactly; documented as Phase-1-only, retired when overlap arrives. No `char_start`/`char_end` columns | Locks in the property that makes the 2b re-chunk a pure DB+embedding operation, no re-download; columns would be speculative now (I3) | 2b |
| 4.5 | Section labels | Not stored; no column reserved | Loop 2 is conditional and section targeting was dropped; a nullable column later is a cheap migration | — |
| 4.6 | PDF storage | Files keyed `{paper_id}.pdf` in the existing `pdfs_auto` volume; skip download when the file exists **and starts with `%PDF`** (v1's magic-byte check) | Kills title collisions and re-downloads without trusting truncated files from a killed run (N9) | 2b |
| 4.7 | Retrieval | pgvector cosine similarity, always filtered by `paper_id`, top-5 per field, reusing `FIELD_QUERIES`; lives in `src/pipeline/ingestion/retrieval.py`; SQL `LIMIT k` returns fewer rows for small papers — the FAISS `-1` edge case is gone by construction (register entry V5) | Reproduces v1's per-paper retrieval in the shared store; the stage has a named home (M17) | 2b |

### 5. LLM layer

| # | Decision | Default | Rationale | Batch |
| --- | --- | --- | --- | --- |
| 5.1 | Async scope | Async-only `get_llm(role)` returning an Instructor-patched `AsyncOpenAI`. Facts: **search is the only sync LLM call site**; extraction is already async — its defect is a client built at module import time, which becomes lazy construction inside `get_llm`. `search_node` becomes `async def`; the OpenAlex `requests` paging loop is wrapped in `asyncio.to_thread` (the pattern v1 already uses for download/parse/embed) so it never blocks the event loop. No HTTP library changes in Phase 1 | One client style without freezing `/status` polling during a search (M2) | 1a |
| 5.2 | Tracing | `maybe_wrap_openai` moves unchanged into `src/llm/tracing.py` | It works; moving beats rewriting | 1a |
| 5.3 | Retries | No tenacity for the LLM path: `AsyncOpenAI(max_retries=3)` inside `get_llm`, Instructor `max_retries=2` per call, uniform across roles. The screening agent's hand-rolled retry loop is removed in the port (register entry V6). Search's fallback to a tokenized query is preserved, firing after SDK retries are exhausted. No special 429 code — local Ollama never emits it | Avoids stacking five retry layers into 6+ attempts per paper on a fanless laptop (M6) | 1a |
| 5.4 | Roles | `get_llm` serves exactly `search`, `screening`, `extraction` and raises on unknown roles; `get_embedder()` is separate. `router`/`summary`/`judge` are documented role names, not config entries | Unused config is untestable; adding a field later is one line (N5) | 1a |
| 5.5 | Fake surface (`test` profile) | (1) Fake LLM: a registry keyed by `response_model` type whose values are a canned instance **or** a `Callable[[messages], instance]`; the canned screening decision is `include` (otherwise ingestion and extraction are never exercised); mixed buckets for integration tests via sentinel tokens in fixture abstracts, e.g. `[FAKE:EXCLUDE]`. (2) A stubbed OpenAlex client returning the committed fixture. (3) Two fixture PDFs (2–3 pages each) read from a local path, so page-aware chunking is exercised. (4) `get_embedder()` returns a deterministic 384-dim fake — CI never downloads MiniLM; the real embedder runs in the optional live smoke only | The end-to-end run touches network in three places, not one; faking only the LLM leaves CI non-deterministic (B1, I5) | 1a |
| 5.6 | Settings | Pydantic Settings from env/`.env`: `profile` (`local`/`test`), `ollama_base_url`, model per wired role, `embedding_model`, `database_url`, `openalex_email` (**required, no default** — removes the hardcoded fallback at `new_main.py:16`), LangSmith switch, PDF directory. Replaces the hardcoded model at `Orchestration/nodes.py:62`. Documented URL defaults: `localhost:11434` native, `host.docker.internal:11434` in compose; `.env.example` lists every setting | Every hardcoded value the review flagged, itemized to its call site (N9, N10) | 1a |
| 5.7 | Prompts | v1's inline prompts move byte-identical into `src/llm/prompts/` as versioned files with `PROMPT_VERSION = "v1"` per role | The plan mandates versioned prompt files and 3.7 needs `prompt_version` values; byte-identical means zero behaviour change (M10e) | 1a |

### 6. Tests and CI

| # | Decision | Default | Rationale | Batch |
| --- | --- | --- | --- | --- |
| 6.1 | Order | Batch 0 (tests + CI) precedes any code moves; its check is "unit tests green in CI" — the fake end-to-end run starts in commit 1a, where its seam exists | R1: a safety net first, but only the part that can actually run before the seam (B1) | 0 |
| 6.2 | Test repair | Repoint the config fixture to `testdaten/review_config.json` (the path the test names does not exist); fix the duplicate `screening_schemas` import; temporary `conftest.py` path shim for collection, removed when tests move to `tests/` in commit 1b | Repair in place first; the shim is declared throwaway (M15, N9) | 0 |
| 6.3 | Fixtures | Trimmed `tests/fixtures/search_results.json` (3–5 papers) including the two-OpenAlex-IDs-one-DOI pair and the new contract fields; two small fixture PDFs | The gitignored full file would fail CI; the duplicate-DOI exit test needs its fixture named (M4, M10d) | 0 |
| 6.4 | Dropped tests | Only `test_screening_main_calls_protocol_helper` (reads the deleted file's source); `test_screen_file_with_protocol_signature` and `test_review_config_round_trip` are kept | The other two target moved-not-deleted code and a pure fixture round-trip (M13) | 0 |
| 6.5 | Year-prefilter gap | Not wired into the graph (`pre_excluded=[]` stays); documented as known v1 behaviour for the Phase 2a baseline | Phase 1 must not change behaviour, even to fix an oddity | — |
| 6.6 | Node-level tests | Fake-LLM unit tests for the screening and extraction nodes (not just the e2e smoke), landing with the seam in commit 1a | Required by the inputs; the e2e run is not a node test (M10c) | 1a |
| 6.7 | Golden transcript | At the end of commit 1a, capture the fake e2e run's final state JSON as a committed artifact; later commits and batches diff against it with an allow-list = the deviation register. Regenerating it is a deliberate, reviewed step | Unintended behaviour drift fails CI instead of surfacing in the Phase 2a baseline (I1, M1) | 1a |
| 6.8 | Smoke definition | "The system runs" = graph compiles + fake e2e passes (from 1a) + compose serves `GET /health` (added in 1b, checked in CI from 2b after image build with a dummy `OLLAMA_BASE_URL`, backend + Postgres only) | Codifies the plan's definition with the endpoint it needs — v1 has no `/health` (M16) | 1–2 |
| 6.9 | CI | GitHub Actions: ruff (from 1b) → unit tests (fake LLM, fake embedder — no model downloads) → image build (buildx layer cache) → compose `/health` check (from 2b); pip cached. Integration tests are **not** in CI (R2) | The frozen plan's CI scope, in dependency order, with the cost items named (M16) | 0→2 |
| 6.10 | Eval snapshot | Both gitignored `search_results.json` files copied to `eval/snapshots/v1/` (renamed `screening_search_results.json`, `extract_search_results.json`), retrieval date recorded in `eval/snapshots/v1/README.md` | The plan's checklist item gets a concrete destination (M10b) | 0 |

### 7. Working agreements

* After each core task (ingestion, LLM layer/settings, data model), a 5–10 line
  plain-language explanation of how the code works and why, appended to
  `docs/notes/phase1_explanations.md`.
* Dependencies (project-wide): add `sqlalchemy`, `alembic`, `pgvector`, `psycopg[binary]`,
  `pydantic-settings`, `ruff`; remove `faiss-cpu` (Batch 2b); keep `sentence-transformers`;
  keep `libgomp` in the image until a build without it passes the smoke check.
* `Makefile` targets `up`, `migrate`, `test`, `integration` keep agent sessions
  reproducible.

## Declared deviations from v1 (the register)

The Phase 2a baseline is measured against the system *with* these changes; everything else
is behaviour-identical, enforced by the golden transcript (6.7).

| ID | Change | v1 behaviour | Phase 1 behaviour | Why |
| --- | --- | --- | --- | --- |
| V1 | PDF URL source | Re-resolved at ingestion by DOI with a broad candidate heuristic; DOI-less papers silently skipped | Search-time `pdf_url` first, v1's candidate lookup as fallback; DOI-less papers ingestible | Fixes silent drops; fallback keeps success rates close (M1a) |
| V2 | Chunk boundaries | All pages joined, continuous 1200-char windows | Per-page 1200-char windows with page + ordinal | Owner-mandated: page-level evidence (4.3) |
| V3 | PDF caching | Re-downloaded every run, title-keyed (collisions) | Keyed by paper id, skipped when present and `%PDF`-valid | Fixes collisions and waste (4.6) |
| V4 | Mid-pipeline results storage | In-memory, lost on restart | Postgres `runs` row, per-step updates | The point of Phase 1; wire contract unchanged (2.3–2.4) |
| V5 | Retrieval edge case | FAISS returns `-1` for <5 chunks; `chunks[-1]` silently duplicates the last chunk | SQL `LIMIT 5` returns what exists | The v1 behaviour was a bug (4.7) |
| V6 | LLM retry path | Screening: hand-rolled 2-retry loop with sleeps; search: instant fallback to tokenized query; SDK defaults on top | Uniform SDK `max_retries=3` + Instructor 2; hand-rolled loop removed; search fallback after retries | One declared retry policy instead of five stacked layers (M6) |

Behaviour-neutral additions (not deviations): `openalex_id`, `pdf_url`, `venue`, `authors`
carried in the search output; `GET /health`; provenance envelope in `runs.result`.

## Goals vs. Non-Goals

* **In-Scope Goals** — the Phase 1 checklist of `docs/plan_v2.md` §10, mapped to decisions:
  eval snapshot copy → 6.10; test repair + smoke + CI → 6.1–6.9; new layout + deletions +
  docs correction → 1.1–1.4, commit 1c; settings + `get_llm` + profiles + OpenAlex email →
  5.1–5.7; Postgres + models + migration → 2.1, 3.1–3.11; ingestion (upsert, page-aware
  chunking, pgvector) → 4.1–4.7; run status in Postgres + interrupted marking → 2.2–2.8.
* **Out-of-Scope Non-Goals:** checkpointer (Phase 3, D1); new models (Phase 2a, D2);
  multi-user/auth (backlog, D3); `screenings`/`extractions` tables and the store node
  (Phase 2b); chunk overlap and reranking (Phase 2b); section labels (not stored, 4.5);
  integration tests in CI (R2); auto-migration on API start (Phase 4); any plan-level
  change — the plan is frozen, plan-level ideas go to `docs/backlog.md` (18 candidates
  from this review appended there).

## Alternatives Weighed

1. **Atomic one-commit migration** — rejected by author: one large, risky change; batches
   with a runnable system after each are preferred (1.2).
2. **Package-by-package migration** (whether as batches or as per-package commits with
   shims) — rejected by author (R3): dual module identity during the hybrid reproduces
   exactly the duplicate-`ResearchPaper` class of bug that 6.2 fixes.
3. **Batch 0 monkeypatching of the three v1 client sites** to get an early e2e — rejected
   by author (R1): throwaway scaffolding; the e2e starts where its seam exists.
4. **Integration tests in CI** — rejected by author (R2): deviates from the frozen plan's
   "CI runs only lint and unit tests"; they run locally instead.
5. **Async SQLAlchemy engine** — rejected by author (R4): changes every repository
   signature; sync engine + `asyncio.to_thread` is the simple-and-robust option.
6. **Sync + async dual support in `get_llm`** — rejected (5.1): two code paths at the only
   LLM seam.
7. **tenacity wrapper at the seam** — rejected (5.3): stacks on the SDK's, Instructor's and
   v1's own retry layers; the SDK's built-in retries suffice.
8. **Keeping FAISS next to Postgres** — rejected in the frozen plan (§5.5).
9. **External-ID mapping table for paper identity** — rejected unless duplicates are
   measured to be common (inputs §3, Stage 8 rule); the two-key upsert covers the known
   case (3.1).
10. **Retry counter / backoff policy on ingestion** — rejected (3.2): re-attempt on next
    run is simpler and cannot wedge a paper.
11. **Native Postgres enum types** — rejected (3.10): text + CHECK migrates with less
    friction.
12. **Reserving a `section` column on `chunks`** — rejected (4.5): speculative; a nullable
    column later is cheap.
13. **`char_start`/`char_end` on chunks now** — deferred (4.4): the partition-invariant
    test preserves reconstructability without them; revisit with the 2b overlap design.
14. **Editable install / separate top-level packages** — rejected (1.3): `src` as a plain
    package is zero-config and matches the plan's layout literally.

## Analysis

Seven review lenses examined the previous revision of this brief against the frozen plan,
the collected inputs and the v1 code. The full deduplicated report (2 blockers, 17 majors,
10 nits, 5 ideas, 18 backlog candidates) is in
`docs/reviews/phase1_brainstorm_goldfish.md`; findings are cited above by its IDs. The
reviewers verified the brief's code claims line by line: most held, but three did not —
extraction was already async (its real defect being a client built at import time), the
deletion list named three files that do not exist, and dropping a whole test class would
have discarded two tests that remain valid. All three are corrected above.

The blockers were (B1) an undefined "fake-LLM end-to-end run" — the test profile faked
only the LLM while the run also touches OpenAlex, PDF downloads and a HuggingFace model
download, and the seam the fake plugs into did not exist in Batch 0 — resolved by R1 and
the full fake surface in 5.5; and (B2) a `runs` design that could not reproduce v1's
`/status` wire contract — resolved by the column list, per-step update rule and status
mapping in 2.1–2.4.

The recurring contradiction was claiming "unchanged v1 behaviour" while five defaults
changed observable behaviour. The resolution is the deviation register: the changes stay
(each fixes a defect or is owner-mandated), the claim is qualified, and the golden
transcript (6.7) turns the register into a CI check, so unintended drift fails a test
instead of surfacing in the Phase 2a baseline.

The remaining majors were specification gaps a fully prescriptive design must close, each
now closed in its section: the two-key upsert algorithm and merge rule (3.1), transactional
chunk idempotency with `chunker_version` (3.2–3.3), the retry-stacking resolution (5.3),
the `reviews` writer and the corrected criteria shape (R5, 3.6), Alembic/pgvector
mechanics and the seeded user (3.11), packaging and tooling config (1.3, Batch 0),
retrieval's module home (1.4, 4.7), provenance's Phase 1 carrier (2.8), `/health` and CI
cost control (6.8–6.9), and the five checklist items the earlier draft had not mapped
(docs correction, eval snapshot, node-level tests, duplicate-DOI fixture, prompt
versioning).

**Ideal Final Result** (inventive lens): Phase 1 changes nothing a user or the Phase 2a
baseline can observe, while every future change — model swap in 2a, re-chunk in 2b —
becomes a recorded, mechanically testable operation. Three adopted ideas carry this:
the golden transcript (6.7), the provenance envelope (2.8), and the page-partition
invariant (4.4), which makes the Phase 2b overlap experiment a pure
database-plus-embedding operation with no re-download.

**Plan-level findings** stayed out of Phase 1 per the freeze: the report's 18 backlog
candidates (OpenAlex client hygiene, structured logging ownership, result retention,
concurrent-run safety, plan-wording amendments and others) go to `docs/backlog.md`.

## Key Decisions & Staging for Next Steps

Carried into `/egm-draft` as settled:

1. Three batches (safety net / seam-then-layout / Postgres), Batch 1 as three green
   commits, Batch 2 as two (R1, R3).
2. CI = lint + unit (fake LLM, fake embedder) + image build + compose health check;
   integration tests local-only (R2).
3. Sync SQLAlchemy engine via `asyncio.to_thread`; async-only `get_llm`; OpenAlex HTTP
   stays sync `requests` in `to_thread` (R4, M2).
4. `/start_pipeline` writes `reviews`; `runs.review_id` NOT NULL (R5).
5. The `runs` wire-contract mapping (2.1–2.6) and provenance envelope (2.8).
6. The paper upsert algorithm and merge rule (3.1); transactional chunking with
   `chunker_version` (3.2–3.3); the deviation register with golden-transcript enforcement.
7. The full fake surface (5.5) and the test/fixture plan (6.1–6.10).
8. Deliverables for the draft: the design doc must contain the module disposition table
   (1.1), the schema DDL-level column list, the status mapping table, the fake-surface
   contract, the batch-by-batch commit plan, and the deviation register.
