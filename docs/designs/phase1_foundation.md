# Phase 1 — Foundation

*   **Author:** Mohamed Elsayed
*   **Status:** Approved
*   **Date:** 2026-11-16

--------------------------------------------------------------------------------

## Overview

Phase 1 turns the v1 literature-review prototype into a foundation the rest of the
v2 plan can build on, without changing what the system does. The v1 linear pipeline
(search → screening → ingestion → extraction) keeps its behaviour, its models
(`qwen2.5-coder:7b` on local Ollama, `all-MiniLM-L6-v2` in-process) and its two HTTP
endpoints (`POST /start_pipeline`, `GET /status/{job_id}`), but moves into a `src/`
package layout, gets one `get_llm(role)` seam for every LLM call, and stores papers,
chunks and run status in Postgres with pgvector instead of an in-memory dict and
per-paper FAISS indexes. Repaired tests, a fake-LLM end-to-end run, and CI make
"the system runs" a checked property instead of a hope.

The work lands in three batches — safety net, seam-then-layout, Postgres — each
leaving a runnable system. Behaviour is identical to v1 except six declared,
register-tracked deviations (each fixes a defect or is owner-mandated); a golden
transcript test enforces that nothing else drifts. The design follows the decisions
in `concepts_brief.md` (owner rulings R1–R5) and the frozen plan `docs/plan_v2.md`.

## The Problem

v1 works as a demo and fails as a foundation:

*   **Nothing survives a restart.** Job state lives in an in-memory dict in the
    FastAPI process; papers, chunks and results are gone when it stops, and the
    Streamlit UI polls a dead job's 404 forever. v2's persistent library (plan
    feature "Persistent library", Phase 1) is impossible on this base.
*   **Papers are not reusable.** Each run builds throwaway per-paper FAISS indexes;
    the same paper is re-downloaded, re-parsed and re-embedded on every run, and
    chunks carry no page information, so later phases cannot cite evidence pages.
*   **The layout blocks change.** Code sits in flat root packages with `sys.path`
    workarounds, three independently built LLM clients (one constructed at module
    import time), hardcoded model names and a hardcoded contact email. Swapping a
    model per role — the whole point of the Phase 2a benchmark — would mean editing
    three call sites.
*   **Quality is unmeasured and unprotected.** 3 of 11 tests fail, one fixture is
    gitignored so CI could never pass, and there is no CI. Phase 2a wants to measure
    a baseline; today there is no mechanism to even keep behaviour stable while
    refactoring.

Phase 1 solves exactly these four problems and defers everything else (new models,
pipeline loops, chat, deployment) to later phases.

## Goals

Measurable, from the plan's Phase 1 exit criteria and the brief:

*   **G1 — Idempotent library.** Running the pipeline twice with the same question
    and criteria leaves one `papers` row and one set of `chunks` per paper
    (including the known case of two OpenAlex records sharing one DOI), proven by
    an automated integration test.
*   **G2 — Restart survival.** After restarting the API and Postgres, every
    completed run's results and all library rows are still present; unfinished runs
    are marked `interrupted` and the UI stops polling them. Proven by an automated
    integration test.
*   **G3 — Unchanged behaviour at the seam.** The v1 wire contract
    (`ResearchResponse`, per-step progress included) is preserved; behaviour equals
    v1 except the six register-tracked deviations, enforced by a golden-transcript
    test with the register as its allow-list.
*   **G4 — One LLM seam.** `get_llm(role)` / `get_embedder()` are the only places
    LLM and embedding clients are built; the `test` profile makes both return
    fakes. Together with the fixture OpenAlex and PDF replacements the test
    fixtures install and `REPOSITORY_BACKEND=memory`, an end-to-end run passes
    with no network, no model downloads and no database.
*   **G5 — Green CI.** The existing screening tests pass under the new layout; CI
    runs ruff + unit tests (fake surface) + image build + a compose `/health`
    check, all green.
*   **G6 — Phase 2a readiness.** Page-aware chunks with ordinals, model and
    prompt-version provenance on every run, and a committed eval snapshot with its
    retrieval date — the hooks Phase 2a's baseline measurement needs.

## Non-Goals

*   **No checkpointer** — Phase 3 (decision D1); Phase 1 only guarantees completed
    results survive.
*   **No new models** — Phase 2a (decision D2); Phase 1 changes code, not models.
*   **No multi-user or auth** — backlog (decision D3); one seeded `local` user,
    `user_id` NOT NULL from the start.
*   **No `screenings`/`extractions` tables and no store node** — Phase 2b; until
    then run output lives in `runs.result`.
*   **No chunk overlap, reranking, or section labels** — Phase 2b experiments or
    dropped; Phase 1 chunks are page-aware, zero-overlap, with a tested
    page-partition invariant that keeps the 2b re-chunk cheap.
*   **No integration tests in CI** — owner ruling R2; they run locally and at phase
    exit.
*   **No auto-migration inside the API** — the API never migrates by itself;
    local runs use `make migrate`. The compose stack runs a one-shot `migrate`
    service (`alembic upgrade head`) that the backend waits for; a
    migrations-before-API mechanism beyond that is a Phase 4 design item.
*   **No pipeline changes** — no loops, no subgraph split, no year-prefilter wiring
    (`pre_excluded=[]` stays as in v1); the graph shape is untouched.
