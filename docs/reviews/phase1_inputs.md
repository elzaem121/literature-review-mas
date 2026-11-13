# Phase 1 — Inputs for the brainstorm

> Collected 2026-11-13 from `docs/reviews/consolidated_review_report.md`, from every item marked "Phase 1 design" or "Phase 1 data design". These are inputs, not decisions; the Phase 1 brainstorm settles them and the result goes to `docs/designs/`.
> Each item has been adjusted for the owner decisions D1-D8 (listed below). Action IDs (A#) and raw finding IDs point back to the reports in this folder.

## Decisions that shape Phase 1

- **D1 = (b):** the checkpointer moves to Phase 3. The Phase 1 exit is "no completed results lost". Run status lives in Postgres; unfinished runs are marked interrupted on restart.
- **D2 = (c):** Phase 1 keeps the v1 models (`qwen2.5-coder:7b`) and embedder (`all-MiniLM-L6-v2`, 384 dimensions, in-process). New models only after the Phase 2a benchmark.
- **D3:** multi-user and auth go to the backlog. `user_id` stays, filled with one seeded `local` user.
- **D8:** Excel export is dropped.

The plan-level result is in `docs/plan_v2.md`, section 10 "Phase 1" (end state, checklist, exit) and section 6 (entities and rules).

## 1. Migration of v1 code into `src/` (A2; IR B1, IR M5, Z8-14)

- A table marking each v1 module **Move** (with its target `src/` path), **Delete**, or **Keep until phase N**. Candidates for Delete:
  - `App_Main/streamlit-app.py` (second UI, with mock schemas);
  - `search_agent/main.py` and `search_agent/archiv/app.py` (backlog #2);
  - the legacy extract CLI scripts `auto_pdf_downloader.py`, `add_full_text_from_pdfs.py`, `rag_chunker.py`, `rag_retriever.py`, and the script parts of `rag_extraction_main.py` (backlog #3);
  - `Screening_Agent/screening_main.py`.

  To decide: `export_graph.py` and `tracing.py`.
- Whether the move is one atomic commit (imports, Dockerfiles, compose, READMEs together) or one package at a time. Every step must keep "the system runs" true (plan rule 1).
- Things that assume the flat root layout:
  - imports in `Orchestration/nodes.py:4-12`, `Orchestration/graph.py:2-14`, `Backend/main.py:6-10` and `Screening_Agent/screening_agent.py:11`;
  - the root `tracing` module, imported from four places;
  - the `sys.path` and `__package__` workarounds in `extract_agent/rag_extraction_main.py:10` and `search_agent/new_main.py:9-13`;
  - `Dockerfile.backend:24`, `Dockerfile.frontend:17` and `.dockerignore`.
- Close backlog #2 and #3 by deleting the code.

## 2. Restart behaviour without a checkpointer (A3; IR B2, Z5-6, Critic M-4, Z8-2, Z8-9)

Under D1 = (b), Phase 1 needs no checkpointer, but it still has to make completed results survive a restart.
- Replace the in-memory `JOBS` dict (`Backend/main.py:24`) with a `runs` row in Postgres: status, timestamps, and the run's screening and extraction output until Phase 2b adds `screenings` and `extractions`.
- Runs are started from FastAPI `BackgroundTasks` (`Backend/main.py:96`). Decide how a run is tied to its `runs` row, and how startup marks unfinished rows `interrupted`.
- `GET /status/{job_id}` reads from `runs`. Decide what an interrupted or unknown run returns.
- `ui_app.py:144-165` keeps polling after a non-200 response, so after a restart it polls a 404 forever. Make it stop on 404 and on interrupted runs.
- The two exit checks (no duplicates on a repeat run; completed results survive an API and Postgres restart) are automated integration tests. Decide how they run: docker-compose in a test, or a local script.

Moved to Phase 3 by D1, for reference:
- the async checkpointer class (`AsyncPostgresSaver`, check it against the pinned version);
- a `build_graph(checkpointer=None)` factory compiled in the FastAPI lifespan instead of at import time (`Orchestration/graph.py:49`);
- who calls `setup()` for the checkpoint tables, relative to Alembic;
- mapping `job_id` to `thread_id`.

## 3. Data model: tables, keys, enumerations (A7, A11, A28, A31; Z5-2, Z5-16, Critic M-6, M-8, M-12, IR M6, IR M21)

The Phase 1 migration creates `users`, `reviews`, `runs`, `papers` and `chunks` (plan section 6). Still to design:
- **Keys and the "current" rule for append-only LLM outputs (A7):** for example, unique (`paper_id`, `field`, `model`, `prompt_version`) plus a rule or view for the current row. This is needed in Phase 2b, but deciding it now keeps the Phase 1 schema consistent with it.
- **Paper identity (A11):**
  - Upsert key: DOI first, OpenAlex ID when there is no DOI. Two OpenAlex records with the same DOI must not break ingestion; `eval_notes.md` already found one duplicate.
  - An ingestion status column (for example pending, downloaded, chunked, pdf_unavailable, failed) with a retry policy.
  - An exit test with two OpenAlex IDs that share a DOI.
  - A mapping table from external IDs only if duplicates turn out to be common (Stage 8: drop unless measured).
- **BibTeX fields (A28):**
  - Add `authors` (jsonb) and `venue` to `papers`.
  - `search_agent/agent.py:173-184` already captures authors. Venue is only computed in the bypassed gatekeeper path (`agent.py:115-127`); carry `primary_location.source.display_name` into the search output.
  - The CSV export in `ui_app.py:251-258` can be reused later.
- **Enumerations (Critic M-8):**
  - the stored screening decision values (v1 has include, exclude, uncertain, failed; the table itself arrives in Phase 2b);
  - the shape of `reviews.criteria` (jsonb). v1 needs `min_year`, inclusion and exclusion criteria, and a target (`Orchestration/state.py`).
- **`user_id` (A31, D3):** one seeded `local` user, with `user_id` NOT NULL on private tables from the start.
- **Embedding filter (Critic N-5):** with one embedding model in production this is moot, but the vector column has a fixed dimension (384 for MiniLM). Re-embedding is a Phase 2a task if the model changes.

## 4. Ingestion and chunks (A10; C-5, Critic M-21, IR M8, IR M10)

- **Paper contract:** v1 stores the OpenAlex ID in `url` (`search_agent/agent.py:180-188`), and `ResearchPaper` (`Screening_Agent/screening_schemas.py:45-57`) has no `openalex_id`. `pdf_url` is required by `api_client.py:109-112` but dropped by `agent.py:180-188`, then looked up again by DOI in `document_processing_node.py:62-96`, which skips papers without a DOI (line 63). Carry `openalex_id` and `pdf_url` through the contract, and update the consumers (`Backend/schemas.py`, `ui_app.py`).
- **Page-aware chunking:** v1 joins all pages without markers (`document_processing_node.py:117`) and cuts 1200-character windows with no overlap (lines 122-123). Chunk page by page and store the page and chunk ordinal, so that Phase 2b evidence can cite a page.
- **Chunk overlap:** decide it now, or declare the Phase 2b re-chunk a one-time migration that keeps `evidence_chunk_id` references valid. The plan's Phase 2b task currently reads "Chunk overlap, if Phase 1 left it out".
- **Section labels:** Loop 2's original "specific sections such as Methods/Results" needs section labels on chunks. Loop 2 is now conditional (D5) and the plan dropped section targeting. Decide whether to store a section label anyway.
- **PDF storage:** v1 caches PDFs as `safe_filename(title)[:80]` (lines 55-59), which can collide, and overwrites them on every run. Key stored PDFs by paper id and check whether a file exists before downloading. PDFs live in the `pdfs_auto` volume (`docker-compose.yml:17`).
- **Retrieval:** v1 builds one FAISS `IndexFlatIP` per paper (`document_processing_node.py:44-49, 136-162`), so retrieval is naturally limited to one paper. In shared pgvector, every retrieval must filter by `paper_id`. Reuse `FIELD_QUERIES` (`document_processing_node.py:22-38`) as the per-field query set.
- **FAISS edge case:** with fewer than 5 chunks, FAISS returns -1 and `chunks[-1]` silently picks the last chunk (`document_processing_node.py:152-157`). Note the behaviour change for the Phase 2a baseline (IR N13).
- **Dependencies (adjusted for D2):**
  - add sqlalchemy, alembic, pgvector, psycopg, pydantic-settings and a linter;
  - remove faiss-cpu;
  - keep sentence-transformers, since MiniLM stays in-process;
  - check whether `libgomp` (`Dockerfile.backend:3-7`) is still needed without FAISS.

## 5. LLM layer (A14; Z5-5, Critic N-7, IR M9)

The plan fixes the interface: `get_llm(role)` returns an Instructor-patched, OpenAI-compatible client wrapped for tracing, and `get_embedder()` is separate. Still to design:
- **Call sites to change:**
  - `search_agent/agent.py:35-41` (sync `instructor.from_openai`);
  - `Screening_Agent/screening_agent.py:51-54` (async `instructor.patch`);
  - `extract_agent/rag_extraction_main.py:27-33` (module-level client built at import time);
  - the hardcoded model at `Orchestration/nodes.py:62`.

  `App_Main` is deleted (section 1).
- **Sync and async:** `get_llm` must serve both, or one style must win.
- **Tracing:** whether `tracing.py` (`maybe_wrap_openai`, lines 26-36) is kept as is or moved into `src/llm/`.
- **Retry and fallback:** use `tenacity`, which v1 already depends on. LangChain `with_fallbacks` is not used, and `langchain-openai` is not installed.
- **`search` role:** query expansion (`agent.py:65-77`) gets its own role, so the Phase 2a benchmark can include it.
- **Fake LLM:** the `test` profile's fake LLM plugs in at this seam.

## 6. Tests and CI first (A30; IR M3)

- **Test repair (backlog #1):**
  - fix the fixture path (`Screening_Agent/testdaten/review_config.json`);
  - fix the duplicate `screening_schemas` import that makes Pydantic see two `ResearchPaper` classes;
  - make collection work without `PYTHONPATH=..`.
- **Gitignored fixture:** `test_screening.py:46-52` loads `Screening_Agent/search_results.json`, which `.gitignore:36` excludes. It passes locally and will fail in CI. Commit a small fixture under `tests/`.
- **`TestMainEntryContract`:** `test_screening.py:143-148` checks the source text of `screening_main.py`, which is deleted. Drop or rewrite it.
- **Tests to keep and add:** keep the 8 pure-logic tests. Add fake-LLM tests for the screening and extraction nodes. Note that `nodes.py:69-76` passes `pre_excluded=[]`, so the tested year-prefilter helpers are not used by the live graph today.
- **Smoke check:** the graph compiles, a fake-LLM end-to-end run passes, and `docker compose up` serves the API.

## 7. Detail removed from `plan_v2.md` (A24; Z5-17, Z8-13)

The plan now holds one line for each of these blocks. They are kept here so the Phase 1 design can start from them. They are the pre-review versions and do not yet reflect D1-D8.

**Repository layout (old section 5.4):**

```text
src/
  api/        FastAPI app, endpoints, schemas
  graph/      main graph, router, state
  pipeline/   subgraph: search, screening, retrieval, extraction
  llm/        get_llm, settings, prompts/ (versioned files)
  db/         SQLAlchemy models, Alembic migrations
  ui/         Streamlit app
eval/         datasets, judge prompts, eval scripts
tests/        unit and integration tests
deploy/       Dockerfiles, docker-compose, Kubernetes manifests
docs/         plan_v2.md, designs/
```

Gaps the reviewers found:
- `docs/` should also list `backlog.md`, `eval_notes.md` and `reviews/`.
- `pipeline/` has no ingestion or store module.

**Column table (old section 6):**

| Table | Key columns | Scope |
| --- | --- | --- |
| `users` | `id`, `email` | private |
| `reviews` | `id`, `user_id`, `question`, `criteria` (jsonb) | private |
| `conversations` | `thread_id`, `user_id`, `review_id` | private |
| `screenings` | PK (`review_id`, `paper_id`), `decision`, `reason`, `model`, `prompt_version` | private |
| `papers` | `id`, `openalex_id` (unique), `doi` (unique), `title`, `year`, `pdf_url` | shared |
| `chunks` | `id`, `paper_id`, `page`, `text`, `embedding` (vector), `embedding_model` | shared |
| `extractions` | `id`, `paper_id`, `field`, `value`, `status`, `evidence_chunk_id`, `model`, `prompt_version` | shared |

The old rules also said: use SQLAlchemy (or SQLModel) with Alembic, and add an HNSW index only when chunk volume requires it. The reviewers asked for a measurable trigger (a chunk count or a query latency). Known changes since the review:
- a `runs` table;
- `authors` and `venue` on `papers`;
- ingestion status on `papers`;
- one review per conversation, with a `new_topic` starting a new conversation (Phase 3);
- review-specific extraction fields stored per review.

**Endpoint list (old section 5.1), for the Phase 3 design:**
- `POST /chat`: SSE stream of answer tokens and pipeline progress
- `POST /chat/resume`: user reply after `interrupt()`. Now needed only for criteria confirmation (a Should).
- `GET /reviews/{id}/table`, `GET /reviews/{id}/export?format=csv|bibtex`
- `GET /health`

The reviewers found these missing: list conversations and reviews, load chat history, fetch the screening log and summary, and a reconnectable run-status endpoint.

**Model YAML (old section 7):** replaced by the role list and the v1 defaults (D2). The old version, kept for the Phase 2a benchmark:

```yaml
llm:
  router:     { provider: ollama, model: qwen3:8b }          # provisional
  screening:  { provider: ollama, model: qwen3:8b }          # provisional
  extraction: { provider: ollama, model: qwen3:8b }          # provisional
  embedding:  { provider: ollama, model: nomic-embed-text }  # provisional
  summary:    { provider: groq,   model: llama-3.3-70b, fallback: ollama }
  judge:      { provider: groq,   model: llama-3.3-70b }
```

**Evaluation table and judge rules (old section 8), for `docs/designs/eval.md` in Phase 2a:**

| Component | Metric | Method |
| --- | --- | --- |
| Router | Accuracy, confusion matrix | 30–50 labeled messages; no judge |
| Search | precision@10 | Judge: relevant yes/no |
| Screening | Agreement rate | Judge decision vs. system decision |
| Extraction | Faithfulness, share of empty fields | Judge sees value + evidence passage |
| Chat answers, summary | Faithfulness, citation correctness | Judge sees answer + cited sources |
| End-to-end | Latency, tokens per step | LangSmith traces |

The old judge rules: binary or 1–3 scale, with reasoning before the verdict; a versioned judge prompt at temperature 0; label 20–30 cases manually and report human–judge agreement before trusting results.

Corrections the reviewers asked for:
- **Screening metric:** score screening deterministically, with include and exclude recall (`eval_notes.md`).
- **New metrics:** add recall@k, evidence-page accuracy and per-loop yield.
- **Pass rule:** give calibration a pass condition, for example agreement ≥ 0.8 or Cohen's kappa ≥ 0.6.