*   **No plan changes** — the plan is frozen; plan-level ideas went to
    `docs/backlog.md` (#15–#31).

## Open Questions

None at drafting time. The brainstorm (Goldfish review + owner rulings R1–R5)
settled all previously open sub-decisions; see `concepts_brief.md`.

## Critical User Journeys (CUJs)

### CUJ 1: Repeat run reuses the library

*   **Given**: A clean database, the stack up via `docker compose up` and
    `make migrate`, Ollama reachable.
*   **When**: The user starts the same review twice through the v1 UI (same
    question, criteria, year).
*   **Then**: Both runs complete with v1-shaped results; each paper exists once in
    `papers` with one chunk set; the second run skips download and chunking for
    already-chunked papers.

### CUJ 2: Restart does not lose finished work

*   **Given**: One completed run and one run mid-pipeline.
*   **When**: API and Postgres restart.
*   **Then**: The completed run's `GET /status/{job_id}` returns its full result;
    the unfinished run returns `current_step="interrupted"` with a message to start
    a new run; the UI shows both states and stops polling.

### CUJ 3: Developer verifies the system without a model

*   **Given**: A fresh checkout, no Ollama, no network beyond pip.
*   **When**: `make test` (and CI on push).
*   **Then**: Unit tests and the fake end-to-end smoke run pass using the fake
    surface; `make integration` against local Postgres proves G1 and G2.

## Technical Plan (Architecture)

### Target layout

```text
src/
  api/        FastAPI app (moved Backend/): endpoints, schemas, run lifecycle
  graph/      LangGraph graph + state (moved Orchestration/)
  pipeline/
    search/     agent, api_client, schemas, new_main (moved search_agent/)
    screening/  screening_agent, screening_schemas (moved Screening_Agent/)
    ingestion/  node.py, pdf.py, chunking.py, retrieval.py (split from
                extract_agent/document_processing_node.py)
    extraction/ node + schemas (moved rag_extraction_main, extraction_schemas)
  llm/        settings.py, client.py (get_llm/get_embedder), tracing.py,
              fake.py (test profile), prompts/ (versioned files, PROMPT_VERSION)
  db/         SQLAlchemy models, session, repository.py (Postgres),
              memory_repository.py (in-memory), records.py (shared constants,
              NewChunk, normalize_doi), Alembic migrations
  ui/         Streamlit app (moved ui_app.py)
scripts/      restart_check.sh, fake_run.py
tests/        unit + integration (marker: integration), fixtures/
eval/snapshots/v1/   frozen v1 search results + retrieval date
```

`src` is a regular package: imports are `from src.pipeline.search import ...`,
the uvicorn target is `src.api.main:app`, pytest runs from the repo root with
`pythonpath = ["."]`. No editable install.

### Runtime shape

```text
Streamlit UI ──poll──► FastAPI (src/api)
                          │  POST /start_pipeline: insert reviews row + runs row
                          │  GET  /status/{job_id}: compose ResearchResponse from runs
                          │  GET  /health: plain 200
                          ▼
                   LangGraph graph (src/graph) — v1 shape, unchanged nodes
                 search → screening → ingestion(+retrieval) → extraction
                          │                         │
                          ▼                         ▼
                 LLM layer (src/llm)          db layer (src/db)
             get_llm(role) · get_embedder()   sync SQLAlchemy engine
                          │                         │
                          ▼                         ▼
                 Ollama (localhost:11434)     Postgres + pgvector (Docker)
```

Async model: nodes are `async def`; blocking work (OpenAlex `requests` paging,
PDF download/parse, embedding, all database access) runs through
`asyncio.to_thread`, so `/status` stays responsive during a run (rulings R4, M2).
No HTTP library changes in Phase 1.

### LLM layer

`get_llm(role)` is the only constructor of LLM clients: it returns an
Instructor-patched `AsyncOpenAI` pointed at Ollama, wrapped by
`maybe_wrap_openai` (tracing, moved unchanged), with SDK `max_retries=3` and
Instructor `max_retries=2` (set once on the returned client, so call sites pass no
retry count), uniform across the wired roles `search`,
`screening`, `extraction` (unknown roles raise). `get_embedder()` is separate.
v1's three scattered clients — including extraction's module-import-time client —
are replaced by call-time `get_llm` lookups. Prompts move byte-identical into
`src/llm/prompts/` with `PROMPT_VERSION = "v1"` per role. Settings
(pydantic-settings, validated at startup) hold the profile (`local`/`test`),
Ollama URL, model per role, embedding model, repository backend
(`REPOSITORY_BACKEND`: `postgres` or `memory`), database URL (required only with
the `postgres` backend), required OpenAlex contact email, optional OpenAlex API
key, LangSmith switch, and PDF directory — removing the hardcoded model in
`Orchestration/nodes.py:62` and email in `search_agent/new_main.py:16`.

The `test` profile swaps in the **fake surface**. Only the LLM and embedder seams
check the profile; the OpenAlex and PDF replacements are installed by the test
side (the pytest `fake_surface` fixture and `scripts/fake_run.py`), and the
repository is chosen by `REPOSITORY_BACKEND`, not by the profile. A process
started with `PROFILE=test` alone (for example the compose backend) therefore
still calls live OpenAlex and live PDF URLs and needs Postgres:

| Seam | `local` profile | `test` profile |
| --- | --- | --- |
| `get_llm(role)` | Instructor + Ollama | Fake LLM: registry keyed by `response_model` type, filled by the tests through `set_fake_answers` (`tests/fakes.py`); values are a canned instance or `Callable[[messages], instance]`; canned screening decision is `include`; mixed buckets via `[FAKE:EXCLUDE]`, `[FAKE:UNCERTAIN]` and `[FAKE:FAIL]` (raises, producing a `failed` paper) sentinels in fixture abstracts, handled in `tests/fakes.py` |
| `get_embedder()` | MiniLM in-process | Deterministic 384-dim fake (no HuggingFace download) |
| OpenAlex client | Live API | Stub (monkeypatched by the test side) replacing `OpenAlexClient.execute_retrieval`, returning raw work dicts from `tests/fixtures/openalex_works.json` (5 papers incl. the two-IDs-one-DOI pair) |
| PDF download | HTTP | Two committed 2–3-page fixture PDFs from a local path (monkeypatched by the test side) |
| `get_repository()` (from 2a/2b) | `REPOSITORY_BACKEND=postgres`: Postgres + pgvector | `REPOSITORY_BACKEND=memory`: [`memory_repository.py`](../../src/db/memory_repository.py), same functions, brute-force cosine retrieval over the fake embedder's vectors |

### Data model

All enums are text + CHECK constraints. Created by Alembic in Batch 2a against
`pgvector/pgvector:pg17` (first migration: `CREATE EXTENSION IF NOT EXISTS
vector`; a data migration seeds the `local` user, `email = "local@localhost"`).

| Table | Columns (key ones) | Notes |
| --- | --- | --- |
| `users` | `id`, `email` | one seeded `local` user |
| `reviews` | `id`, `user_id` FK NOT NULL, `question`, `criteria` jsonb, `created_at` | criteria mirrors v1 `ResearchRequest`: `{"inclusion": [...], "exclusion": [...], "min_year": int, "target_output_count": int, "additional_info": str\|null}` |
| `runs` | `id` uuid PK (= `job_id`), `user_id` FK NOT NULL, `review_id` FK NOT NULL, `status` CHECK (`pending/running/completed/failed/interrupted`), `current_step`, `status_message`, `result` jsonb, `created_at`, `updated_at`, `finished_at` | `result` = exactly the `GET /status` payload, starting with the provenance envelope `{"provenance": {"models": {...}, "prompt_versions": {...}, "profile": ...}}` |
| `papers` | `id`, `openalex_id` unique, `doi` unique nullable (normalized), `title`, `year`, `authors` jsonb, `venue`, `pdf_url`, `ingestion_status` CHECK (`pending/downloaded/chunked/pdf_unavailable/failed`), `last_error` | shared across reviews |
| `chunks` | `id`, `paper_id` FK, `page` (1-based), `ordinal` (per paper), `text`, `embedding vector(384)`, `embedding_model`, `chunker_version` | no index in Phase 1; HNSW trigger: >100k chunks or p95 per-paper retrieval >200 ms |

### Run lifecycle and the v1 wire contract

`POST /start_pipeline` inserts a `reviews` row and a `runs` row (`pending`),
returns `runs.id` as `job_id`, and schedules the background task, which flips the
row to `running` and then — after **every** `astream` step, exactly as v1 updated
`JOBS` — writes `current_step`, `status_message` and the payload fields into
`result`. On process start, the FastAPI lifespan runs one statement:
`UPDATE runs SET status='interrupted' WHERE status IN ('pending','running')`.

`GET /status/{job_id}` composes v1's `ResearchResponse` (no `status` field) plus
a `provenance` field carrying the run's provenance envelope, so the response
carries what `runs.result` stores:

| `runs.status` | Response |
| --- | --- |
| `pending` / `running` | stored `current_step` / `status_message` + partial payload |
| `completed` | `current_step="completed"` + full payload |
| `failed` | `current_step="error"`, `status_message="Pipeline failed: ..."` |
| `interrupted` | `current_step="interrupted"` (new value) + "start a new run" message |
| unknown id | HTTP 404 |

The UI stops polling on 404 and on `current_step ∈ {completed, error,
interrupted}` — fixing v1's forever-404 loop.

### Ingestion and retrieval

Per included paper, the ingestion node (v1 node shape preserved; the
retrieval/ingestion split is Phase 2b):

1.  **Upsert** (one transaction): normalize the DOI (lowercase; strip
    `https?://doi.org/` and `https?://dx.doi.org/`); SELECT by normalized DOI OR
    `openalex_id`, then INSERT or UPDATE. Merge rule: first-seen `openalex_id`
    wins; `doi`, `year`, `venue` and `pdf_url` fill in when they first appear
    (an existing non-empty value is never overwritten); `title` and `authors`
    keep their first-seen values. When the OpenAlex id and the DOI match two
    different rows, the lowest-id row is used and its `doi` stays unset, because
    setting it would violate the unique key. (Two unique keys — a single
    `ON CONFLICT` cannot express this.)
2.  **PDF**: skip if `{paper_id}.pdf` exists in the `pdfs_auto` volume and starts
    with `%PDF`; else download the stored search-time `pdf_url`, falling back to
    v1's broader candidate lookup before marking `pdf_unavailable`.
3.  **Chunk** (one transaction, delete-then-insert): per page, 1200-character
    windows, no overlap; whitespace-only pages skipped; short tails kept; then set
    `ingestion_status='chunked'`. Skip condition on later runs: `chunked` AND
    `embedding_model` matches settings AND `chunker_version` is current — so the
    Phase 2a re-embed and 2b re-chunk are a one-constant bump. A unit test asserts
    the partition invariant: concatenating a page's chunks reproduces the page.
4.  **Retrieve**: pgvector cosine similarity per `FIELD_QUERIES` field, always
    filtered by `paper_id`, top-5, filling `retrieved_chunks_by_field` in state as
    v1 did. SQL `LIMIT` replaces the FAISS `-1` edge case.

### Behaviour-change register and its enforcement

Six declared deviations from v1 (full table in `concepts_brief.md`): PDF-URL
source with fallback (V1), per-page chunk boundaries (V2), id-keyed PDF cache
(V3), Postgres-backed run state (V4), the FAISS `-1` fix (V5), and the unified
retry policy replacing v1's stacked/hand-rolled retries (V6). A **golden
transcript** — the fake e2e run's final state JSON, captured in Batch 1 commit 1a
before any package moves — is committed; a test diffs every later state against
it with the register as its allow-list, so an unintended behaviour change fails
CI instead of surfacing in the Phase 2a baseline.

### Test and CI architecture

*   **Unit + fake e2e** (CI and `make test`): fake surface only, no network, no
    model downloads; includes node-level tests for screening and extraction, the
    chunking partition test, and the golden-transcript diff.
*   **Integration** (`make integration`, local only — ruling R2): docker-compose
    Postgres, fake surface; G1 duplicate-run and duplicate-DOI tests; G2 restart
    test simulated in-process (tear down the app, build a second instance on the
    same DSN, invoke the lifespan, assert survivors and `interrupted` marking).
    The literal `docker compose restart` check is a local script in the phase
    exit checklist.
*   **CI** (GitHub Actions): ruff → unit tests → image build (buildx cache) →
    compose up (backend + Postgres, dummy `OLLAMA_BASE_URL`) → `GET /health`.
    Pip cached; nothing in CI needs HuggingFace or Ollama.

## Alternatives Considered

### Alternative A: Atomic one-commit migration

*   **Pros**: No hybrid state; one review of the whole move.
*   **Cons**: One large, risky change; a failure leaves nothing runnable to bisect.
*   **Reason for Rejection**: Rejected by author: batches with a runnable system
    after each are preferred (ruling on migration shape).

### Alternative B: Package-by-package migration (with re-export shims)

*   **Pros**: Smallest individual steps; each package reviewed in isolation.
*   **Cons**: Old and new module paths importable simultaneously — dual module
    identity reproduces exactly the duplicate-`ResearchPaper` Pydantic bug the
    test repair fixes; shim files are throwaway work.
*   **Reason for Rejection**: Rejected by author (R3): Batch 1 is one
    move-and-rewrite state in three commits; the runnable-system requirement holds
    per batch.

### Alternative C: Batch 0 monkeypatching of the three v1 client sites

*   **Pros**: A fake end-to-end run exists before any refactoring.
*   **Cons**: Throwaway scaffolding; cannot reach extraction's module-import-time
    client anyway without modifying the module it is meant to protect.
*   **Reason for Rejection**: Rejected by author (R1): Batch 0's check is "graph
    compiles + unit tests green"; the e2e run starts where its seam exists
    (commit 1a).

### Alternative D: Integration tests in CI (Postgres service container)

*   **Pros**: Restart and duplicate-run regressions caught on every push.
*   **Cons**: Deviates from the frozen plan ("CI runs only lint and unit tests");
    service containers cannot be restarted mid-job, so the restart test would be
    partly simulated anyway; flaky-CI risk from subprocess lifecycle management.
*   **Reason for Rejection**: Rejected by author (R2): integration tests run
    locally via `make integration` and at phase exit.

### Alternative E: Async SQLAlchemy engine

*   **Pros**: No thread hops; one async idiom end to end.
*   **Cons**: Async session/repository signatures everywhere; more concepts in
    play for the same single-user throughput; Alembic runs sync regardless.
*   **Reason for Rejection**: Rejected by author (R4): sync engine called via
    `asyncio.to_thread` is the simple-and-robust option.

### Alternative F: Sync + async dual support in `get_llm`

*   **Pros**: Call sites keep their current style; no async port of search.
*   **Cons**: Two code paths to build, test and trace at the only LLM seam.
*   **Reason for Rejection**: Rejected by author: async-only; search is the single
    sync call site and is ported with its blocking HTTP moved to
    `asyncio.to_thread`.

### Alternative G: tenacity retry wrapper at the seam

*   **Pros**: Central, configurable retry policy; tenacity is already a dependency.
*   **Cons**: Stacks on the OpenAI SDK's own retries, Instructor's validation
    retries, and v1's hand-rolled screening loop — worst case 6+ attempts per
    paper with compounding backoff on a fanless laptop.
*   **Reason for Rejection**: Rejected by author: one declared policy — SDK
    `max_retries=3` + Instructor `max_retries=2`; the hand-rolled loop is removed
    (register entry V6).

### Alternative H: Keep FAISS next to Postgres

*   **Pros**: No retrieval behaviour change at all; no pgvector dependency.
*   **Cons**: Two stores to back up and keep consistent; chunks not queryable or
    joinable; blocks the shared persistent library.
*   **Reason for Rejection**: Rejected in the frozen plan (§5.5): one Postgres +
    pgvector store for library, vectors and run status.

### Alternative I: External-ID mapping table for paper identity

*   **Pros**: Handles arbitrary future ID aliasing beyond DOI/OpenAlex.
*   **Cons**: A join on every paper lookup for a duplication rate nobody has
    measured; the one observed case is covered by the two-key upsert.
*   **Reason for Rejection**: Rejected by author (inputs §3, "drop unless
    measured"); revisit via backlog #19 if duplicates prove common.

### Alternative J: Retry counter / backoff policy on ingestion

*   **Pros**: Bounded retries for permanently broken PDFs.
*   **Cons**: Extra state and policy for a failure mode a re-attempt-per-run
    already handles; a counter can wedge a paper permanently.
*   **Reason for Rejection**: Rejected by author: re-attempt every non-`chunked`
    paper on the next run that includes it; `last_error` records why it failed.

### Alternative K: Native Postgres enum types

*   **Pros**: Database-enforced value sets with compact storage.
*   **Cons**: Every value change is an `ALTER TYPE` migration with ordering
    constraints; text + CHECK migrates with one constraint swap.
*   **Reason for Rejection**: Rejected by author: text + CHECK everywhere.

### Alternative L: Reserving a `section` column on `chunks`

*   **Pros**: Ready if Loop 2 ever targets Methods/Results sections.
*   **Cons**: Speculative — Loop 2 is conditional and section targeting was
    dropped from the plan; nothing would write the column.
*   **Reason for Rejection**: Rejected by author: a nullable column later is a
    cheap migration.

### Alternative M: `char_start`/`char_end` offsets on chunks now

*   **Pros**: Sub-page evidence highlighting without a future migration; offsets
    are not derivable once overlap exists.
*   **Cons**: Redundant while the zero-overlap partition invariant holds —
    offsets are reconstructible from `(page, ordinal)` order.
*   **Reason for Rejection**: Deferred by author: the partition-invariant test
    preserves reconstructability; revisit with the Phase 2b overlap design.

### Alternative N: Editable install / separate top-level packages

*   **Pros**: Conventional `pip install -e .` packaging; import names without the
    `src.` prefix.
*   **Cons**: Either generic top-level names (`api`, `graph`) colliding with the
    ecosystem, or install-step coupling for Docker, pytest and local runs.
*   **Reason for Rejection**: Rejected by author: `src` as a plain package is
    zero-config, one convention for code, tests and Docker, and matches the
    frozen plan's layout literally.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

One unified list, ordered by execution (Batch 0 → commits 1a, 1b, 1c, 2a, 2b).
A file's first entry sits under the step that first touches it and names the
later steps that touch it again; those later touches either get entries of
their own or are described in that first entry. No production code here —
signatures and schemas only.

### Batch 0 — Safety net

#### 0.1 `./Screening_Agent/test_screening.py` (Modify)

*   **Type / Scope**: Unit tests (repaired in place; moved in 1b)
*   **Proposed Changes**: Repoint the config fixture to
    `Screening_Agent/testdaten/review_config.json` (the path the test names does
    not exist); rewrite the test's flat imports to the package-qualified
    `Screening_Agent.screening_agent` / `Screening_Agent.screening_schemas` —
    the identity `screening_agent.py` itself uses — so Pydantic sees one
    `ResearchPaper` class; load search data from `tests/fixtures/search_results.json`
    instead of the gitignored file; delete only
    `test_screening_main_calls_protocol_helper` (reads the source of a file 1c
    deletes); keep the class's other two tests.

#### 0.2 `./Screening_Agent/conftest.py` (Dropped — not created)

*   **Type / Scope**: Test scaffolding (removed from the plan)
*   **Proposed Changes**: None. 0.4's `pythonpath = ["."]` already makes
    repo-root collection resolve 0.1's package-qualified imports; a shim that
    inserted `Screening_Agent/` into `sys.path` would re-create the dual module
    identity 0.1 removes.

#### 0.3 `./tests/fixtures/search_results.json`, `./tests/fixtures/openalex_works.json` (Create)

*   **Type / Scope**: Committed fixtures
*   **Proposed Changes**: The same 5 papers in two shapes.
    `openalex_works.json` holds them as raw OpenAlex work dicts (`id`, `doi`,
    `abstract_inverted_index`, `authorships`, `primary_location`,
    `best_oa_location`, …) and feeds the stub OpenAlex client (1a.4).
    `search_results.json` holds them in the formatted `{"papers": [...]}`
    shape, trimmed from the v1 output and extended with `openalex_id`,
    `pdf_url`, `venue`, `authors`; it feeds the screening tests. Roster: P1
    plain abstract (include), P2 `[FAKE:EXCLUDE]`, P3 `[FAKE:UNCERTAIN]`, P4
    `[FAKE:FAIL]`, P5 plain abstract (include). P1 and P5 are two OpenAlex
    records sharing one DOI, both included so the G1 duplicate-DOI upsert merge
    is exercised downstream.

#### 0.4 `./pyproject.toml` (Create)

*   **Type / Scope**: Build/tooling configuration
*   **Proposed Changes**: Project metadata; pytest config
    (`markers = ["integration"]`, `addopts = "-m 'not integration'"`,
    `pythonpath = ["."]`); ruff configuration (gate turned on in CI in 1b).
    `requires-python` matches the Dockerfile's Python base image; CI's
    `python-version` uses the same value.

#### 0.5 `./.github/workflows/ci.yml` (Create)

*   **Type / Scope**: CI pipeline
*   **Proposed Changes**: Batch 0: pip-cached unit-test job only. Grows in later
    steps (1b: ruff; 2b: image build + compose `/health` check). Integration tests
    are never added (R2).

#### 0.6 `./Makefile` (Create)

*   **Type / Scope**: Developer entry points
*   **Proposed Changes**: Targets `up` (compose), `migrate` (`alembic upgrade
    head`), `test` (unit + fake e2e), `integration` (marker run). Keeps agent
    sessions reproducible; targets become functional as their subjects land.
    `integration` assumes `make up` and `make migrate` have run; the test DSN
    comes from `DATABASE_URL`, defaulting to the compose service on
    `localhost:5432`.

#### 0.7 `./eval/snapshots/v1/` (Create: `screening_search_results.json`, `extract_search_results.json`, `README.md`)

*   **Type / Scope**: Eval input snapshot
*   **Proposed Changes**: Copies of the two gitignored `search_results.json`
    files, renamed per source; `README.md` records their retrieval date. Plan §10
    checklist item.

#### 0.8 `./.gitignore` (Verify — no expected edit)

*   **Type / Scope**: VCS configuration
*   **Proposed Changes**: Confirm the new fixture paths are tracked. The
    existing ignores are path-anchored (`Screening_Agent/search_results.json`,
    `extract_agent/search_results.json`) and do not match `tests/fixtures/` or
    `eval/snapshots/`; `git add` failing loudly is the backstop.

#### 0.9 `./requirements.txt` (Modify; touched again in 1a, 2a, 2b)

*   **Type / Scope**: Dependencies
*   **Proposed Changes**: Batch 0 adds a `ruff` pin (`pytest==9.1.0` is
    already pinned). 1a adds
    `pydantic-settings`. 2a adds `sqlalchemy`, `alembic`, `pgvector`,
    `psycopg[binary]`. 2b removes `faiss-cpu`. `sentence-transformers` stays.

### Commit 1a — Seam (v1 layout still in place)

#### 1a.1 `./src/llm/settings.py` (Create, plus `src/__init__.py`, `src/llm/__init__.py`)

*   **Type / Scope**: Configuration module
*   **Proposed Changes**: Pydantic Settings: `profile` (`local`/`test`),
    `ollama_base_url`, model per wired role, `embedding_model`, `database_url`
    (optional until 2a — no Postgres exists before it; from 2a required whenever
    `repository_backend` is `postgres`), `repository_backend` (`postgres`
    default, or `memory`; added in 2b), `openalex_email` (required, no default —
    closes backlog #5), `openalex_api_key` (optional), `langsmith_tracing`
    (the switch `tracing.py` reads), PDF directory. Validated at startup.

#### 1a.2 `./src/llm/client.py` (Create)

*   **Type / Scope**: LLM seam
*   **Proposed Changes**: `get_llm(role) -> AsyncInstructor` (Instructor-patched
    `AsyncOpenAI`, `max_retries=3`, tracing-wrapped, Instructor `max_retries=2`
    bound as the default of the client's `create`;
    raises on roles other than `search`/`screening`/`extraction`);
    `get_embedder()`. `test` profile returns the fakes from 1a.4.

#### 1a.3 `./tracing.py` → `./src/llm/tracing.py` (Move)

*   **Type / Scope**: Tracing wrapper
*   **Proposed Changes**: All four public helpers (`maybe_wrap_openai`,
    `traceable_stage`, `root_trace`, `tracing_enabled`) moved unchanged. The
    four remaining v1-path imports — `Backend/main.py` (first touched here;
    moved in 1b), `Orchestration/nodes.py`,
    `extract_agent/document_processing_node.py`,
    `extract_agent/rag_extraction_main.py` — are rewritten to
    `from src.llm.tracing import ...` in this commit; the root module is then
    removed so only one import path exists. (`search_agent/agent.py` and
    `Screening_Agent/screening_agent.py` lose their tracing imports via 1a.6 /
    1a.9.)

#### 1a.4 `./src/llm/fake.py` (Create)

*   **Type / Scope**: Test-profile fake surface
*   **Proposed Changes**: Fake LLM: an empty registry keyed by `response_model` type
    (values: canned instance or `Callable[[messages], instance]`) that the tests
    fill through `set_fake_answers`. The canned screening decision `include`, the
    `[FAKE:EXCLUDE]`/`[FAKE:UNCERTAIN]` sentinel handling and `[FAKE:FAIL]`
    (whose callable raises a simulated API error so the paper lands in
    `failed_papers` exactly as a v1 LLM failure did) live in `tests/fakes.py`,
    keeping `src/llm` free of test-tree imports. Deterministic 384-dim fake embedder (vector seeded from the SHA-256 of the
    input text, L2-normalized); stub OpenAlex client replacing
    `OpenAlexClient.execute_retrieval`, returning raw work dicts from
    `tests/fixtures/openalex_works.json` so the agent's formatting loop runs
    unmodified; fixture-PDF provider. The stub and PDF replacements are plain
    functions; the test side installs them by monkeypatching (the `fake_surface`
    fixture, `scripts/fake_run.py`). `fake.py` reads `tests/fixtures`, so it
    cannot run inside the backend image, which ignores `tests/`.

#### 1a.5 `./src/llm/prompts/` (Create: `__init__.py`, `search.py`, `screening.py`, `extraction.py`)

*   **Type / Scope**: Versioned prompts
*   **Proposed Changes**: v1's inline prompt strings moved byte-identical, one
    module per role, each with `PROMPT_VERSION = "v1"`. Plan §5.4 mandate; feeds
    the provenance envelope. Interpolated v1 prompts (the per-call f-strings in
    screening and extraction) become `.format` templates with a per-role
    `render_*` function; rendered output is byte-identical to v1's f-strings.

#### 1a.6 `./search_agent/agent.py` (Modify; moved in 1b)

*   **Type / Scope**: Search agent
*   **Proposed Changes**: Client from `get_llm("search")`; query-expansion call
    ported to async (the only sync LLM call site); prompt from 1a.5; output
    carries `openalex_id`, `pdf_url`, `venue`
    (`primary_location.source.display_name` — new, behaviour-neutral), `authors`.
    Fallback-to-tokenized-query preserved after SDK retries (register V6).
    `pdf_url` = `primary_location.pdf_url or best_oa_location.pdf_url` (the
    expression `execute_retrieval` already computes); `openalex_id` stored bare
    (the `https://openalex.org/` prefix stripped at formatting time) — the form
    `papers.openalex_id` uses.

#### 1a.7 `./search_agent/new_main.py` (Modify; moved in 1b)

*   **Type / Scope**: Search entry point
*   **Proposed Changes**: Async `main`; OpenAlex contact email from settings,
    hardcoded fallback removed; `sys.path` workaround dropped (obsolete once 1b
    moves it; the 1a fake-e2e smoke covers the removal).

#### 1a.8 `./search_agent/api_client.py` (Modify; moved in 1b)

*   **Type / Scope**: OpenAlex client
*   **Proposed Changes**: Contact email injected from settings. HTTP stays sync
    `requests`; callers wrap it in `asyncio.to_thread`. No other change.

#### 1a.9 `./Screening_Agent/screening_agent.py` (Modify; moved in 1b)

*   **Type / Scope**: Screening agent
*   **Proposed Changes**: Client from `get_llm("screening")`; hand-rolled retry
    loop removed (register V6); prompt from 1a.5; semaphore concurrency unchanged.

#### 1a.10 `./Screening_Agent/screening_schemas.py` (Modify; moved in 1b)

*   **Type / Scope**: Shared paper contract
*   **Proposed Changes**: `ResearchPaper` gains optional-with-default
    `openalex_id`, `pdf_url`, `venue` so old fixtures keep validating. No
    consumer edits needed: `Backend/schemas.py` carries papers as
    `List[Dict[str, Any]]` and `ui_app.py` reads raw JSON, so the added
    optional fields flow through unchanged.

#### 1a.11 `./extract_agent/rag_extraction_main.py` (Modify; moved in 1b)

*   **Type / Scope**: Extraction node
*   **Proposed Changes**: Module-import-time client replaced by call-time
    `get_llm("extraction")`; prompt from 1a.5; tracing import rewritten (1a.3).

#### 1a.12 `./extract_agent/document_processing_node.py` (Modify; split in 1b, rewritten in 2b)

*   **Type / Scope**: Ingestion node
*   **Proposed Changes**: 1a only swaps the embedder construction to
    `get_embedder()` and rewrites the tracing import (1a.3). FAISS logic
    untouched until 2b.

#### 1a.13 `./Orchestration/nodes.py` (Modify; moved in 1b)

*   **Type / Scope**: Graph nodes
*   **Proposed Changes**: `search_node` becomes `async def` with OpenAlex work in
    `asyncio.to_thread`; hardcoded model at line 62 replaced by settings
    (closes backlog #14's second item); `pre_excluded=[]` left as-is (Non-Goal).

#### 1a.14 `./tests/unit/test_screening_node.py`, `./tests/unit/test_extraction_node.py` (Create)

*   **Type / Scope**: Node-level fake-LLM unit tests
*   **Proposed Changes**: Screening: fixture papers produce the four buckets via
    sentinels. Extraction: canned `ExtractedPaperInfo` round-trips into the state
    shape. Required by the inputs; distinct from the e2e smoke.

#### 1a.15 `./tests/e2e/test_fake_pipeline.py` (Create)

*   **Type / Scope**: End-to-end smoke (fake surface)
*   **Proposed Changes**: Graph compiles; a full fake run completes; final state
    shape matches v1's. This is the per-commit green check from here on.

#### 1a.16 `./tests/fixtures/paper_small_1.pdf`, `./tests/fixtures/paper_small_2.pdf` (Create)

*   **Type / Scope**: Committed binary fixtures
*   **Proposed Changes**: Two generated 2–3-page PDFs so that 2b's page-aware
    chunking and partition test run offline (in 1a they feed v1's FAISS path).

#### 1a.17 `./tests/fixtures/golden_run.json` + `./tests/e2e/test_golden_transcript.py` (Create)

*   **Type / Scope**: Characterization test
*   **Proposed Changes**: Captured final-state JSON of the fake e2e run, taken
    before any package moves; the test diffs current runs against it with the
    deviation register as allow-list. Regeneration is a deliberate, reviewed step
    (2b regenerates when V1–V3/V5 land). Mechanics: before diffing, volatile
    fields (run/job ids, timestamps, filesystem paths) are replaced with fixed
    placeholders; the allow-list is a list of JSON-path prefixes per register
    entry, defined beside the test; any difference outside an allowed prefix
    fails.

#### 1a.18 `./.env.example` (Create; touched in 2a)

*   **Type / Scope**: Configuration documentation
*   **Proposed Changes**: Every setting from 1a.1 with native-vs-compose Ollama
    URL comments; `DATABASE_URL` is listed commented out from the start, and 2a
    uncomments it with the compose default.

#### 1a.19 `./docs/notes/phase1_explanations.md` (Create; appended throughout)

*   **Type / Scope**: Owner learning notes (working agreement)
*   **Proposed Changes**: 5–10-line plain-language explanation after each core
    task (LLM layer/settings here; data model in 2a; ingestion in 2b).

### Commit 1b — Move into `src/`

#### 1b.1 Package moves (Move; imports updated, no logic changes)

*   **Type / Scope**: Layout migration
*   **Proposed Changes**:
    `Orchestration/{graph,nodes,state}.py` → `./src/graph/`;
    `Backend/{main,schemas}.py` → `./src/api/`;
    `search_agent/{agent,api_client,schemas,new_main}.py` → `./src/pipeline/search/`;
    `Screening_Agent/{screening_agent,screening_schemas}.py` → `./src/pipeline/screening/`;
    `extract_agent/document_processing_node.py` split into
    `./src/pipeline/ingestion/{node,pdf,chunking,retrieval}.py` (function-level
    split; FAISS retrieval stays inside `retrieval.py` until 2b);
    `extract_agent/{rag_extraction_main,extraction_schemas}.py` →
    `./src/pipeline/extraction/{node,schemas}.py` (CLI/`sys.path` scaffolding
    stripped); `ui_app.py` → `./src/ui/app.py`. All with `__init__.py` files and
    `from src. ...` imports.

#### 1b.2 `./Screening_Agent/test_screening.py` → `./tests/unit/test_screening.py` (Move)

*   **Type / Scope**: Test relocation
*   **Proposed Changes**: Imports switch to `src.pipeline.screening`;
    `Screening_Agent/testdaten/review_config.json` →
    `./tests/fixtures/review_config.json`.

#### 1b.3 `./src/api/main.py` (Modify — within the move; touched again in 2a.5)

*   **Type / Scope**: API
*   **Proposed Changes**: `GET /health` returning plain 200 (CI compose check
    target; readiness-grade DB ping is backlog #20).

#### 1b.4 `./Dockerfile.backend`, `./Dockerfile.frontend`, `./docker-compose.yml`, `./.dockerignore` (Modify)

*   **Type / Scope**: Build/deploy configuration
*   **Proposed Changes**: CMD → `uvicorn src.api.main:app`; frontend entry →
    `src/ui/app.py`; copy paths and ignore rules for the new tree; `libgomp` kept
    until a build without it passes the smoke check.

#### 1b.5 `./.github/workflows/ci.yml` (Modify)

*   **Type / Scope**: CI
*   **Proposed Changes**: ruff gate on `src/` and `tests/`.

### Commit 1c — Delete and correct docs

#### 1c.1 Deletions (Delete)

*   **Type / Scope**: Dead code removal (closes backlog #2, #3)
*   **Proposed Changes**: `App_Main/` (whole directory);
    `search_agent/main.py`; `search_agent/archiv/`;
    `extract_agent/{auto_pdf_downloader,add_full_text_from_pdfs,rag_chunker,rag_retriever}.py`;
    `Screening_Agent/screening_main.py`;
    `Screening_Agent/review_config_Evaluation.json`; `export_graph.py`;
    per-package `README.md` files; the remaining tracked leftovers
    `Backend/__init__.py`, `Orchestration/__init__.py`,
    `search_agent/__init__.py`, `extract_agent/.gitignore`; then the emptied
    `Backend/`, `Orchestration/`, `search_agent/`, `Screening_Agent/`,
    `extract_agent/` directories. Untracked leftovers
    (`Screening_Agent/screening_results.json`, `search_agent/.mas_runs/`, the
    two gitignored `search_results.json` files) are deleted locally; they were
    never tracked.

#### 1c.2 `./CLAUDE.md`, `./README.md` (Modify)

*   **Type / Scope**: Documentation
*   **Proposed Changes**: Rewritten for the `src/` layout, new run/test commands,
    settings-based configuration (closes backlog #14's doc items; plan §10 item).

### Commit 2a — Postgres: runs, schema, migrations

#### 2a.1 `./docker-compose.yml` (Modify)

*   **Type / Scope**: Local stack
*   **Proposed Changes**: `pgvector/pgvector:pg17` service with named volume
    `pgdata`, published on host port 5432; backend gets `DATABASE_URL` plus
    `OPENALEX_EMAIL` and `PROFILE` passthrough; `pdfs_auto` volume name kept. A
    one-shot `migrate` service runs `alembic upgrade head` and the backend starts
    only after it succeeds (added after 2b; CI's `stack` job and
    `scripts/restart_check.sh` rely on it).

#### 2a.2 `./src/db/models.py`, `./src/db/session.py` (Create)

*   **Type / Scope**: ORM layer
*   **Proposed Changes**: SQLAlchemy models for `users`, `reviews`, `runs`,
    `papers`, `chunks` exactly as the Technical Plan's column table (text + CHECK
    enums, `vector(384)`); sync engine + session factory; all calls from async
    contexts go through `asyncio.to_thread` (R4). Completing the column table
    to DDL level: PKs — `runs.id` uuid, all other tables integer identity.
    FKs — `chunks.paper_id` ON DELETE CASCADE; all other FKs RESTRICT.
    Uniques — `users.email`, `papers.openalex_id`, `papers.doi` (nullable
    unique), `chunks (paper_id, ordinal)`. `papers` gains `created_at` /
    `updated_at`. Columns not listed in the Technical Plan's table plus these
    do not exist.

#### 2a.3 `./alembic.ini`, `./src/db/migrations/` (Create: `env.py`, `versions/0001_initial.py`, `versions/0002_seed_local_user.py`)

*   **Type / Scope**: Migrations
*   **Proposed Changes**: `0001`: `CREATE EXTENSION IF NOT EXISTS vector` + all
    five tables (explicit `pgvector.sqlalchemy.Vector` imports). `0002`: data
    migration seeding `local@localhost`. Runner: `make migrate` and the
    integration-test session fixture; the API never auto-migrates (Non-Goal).

#### 2a.4 `./src/db/repository.py`, `./src/db/memory_repository.py`, `./src/db/records.py` (Create)

*   **Type / Scope**: Data access
*   **Proposed Changes**: [`repository.py`](../../src/db/repository.py): functions
    for run lifecycle (`create_run`, which inserts the review and the run
    together, plus `start_run`, `get_run`, `update_run_step`, `finish_run`,
    `mark_unfinished_interrupted`), paper upsert (the Technical Plan's "Ingestion and retrieval"
    step 1; `concepts_brief.md` decision 3.1 — used from 2b), chunk replace +
    retrieval queries (used from 2b). plus the paper and chunk helpers it
    needs (`get_paper`, `set_paper_status`, `is_chunked`). Keeps SQL out of nodes
    and API. Also defines the repository seam: `get_repository()` returns the
    Postgres implementation when `REPOSITORY_BACKEND` is `postgres` (the default)
    and the in-memory fake when it is `memory`, independent of the profile; nodes
    and API call only this seam. [`memory_repository.py`](../../src/db/memory_repository.py)
    is that in-memory fake (built in 2b.1). [`records.py`](../../src/db/records.py)
    holds what both share: constants, the `NewChunk` record and `normalize_doi`.

#### 2a.5 `./src/api/main.py` (Modify)

*   **Type / Scope**: Run lifecycle
*   **Proposed Changes**: `JOBS` dict removed (register V4). `POST /start_pipeline` inserts
    `reviews` + `runs` (`pending`, provenance envelope written from settings),
    returns `runs.id` as `job_id`. Background task flips to `running`, updates
    per `astream` step. Lifespan runs the one-statement `interrupted` update.
    `GET /status/{job_id}` composes `ResearchResponse` per the mapping table.

#### 2a.6 `./src/ui/app.py` (Modify)

*   **Type / Scope**: UI polling
*   **Proposed Changes**: Stop on HTTP 404 and on
    `current_step ∈ {completed, error, interrupted}`; show the interrupted
    message.

#### 2a.7 `./tests/integration/test_restart.py` (Create, plus `tests/integration/conftest.py`)

*   **Type / Scope**: Integration test (G2)
*   **Proposed Changes**: Session fixture runs migrations against compose
    Postgres; test completes one fake run, leaves one mid-run row, tears the app
    down, builds a second instance on the same DSN, invokes the lifespan, asserts
    survivors and `interrupted` marking, and asserts the 404 and interrupted
    status responses. Also asserts the `failed → current_step="error"` mapping
    via one forced-failure run, completing coverage of the status-mapping table.

#### 2a.8 `./scripts/restart_check.sh` (Create)

*   **Type / Scope**: Phase-exit script (local)
*   **Proposed Changes**: Literal `docker compose restart` of API + Postgres
    around a fake run; asserts the completed run's status survives. The compose
    API cannot produce a fake run itself (see the fake-surface table), so the
    script creates the run from the host with
    [`scripts/fake_run.py`](../../scripts/fake_run.py), which runs the whole app
    in-process through `TestClient` against the compose Postgres using the test
    fakes; the compose API only reads the run back. Referenced in the exit
    checklist; not in CI (R2).

### Commit 2b — Postgres: ingestion, retrieval, exit tests

#### 2b.1 `./src/pipeline/ingestion/{node,pdf,chunking,retrieval}.py` (Modify)

*   **Type / Scope**: Ingestion rewrite onto Postgres
*   **Proposed Changes**: `node.py` orchestrates upsert → PDF → chunk → retrieve
    per included paper, keeping the v1 state contract
    (`retrieved_chunks_by_field`). `pdf.py`: `{paper_id}.pdf` keying, `%PDF`
    check, stored-URL-then-fallback resolution (register V1, V3). `chunking.py`:
    per-page 1200-char windows, 1-based pages, per-paper ordinals, skip
    whitespace-only pages, keep tails; delete-then-insert in one transaction with
    `chunked` status; skip rule keyed on `embedding_model` + `chunker_version`,
    checked on any single chunk row of the paper — uniform by the
    delete-then-insert invariant (register V2). `CHUNKER_VERSION = "v1"` is
    defined in `chunking.py` and written to every chunk row. `retrieval.py`:
    pgvector cosine top-5 per `FIELD_QUERIES` field filtered by `paper_id`;
    FAISS removed (register V5). `test` profile: an in-memory fake repository
    (same functions as 2a.4; retrieval is brute-force cosine over the fake
    embedder's vectors) backs the fake e2e and golden-transcript tests, which
    therefore stay in `make test` and CI with no Postgres.

#### 2b.2 `./tests/unit/test_chunking.py` (Create)

*   **Type / Scope**: Unit test
*   **Proposed Changes**: The partition invariant — concatenating a page's chunks
    reproduces the page text; documented as Phase-1-only, retired when overlap
    arrives.

#### 2b.3 `./tests/integration/test_duplicate_run.py`, `./tests/integration/test_duplicate_doi.py` (Create)

*   **Type / Scope**: Integration tests (G1)
*   **Proposed Changes**: Same fake run twice → one `papers` row and one chunk
    set per paper; the fixture's two-OpenAlex-IDs-one-DOI pair merges into one
    paper under the upsert merge rule ("Ingestion and retrieval" step 1;
    `concepts_brief.md` decision 3.1).

#### 2b.4 `./tests/fixtures/golden_run.json` (Modify — deliberate regeneration)

*   **Type / Scope**: Characterization baseline
*   **Proposed Changes**: Regenerated once, with register entries V1–V3, V5 and
    the FAISS→pgvector retrieval swap as the documented justification; the
    allow-list empties: V1–V3/V5 are baked into the regenerated baseline, V6
    predates the original capture, and V4 is API-layer state invisible in
    graph-level output.

#### 2b.5 `./.github/workflows/ci.yml` (Modify)

*   **Type / Scope**: CI
*   **Proposed Changes**: Image build (buildx layer cache) + compose up of
    backend + Postgres with dummy `OLLAMA_BASE_URL` and dummy `OPENALEX_EMAIL`
    (e.g. `ci@example.invalid`) + `GET /health` assertion.

### Verification Plan

*   **Compilation/Build**: `docker compose build`; CI image-build stage green.
*   **Unit Tests**: `make test` (pytest, `-m "not integration"`, fake surface) —
    includes node tests (1a.14), fake e2e (1a.15), golden transcript (1a.17),
    partition invariant (2b.2), and the repaired screening tests (post-2b,
    ingestion runs against the in-memory fake repository).
*   **Static Analysis & Linting**: `ruff check src tests` (CI gate from 1b).
*   **Integration (local, R2)**: `make integration` — G1 (duplicate run,
    duplicate DOI) and G2 (restart simulation) against compose Postgres.
*   **Phase exit**: `scripts/restart_check.sh` (literal compose restart); one
    non-gating live smoke run with real Ollama + MiniLM (recommended before
    tagging; exit criteria do not depend on it); exit criteria G1–G6
    checked against the plan §10 exit block; git tag `v0.2`.
*   **Per-commit check**: from 1a on, the fake e2e smoke passes after every
    commit; Batch 0's check is unit tests green in CI.

--------------------------------------------------------------------------------

*Drafted with EGM*
