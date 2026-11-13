# Goldfish Review Report

**Target:** `/Users/mohamedelsayed/PycharmProjects/literature-review-mas-neu/docs/plan_v2.md` (lines 201-294, `## 10. Phases` through `## 14. Open questions`)

**Mode:** REVIEW. Lines 1-200 were read for context only.

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `implementation-readiness` | completed (15 raw findings) |
| `codebase-details` | completed (18 raw findings) |
| `style` | completed (27 raw findings) |

## Summary

| Severity | Count |
| --- | --- |
| Blocker | 2 |
| Major | 24 |
| Nit | 16 |

The 60 raw findings were merged into 42 consolidated ones. Each consolidated finding lists every source id.

**Verdict:** Phase 1 is not ready to start. The phase order (foundation, then pipeline, then chat, then deployment, then release) is sound. The gaps are:
- Phase 1 never says what happens to the running v1 code.
- The Phase 1 exit criterion can't be checked and can't be met by the listed tasks.
- Several decisions that shape the first migration and the Phase 2 baseline are left open, even though section 14 says there are none.

**Codebase claims in scope:**
- Confirmed: the `v0.1` tag and `v2` branch exist, and the v1 gaps listed in the plan are real.
- Spot-checked by the synthesizer:
  - `Backend/main.py:24` keeps job state in an in-memory `JOBS` dict.
  - `.gitignore:36` excludes `Screening_Agent/search_results.json`.
  - `Backend/schemas.py:10` defines `target_output_count` as a search fetch size.
  - `extract_agent/` has none of the `extract_agent.py`, `extraction_agent.py` or `extraction_main.py` files that `CLAUDE.md` lists.

**Severity changes:**
- `style-1-7` and `style-1-11` were downgraded from Major to Nit. A phase design can resolve either one without changing the plan's direction.
- `implementation-readiness-1-14` (Nit) and `style-1-12` (Major) were merged and kept at Major.

---

## Prioritized Findings (Blockers -> Major -> Nits)

### B1. Phase 1 doesn't say how v1 code moves into the new layout or which pipeline runs at the end of the phase - Severity: Blocker
* **IDs:** `implementation-readiness-1-1`, `style-1-3`, `codebase-details-1-3`
* **Reviewer Lens:** `implementation-readiness`, `style`, `codebase-details`
* **Affected Scope:** Lines 213, 216-217, 220, 230, 284, 288
* **Discrepancy Description:**
  * "New repository layout" (line 213) is one checkbox. It could mean creating empty `src/` directories or porting the v1 pipeline.
  * The v1 packages import each other as flat root-level packages:
    * `Orchestration/nodes.py:4-12`, `Orchestration/graph.py:2-14`, `Backend/main.py:6-10` and `Screening_Agent/screening_agent.py:11`;
    * the root `tracing` module, imported from four places;
    * the `sys.path` and `__package__` workarounds in `extract_agent/rag_extraction_main.py:10` and `search_agent/new_main.py:9-13`;
    * `Dockerfile.backend:24`, `Dockerfile.frontend:17` and `.dockerignore`, which all assume the repo-root layout.
  * The plan doesn't say whether the v1 pipeline is ported into `src/pipeline/` in Phase 1, or whether it is changed to use the new ingestion code (pgvector and `nomic-embed-text` instead of FAISS and MiniLM). "Pipeline as subgraph" is a Phase 2 task (line 230).
  * The exit test "running the same topic twice" needs a pipeline that writes to Postgres, but no task connects v1 search and document processing to the new ingestion code.
  * The plan doesn't say which graph `PostgresSaver` attaches to.
  * Rule 1 ("the system runs after every step") has no definition of "runs" and no step-by-step migration path.
* **Rationale & Recommendation:**
  * A Phase 1 session can't scope its work without this. Add a short "Phase 1 end state" paragraph that names:
    * the working entry point at the end of the phase (for example, the v1 `POST /start_pipeline` and `GET /status/{job_id}`, now backed by the checkpointer);
    * which v1 stages are ported and connected to Postgres/pgvector, and which stay as they are;
    * the graph that `PostgresSaver` attaches to.
  * Add a task: "Port the v1 linear pipeline into `src/pipeline/` with unchanged behavior, using `get_llm(role)` and Postgres instead of FAISS."
  * Say whether the move is one atomic commit (imports, Dockerfiles, compose and READMEs together) or one package at a time.
  * Define "runs" as a smoke check: the graph imports and compiles, a fake-LLM end-to-end `ainvoke` succeeds, and `docker compose up` serves the API.

### B2. The Phase 1 exit criterion can't be checked and can't be met by the listed tasks - Severity: Blocker
* **IDs:** `codebase-details-1-1`, `style-1-4` (also raised in `implementation-readiness-1-1`)
* **Reviewer Lens:** `codebase-details`, `style`
* **Affected Scope:** Lines 217, 220
* **Discrepancy Description:**
  * Four terms in the exit are undefined:
    * "Same topic": the data model uses `question`/`criteria`, and "topic" also appears in the router's `new_topic` route.
    * "No duplicates": the plan doesn't say duplicates of which rows.
    * "A restart": the plan doesn't say a restart of what.
    * "Loses nothing": the plan doesn't say what must survive.
  * Adding `PostgresSaver` alone can't make a restart lose nothing:
    * `Backend/main.py:24` keeps job state in an in-memory `JOBS` dict.
    * Runs go through FastAPI `BackgroundTasks` (`Backend/main.py:96`), which die with the process.
    * `astream(initial_state)` is called with no `config` and no `thread_id` (`Backend/main.py:38`).
    * An unknown `job_id` returns 404 (`Backend/main.py:109-110`).
    * `ui_app.py:144-165` keeps polling after a non-200 response, so after a restart it polls a 404 forever.
    * `Orchestration/graph.py:49` compiles the graph at import time with no checkpointer.
  * No Phase 1 task:
    * maps `job_id` to `thread_id`;
    * reads `/status` from checkpointer state;
    * decides whether in-progress runs resume or fail;
    * stops the UI polling loop.
* **Rationale & Recommendation:**
  * An exit criterion that can't be checked or reached means Phase 1 never ends cleanly.
  * Either add the missing tasks:
    * replace `JOBS` with a `thread_id`-keyed status read through `get_state`;
    * state whether interrupted runs resume on startup or are marked failed;
    * make `ui_app.py` stop on 404 or any non-200 response.
  * Or narrow the exit. Suggested rewrite: "Running the pipeline twice with the same question and criteria leaves one `papers` row and one set of `chunks` per paper. After restarting the API and Postgres containers, all library rows and the checkpoint for the run's `thread_id` are still present. Both checks are automated integration tests. CI (lint and unit tests) passes on `v2`."

---

### M1. The Phase 2 baseline is undefined, and Phase 1 changes models before anything is measured - Severity: Major
* **IDs:** `implementation-readiness-1-2`, `codebase-details-1-9`, `style-1-1`
* **Reviewer Lens:** `implementation-readiness`, `codebase-details`, `style`
* **Affected Scope:** Lines 205, 208, 210, 214, 216, 225, 238, 289
* **Discrepancy Description:**
  * Phase 0 is titled "Baseline" and tagged `v0.1` (the v1 code), but line 210 says v1 quality isn't measured.
  * Line 225 measures "the baseline before any Phase 2 pipeline change". That is the Phase 1 code, which has already changed three things:
    * the model, from `qwen2.5-coder:7b` (`Orchestration/nodes.py:62`, `search_agent/new_main.py:18`, `extract_agent/rag_extraction_main.py:21`) to `qwen3:8b`;
    * the embedder, from MiniLM to `nomic-embed-text`;
    * the vector store, from FAISS to pgvector.
  * `docs/eval_notes.md` open question 6 asks the same thing and leaves it open.
  * Rule 6 (line 289) requires a metric delta for improvements, but the Phase 1 model swap is never measured. The answer also decides whether v1 must stay runnable at `v0.1`, and whether a v1 eval adapter is needed.
* **Rationale & Recommendation:**
  * Decide this in the plan, not in the eval notes. Either:
    * state "Baseline = Phase 1 code at `v0.2` with provisional models; the v1-to-Phase 1 model swap is not measured", or
    * keep v1 runnable at `v0.1` and budget a v1 adapter in Phase 2.
  * Rename Phase 0 to "v1 documentation" so "baseline" has one meaning.

### M2. Section 14 says there are no open plan-level questions, but several exist - Severity: Major
* **IDs:** `style-1-12`, `implementation-readiness-1-14`
* **Reviewer Lens:** `style`, `implementation-readiness`
* **Affected Scope:** Lines 292-294
* **Discrepancy Description:** These questions are open at plan level:
  * the Phase 1 end state (B1);
  * the baseline definition (M1, `eval_notes.md` Q6);
  * the embedding-model migration (M11, Q7);
  * which tables Phase 1 creates, and the pre-auth `user_id` (M6);
  * where the CI eval subset runs, and what CI "deploy" targets (M22).
* **Rationale & Recommendation:** The statement tells a session that the plan is complete when it isn't. List these questions in section 14 until each is resolved, and keep the pointer to `docs/eval_notes.md` for questions at design level.

### M3. Tests and CI come last in Phase 1, "CI is green" sets no minimum, and a clean checkout has a fourth failing test - Severity: Major
* **IDs:** `implementation-readiness-1-4`, `codebase-details-1-8` (ordering part of `codebase-details-1-3`)
* **Reviewer Lens:** `implementation-readiness`, `codebase-details`
* **Affected Scope:** Lines 218, 220, 288
* **Discrepancy Description:**
  * The pytest/CI task is listed last (line 218), but rule 5 (line 288) requires passing tests after every task.
  * Backlog #1 records 3 of 11 screening tests failing.
  * A fourth test, `Screening_Agent/test_screening.py:46-52`, loads `Screening_Agent/search_results.json`, which `.gitignore:36` excludes. It passes locally and will fail in CI.
  * `test_screening.py:143-148` asserts on the source text of `screening_main.py`, a dev script that has no place in the new layout.
  * The tested helpers are not used by the live graph: `nodes.py:69-76` passes `pre_excluded=[]`.
  * "CI is green" is met by an empty suite, or by deleting the failing tests.
* **Rationale & Recommendation:**
  * Move test repair and the smoke check to the start of Phase 1.
  * Commit a small fixture under `tests/`, and drop or rewrite `TestMainEntryContract`.
  * Keep the 8 pure-logic tests, and add fake-LLM tests for `screening_node` and `extraction_node`.
  * Strengthen the exit: "the existing screening tests pass under the new layout; the duplicate and restart checks are automated."

### M4. The phase checklists and rule 4 don't reach `docs/backlog.md` or `docs/eval_notes.md` - Severity: Major
* **IDs:** `style-1-5`, `style-1-27`, part of `implementation-readiness-1-4`, part of `codebase-details-1-4`, part of `implementation-readiness-1-13`
* **Reviewer Lens:** `style`, `implementation-readiness`, `codebase-details`
* **Affected Scope:** Lines 213-218, 223, 227, 287, 290
* **Discrepancy Description:**
  * Rule 4 (line 287) limits a session to "this plan, the relevant design doc, and the relevant code".
  * Line 223 names `docs/eval_notes.md` as the Phase 2 input.
  * `docs/backlog.md` assigns items 1, 2, 3 and 5 to Phase 1 and item 6 to Phase 2. None appear in the checklists.
  * Rule 7 says "the backlog" without a path.
* **Rationale & Recommendation:** A session that follows rule 4 will miss work assigned to its phase.
  * Rewrite rule 4: "Each session reads this plan, the relevant design doc, the backlog items assigned to the current phase (`docs/backlog.md`), any inputs the design doc names, and the relevant code."
  * List the backlog items by number in the Phase 1 and Phase 2 checklists. Fold item 6 into the Phase 2 decision-record task.
  * Use `docs/backlog.md` in rule 7.

### M5. The plan doesn't say what happens to v1 modules that have no place in the target layout - Severity: Major
* **IDs:** `codebase-details-1-4`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Line 213 (section 5.4 layout, lines 97-109, for context)
* **Discrepancy Description:** These modules have no home in section 5.4:
  * `App_Main/streamlit-app.py` (with mock schemas at lines 304-390);
  * `search_agent/main.py` and `search_agent/archiv/app.py`;
  * the legacy extract CLI scripts (`auto_pdf_downloader.py`, `add_full_text_from_pdfs.py`, `rag_chunker.py`, `rag_retriever.py`);
  * `Screening_Agent/screening_main.py`, `export_graph.py` and `tracing.py`.
* **Rationale & Recommendation:** Without a decision for each module, the implementer chooses what to delete. Add a Phase 1 item, or a table in the Phase 1 design, that marks each v1 module as Move (with its target `src/` path), Delete, or Keep until a named phase.

### M6. The Phase 1 table scope and the `user_id` policy before auth are undecided - Severity: Major
* **IDs:** `implementation-readiness-1-5` (also raised in `style-1-3`)
* **Reviewer Lens:** `implementation-readiness`
* **Affected Scope:** Lines 215, 255
* **Discrepancy Description:**
  * "SQLAlchemy models; Alembic migrations (incl. `user_id`)" doesn't say whether Phase 1 creates all seven section 6 tables or only `papers` and `chunks`. `screenings.reason` and `extractions.status` are Phase 2 work (lines 231, 233).
  * With no auth until Phase 4, it isn't said what fills `user_id`: a seeded default user, or a nullable column. Phase 4 "Authentication" has no task for rows created before auth.
* **Rationale & Recommendation:** This decides the first migration, so it belongs at plan level.
  * List the tables the Phase 1 migration creates.
  * Decide the `user_id` policy before auth (for example, one seeded `local` user, with the column NOT NULL from the start).
  * Add a Phase 4 task to reassign those rows.

### M7. The named checkpointer doesn't fit the async graph or the module-level compile - Severity: Major
* **IDs:** `codebase-details-1-2`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Line 217 (line 133 for context)
* **Discrepancy Description:**
  * The live nodes are `async def`: `Orchestration/nodes.py:60`, `extract_agent/document_processing_node.py:169` and `extract_agent/rag_extraction_main.py:224`. The API runs the graph with `astream` (`Backend/main.py:38`).
  * The sync `PostgresSaver` doesn't implement the async checkpoint methods; `AsyncPostgresSaver` is the matching class. The reviewer asks for this to be checked against the pinned version.
  * An async saver needs a connection pool opened inside the event loop. That conflicts with `app = workflow.compile()` at import time (`Orchestration/graph.py:49`), which `export_graph.py:1` imports.
  * Neither `langgraph-checkpoint-postgres` nor `psycopg` is in `requirements.txt`.
  * The plan doesn't say who calls `.setup()` for the checkpoint tables, or how that relates to Alembic.
* **Rationale & Recommendation:**
  * Name `AsyncPostgresSaver`, after checking it against the pinned version.
  * Turn `graph.py` into a `build_graph(checkpointer=None)` factory that is compiled in the FastAPI lifespan. Keep a compile without a checkpointer for `export_graph.py` and tests.
  * State whether `setup()` runs at API startup or in the migration step.

### M8. The ingestion task conflicts with how v1 builds papers and chunks - Severity: Major
* **IDs:** `codebase-details-1-5`, `implementation-readiness-1-12`, `style-1-16`
* **Reviewer Lens:** `codebase-details`, `implementation-readiness`, `style`
* **Affected Scope:** Lines 216, 220, 233-234, 236 (section 6, lines 123-129, and section 5.3, line 90, for context)
* **Discrepancy Description:**
  * **No `openalex_id` to upsert on:**
    * `search_agent/agent.py:180-188` stores the OpenAlex ID in `url`.
    * `Screening_Agent/screening_schemas.py:45-57` (`ResearchPaper`) has no `openalex_id` field.
  * **`pdf_url` is dropped:**
    * `search_agent/api_client.py:109-112` requires `pdf_url`, but the paper object built in `agent.py:180-188` drops it.
    * `document_processing_node.py:62-96` looks the URL up again by DOI, and skips papers without a DOI (line 63).
  * **No page tracking or overlap:** `document_processing_node.py:117` joins all pages without markers, and lines 122-123 cut 1200-character windows with no overlap. Phase 2 "evidence (chunk, page)" then has no page to cite.
  * **Chunk overlap means re-chunking:**
    * Adding overlap in Phase 2 (line 236) means re-chunking and re-embedding the shared library. That contradicts "chunk each paper once" (line 129) and breaks existing `evidence_chunk_id` references.
    * Loop 2's "specific sections such as Methods/Results" needs section labels on chunks. The `chunks` table has none.
  * **PDF cache:** the cache key is `safe_filename(title)[:80]` (lines 55-59), which can collide, and files are overwritten on every run. PDFs live in the `pdfs_auto` volume (`docker-compose.yml:17`).
  * **Undefined term:** "Ingestion" doesn't appear in the section 5 pipeline, and its scope (whether it includes the PDF download) is unstated.
* **Rationale & Recommendation:**
  * Define ingestion as: download the PDF, chunk it, embed it, and upsert into `papers`/`chunks`. Phase 1 ingestion should:
    * add `openalex_id` and `pdf_url` to the paper contract, and update its consumers (`Backend/schemas.py`, `ui_app.py`);
    * chunk page by page and store the page and chunk ordinal;
    * key stored PDFs by paper id, with an existence check.
  * Either set chunk overlap in Phase 1, or declare the Phase 2 re-chunk an allowed one-time migration that keeps evidence references valid.
  * Either add a task to detect sections in chunks, or drop section targeting from Loop 2.

### M9. The LLM-layer migration leaves the client type, the search role and the call sites open - Severity: Major
* **IDs:** `codebase-details-1-6`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Lines 214, 218, 226
* **Discrepancy Description:**
  * Clients are built in four places:
    * `search_agent/agent.py:35-41` (sync `instructor.from_openai`);
    * `Screening_Agent/screening_agent.py:51-54` (async `instructor.patch`);
    * `extract_agent/rag_extraction_main.py:27-33` (a module-level client built at import time);
    * `App_Main`.
  * `Orchestration/nodes.py:62` hardcodes `qwen2.5-coder:7b`.
  * `tracing.py:26-36` only wraps raw OpenAI clients.
  * Section 7 names LangChain `with_fallbacks`, but `langchain-openai` isn't installed.
  * The search query-expansion call (`agent.py:65-77`) matches none of the section 7 roles, and the Phase 2 benchmark leaves it out.
  * A fake LLM can only plug in once this seam exists.
* **Rationale & Recommendation:**
  * Decide whether `get_llm` returns instructor-patched OpenAI clients or LangChain chat models. The choice changes `response_model=` versus `with_structured_output` in all three agents.
  * Add a `search` role, or assign query expansion to an existing role, and include it in the benchmark.
  * List the call sites and `nodes.py:62` as Modify targets.
  * State whether `tracing.py` is kept.

### M10. The embedding and vector-store switch doesn't cover dependencies, image size or per-paper retrieval - Severity: Major
* **IDs:** `codebase-details-1-7`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Lines 214, 216
* **Discrepancy Description:**
  * v1 uses in-process `all-MiniLM-L6-v2` (384 dimensions) and one FAISS `IndexFlatIP` per paper (`document_processing_node.py:20,44-49,136-162`), so retrieval is naturally limited to one paper.
  * A shared pgvector table with `nomic-embed-text` (768 dimensions) needs a `paper_id` filter and a fixed vector dimension.
  * The plan doesn't list:
    * the packages to add: sqlalchemy, alembic, pgvector, psycopg, pydantic-settings and a linter;
    * the packages to remove: sentence-transformers and faiss-cpu (`requirements.txt:35-36`), plus `libgomp` (`Dockerfile.backend:3-7`).
* **Rationale & Recommendation:**
  * List the dependency additions and removals for Phase 1.
  * State that pgvector retrieval filters by `paper_id`.
  * Reuse `FIELD_QUERIES` (`document_processing_node.py:22-38`) as the per-field query set.

### M11. No task covers changing the embedding model after the benchmark - Severity: Major
* **IDs:** `implementation-readiness-1-3`, `style-1-17`
* **Reviewer Lens:** `implementation-readiness`, `style`
* **Affected Scope:** Lines 216, 226-227 (line 156 for context)
* **Discrepancy Description:** Section 7 (line 156) and `eval_notes.md` Q7 say that changing the embedding model means re-embedding stored chunks and migrating the vector column. Phase 2 only says "replace the provisional defaults".
* **Rationale & Recommendation:** Add a conditional Phase 2 task: "If the embedding model changes: Alembic migration of the vector column, a script to re-embed stored chunks, and a check that all `chunks` rows share one `embedding_model`."

### M12. The only copy of the Phase 2 eval input data is untracked and at risk during the layout move - Severity: Major
* **IDs:** `codebase-details-1-10`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Lines 213, 224
* **Discrepancy Description:**
  * The topic-2 candidate source, `Screening_Agent/search_results.json`, is gitignored (`.gitignore:36`), as is `extract_agent/search_results.json` (`.gitignore:38`). `eval_notes.md` says the data "exists only on one machine".
  * Reorganizing `Screening_Agent/` in Phase 1 can destroy it.
* **Rationale & Recommendation:** Before the layout task, add a Phase 1 step that copies these files into the planned eval snapshot location and records the retrieval date.

### M13. Phase 2 starts building the gold set before its seven open eval questions are settled - Severity: Major
* **IDs:** `implementation-readiness-1-6`
* **Reviewer Lens:** `implementation-readiness`
* **Affected Scope:** Lines 223-227, 294
* **Discrepancy Description:**
  * `eval_notes.md` is a draft with seven open questions: topic 3, labeling model and circularity, the topic 2 criteria mismatch, class balance, judge calibration, the baseline, and the embedding migration.
  * It also proposes changes that affect the plan: a retrieval recall@k metric, two snapshot levels, and a local results file as the source of truth.
  * The Phase 2 checklist starts directly with the gold dataset. No rule for choosing a model is required before the benchmark runs.
* **Rationale & Recommendation:**
  * Make the first Phase 2 task: "Resolve the `eval_notes.md` open questions; write `docs/designs/eval.md`, including the model-selection rule."
  * Make the remaining tasks depend on it.
  * Update section 8 if recall@k is adopted.

### M14. The Phase 2 exit criteria can't be checked, and one is met automatically - Severity: Major
* **IDs:** `implementation-readiness-1-7`, `style-1-2`
* **Reviewer Lens:** `implementation-readiness`, `style`
* **Affected Scope:** Line 238
* **Discrepancy Description:**
  * Loop 2 turns every field that is still `empty` after 2 iterations into `not_reported` (line 91). So "fewer empty fields" passes whatever the extraction quality.
  * v1 has no field status, so the baseline value depends on an error-prone mapping from strings to status.
  * "Measured faithfulness" accepts any score.
  * "No unbounded loops" restates the design and doesn't say how it is checked.
  * Nothing in the exit checks the decision record, the stored screening log, Loop 1, or evidence linkage.
* **Rationale & Recommendation:** Rewrite the exit as checks:
  * fewer gold-`found` fields reported as `not_reported` or `empty` than the recorded baseline;
  * faithfulness reported with human-judge agreement;
  * fake-LLM tests showing each loop stops at its limit;
  * the decision record committed;
  * every `found` extraction has a non-null `evidence_chunk_id`.

### M15. In Phase 2 the pipeline subgraph has no caller, and the store step has no owner - Severity: Major
* **IDs:** `implementation-readiness-1-8`
* **Reviewer Lens:** `implementation-readiness`
* **Affected Scope:** Lines 230-233
* **Discrepancy Description:**
  * The main graph and router arrive in Phase 3, so in Phase 2 nothing says what calls the subgraph, or through which API.
  * The architecture ends the pipeline with "store" (line 53), but no task writes `extractions` or creates `reviews` rows.
  * Nothing says where `question` and `criteria` come from without the chat flow.
* **Rationale & Recommendation:**
  * State the Phase 2 entry point (for example, the existing job endpoint creates a `reviews` row and calls the subgraph).
  * Add tasks for creating the review and for a store node that writes screenings and extractions with `model` and `prompt_version`.

### M16. Loop 1's target conflicts with v1's `target_output_count`, and uncertain/failed papers aren't handled - Severity: Major
* **IDs:** `codebase-details-1-11`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Lines 231-232 (section 5.3, lines 83-86, for context)
* **Discrepancy Description:**
  * `Backend/schemas.py:10` defines `target_output_count` (default 25) as the "Number of papers to retrieve in search stage". `ui_app.py:52-55` defaults it to 10, and `agent.py:194` trims search results to it.
  * Loop 1 compares *included* papers against a target. Reusing this field would silently change what it means.
  * Screening has four buckets (`screening_agent.py:139-163`). The plan doesn't say whether `uncertain` counts toward the target, or how `uncertain` and `failed` are stored in `screenings.decision`.
* **Rationale & Recommendation:**
  * Add a separate `target_included` field.
  * Define the stored decision values (`include | exclude | uncertain | failed`) and whether uncertain papers count toward the target.
  * Reuse `matched_exclusion_criteria` (`screening_schemas.py:78-81`) as input to the query rewrite.

### M17. The extraction field list, status mapping and evidence linkage are never fixed - Severity: Major
* **IDs:** `codebase-details-1-12`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Lines 233-234
* **Discrepancy Description:**
  * `extraction_schemas.py:28-60` has 8 string fields with no status, and `FIELD_QUERIES` covers only 5 of them.
  * Extraction is one LLM call per paper, with joined context and no chunk IDs (`rag_extraction_main.py:44-70, 201-209`). v1 uses sentinel strings ("not specified", "no empirical dataset") instead of a status.
  * The plan doesn't say:
    * which fields get a status and evidence;
    * how the model cites a chunk;
    * how the sentinel strings map to a status;
    * whether extraction stays one call per paper.
* **Rationale & Recommendation:**
  * Fix the field list (the v1 five plus `paper_type`) and the mapping from sentinel strings to status.
  * Require chunk IDs in the prompt context.
  * Choose per-paper or per-field calls. Per-field calls fit Loop 2's per-field re-retrieval.

### M18. Line 226 defers the router benchmark to Phase 3, but Phase 3 has no task for it - Severity: Major
* **IDs:** `implementation-readiness-1-9`, `style-1-8`
* **Reviewer Lens:** `implementation-readiness`, `style`
* **Affected Scope:** Lines 226-227, 241, 247, 249
* **Discrepancy Description:**
  * Phase 3 has a router test set and an accuracy figure, but no comparison of router models and no task to replace the provisional `qwen3:8b`.
  * Line 227's "replace the provisional defaults" can be read as covering the router too.
  * "No tool calling" implies the router uses tool calling, but section 5.2 specifies structured output.
  * "Router accuracy is measured" has no threshold.
* **Rationale & Recommendation:**
  * Add a Phase 3 task: "Benchmark router models on the router test set; decision record; replace the provisional router default."
  * Make line 227 name only the screening, extraction and embedding roles.
  * Drop "No tool calling", or explain it.
  * Set a minimum accuracy, or state that there is none and why.

### M19. The Phase 3 exit doesn't check the Must features, two routes, or the interrupt points - Severity: Major
* **IDs:** `implementation-readiness-1-11`, `style-1-10`, `style-1-22`
* **Reviewer Lens:** `implementation-readiness`, `style`
* **Affected Scope:** Lines 241-246, 249
* **Discrepancy Description:**
  * "A full demo conversation" is a manual, unscripted check.
  * The exit doesn't verify the section 3 Must criteria: every claim cites a paper, every table cell links to a passage and page, and conversations survive a restart.
  * No task wires `new_topic` to the pipeline or handles `clarify`.
  * The `interrupt()` points in scope aren't named (section 5.2 has one; section 3 suggests more).
* **Rationale & Recommendation:**
  * Add a task: "`new_topic` route starts the pipeline subgraph; `clarify` route asks a follow-up question."
  * Name the interrupt points (for example, the low-retrieval check and before the Loop 1 re-search).
  * Rewrite the exit as a scripted fake-LLM conversation that:
    * exercises all four routes and one interrupt/resume;
    * restarts mid-conversation;
    * checks citations on every answer sentence and a chunk ID and page on every table cell;
    * ends in CSV and BibTeX export, with router accuracy and the confusion matrix reported.

### M20. Excel export is listed as Must in section 3 but missing from Phase 3 and the API - Severity: Major
* **IDs:** `style-1-9`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 243 (line 33 and line 64 for context)
* **Discrepancy Description:** Section 3 lists export as "CSV/Excel and BibTeX" (Must). Line 243 and the API (`format=csv|bibtex`) leave out Excel.
* **Rationale & Recommendation:** Either add Excel to line 243 and the API, or remove it from section 3 and record that decision.

### M21. BibTeX export needs authors and venue, which the planned data model doesn't store - Severity: Major
* **IDs:** `codebase-details-1-13`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Line 243 (section 6, line 123, for context)
* **Discrepancy Description:**
  * The `papers` table has no `authors` or `venue` column.
  * `search_agent/agent.py:173-184` captures authors.
  * Venue is only computed in the bypassed gatekeeper path (`agent.py:115-127`).
* **Rationale & Recommendation:**
  * Add `authors` (jsonb) and `venue` to `papers` in the Phase 1 migration.
  * Carry `primary_location.source.display_name` into the search output.
  * Note that the CSV export in `ui_app.py:251-258` can be reused.

### M22. The CI eval subset and CI deploy have no defined environment, and the Phase 4 exit covers only part of the phase - Severity: Major
* **IDs:** `implementation-readiness-1-10`, `style-1-13`, `style-1-19`
* **Reviewer Lens:** `implementation-readiness`, `style`
* **Affected Scope:** Lines 252, 255-256, 258 (lines 187 and 199 for context)
* **Discrepancy Description:**
  * Hosted CI runners have no Ollama models. A fake-LLM eval measures nothing, and the judge needs a Groq secret.
  * Deploying from CI to a `kind`/`k3d` cluster on a laptop isn't possible from a hosted runner.
  * Line 256's step order ("build images, eval subset, deploy") differs from section 9 ("lint, unit tests, eval subset, build images, deploy"). No phase says when the eval subset joins CI.
  * "One command deploys the full stack" doesn't define "full stack" (Ollama is outside the cluster). It doesn't check the probes, the migration Job, the worker or auth.
  * Line 255 drops "every query filters by `user_id`".
* **Rationale & Recommendation:**
  * Decide where the eval subset runs: a self-hosted runner, a scheduled local job, or a judge-only check on stored outputs.
  * Decide what CI "deploy" means (for example, build and push images in CI, and deploy locally with a script).
  * Match section 9's step order.
  * Rewrite the exit: "On a new cluster, one command brings up UI, API, worker, Postgres and Redis; the migration Job completes; readiness probes pass; a logged-in user runs a pipeline through the worker and sees only their own reviews."

### M23. Process terms in the phases and working rules are undefined - Severity: Major
* **IDs:** `style-1-6`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 203, 262, 284-288
* **Discrepancy Description:**
  * These terms aren't defined in the plan: "EGM", "EGM cycle", "major topic" (which collides with research "topic" and `new_topic`), "drift report", "drift-free", "task" and "step".
  * There is no naming rule for design docs, so "the relevant design doc" can't be located.
* **Rationale & Recommendation:** Add a short glossary, for example:
  * "Task = one checklist item in section 10."
  * "EGM cycle: brainstorm, then draft `docs/designs/<phase-or-topic>.md`, then review, implement, and write a drift report (code compared against the design doc)."
  * "Drift-free = the last drift report for each design doc lists no open items."

### M24. The Phase 5 exit and its "drift-free" task can't be checked - Severity: Major
* **IDs:** `style-1-14`, part of `implementation-readiness-1-13`
* **Reviewer Lens:** `style`, `implementation-readiness`
* **Affected Scope:** Lines 262, 265
* **Discrepancy Description:**
  * "Every claim in the README is backed by an eval result" would include architecture and design statements that no eval can back.
  * "Eval result" isn't defined.
  * "Drift-free" (line 262) has no check.
* **Rationale & Recommendation:**
  * Rewrite the exit: "Every quality or performance number in the README links to a results file in `eval/results/` or a LangSmith experiment."
  * Define drift-free as in M23.

---

### N1. "v1" and the `v1.0` tag mean different things - Severity: Nit
* **IDs:** `style-1-7` (the reviewer rated it Major; downgraded)
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 205, 210, 260, 265
* **Discrepancy Description:** "v1" means the legacy system, but `v1.0` is the release tag of the v2 project.
* **Rationale & Recommendation:** Under line 203, add: "Tags `v0.1`-`v1.0` version the v2 project; 'v1' elsewhere means the legacy system." Alternatively, rename the release tag.

### N2. Line 236 can be read two ways, and "hybrid" has several meanings - Severity: Nit
* **IDs:** `style-1-11` (the reviewer rated it Major; downgraded)
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 236
* **Discrepancy Description:** It's unclear whether "only if metrics improve" applies to chunk overlap, and it doesn't name the metrics. "Hybrid" also means three other things in the plan (lines 73, 163, 280).
* **Rationale & Recommendation:** "Add chunk overlap. Then try keyword plus vector search and a reranker separately; adopt each only if retrieval recall@k or extraction faithfulness improves."

### N3. Eval terms are used inconsistently - Severity: Nit
* **IDs:** `style-1-15`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 203, 225, 238, 256, 265
* **Discrepancy Description:**
  * The plan uses "eval harness", "eval script", "eval subset" and "eval result" without defining them.
  * The Phase 4 and Phase 5 exits don't mention eval, although line 203 says each phase from Phase 2 on is measured.
* **Rationale & Recommendation:** Define "eval harness" once, use only that term, and state what each phase reports.

### N4. "Secrets" means two different things - Severity: Nit
* **IDs:** `style-1-18`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 214, 253
* **Discrepancy Description:** "Secrets" means `.env` in Phase 1 and Kubernetes Secrets in Phase 4.
* **Rationale & Recommendation:** At line 214, write "API keys from `.env`".

### N5. Repeated statements, and rule 6 can be read as banning Phase 1 changes - Severity: Nit
* **IDs:** `style-1-20`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 203, 279, 285, 289
* **Discrepancy Description:**
  * "One phase at a time" appears three times, and "git tag" twice.
  * Rule 6 is broader than line 188's wording and can be read as banning Phase 1 changes, since no metrics exist before Phase 2.
* **Rationale & Recommendation:** Keep one statement of each, and reuse line 188's wording in rule 6.

### N6. Router wording doesn't match sections 5.2 and 8 - Severity: Nit
* **IDs:** `style-1-21`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 241, 247
* **Discrepancy Description:** Line 241 says "LLM + rule", but section 5.2 says "deterministic rules". Section 8 also requires a confusion matrix, which line 247 doesn't mention.
* **Rationale & Recommendation:** Align the wording with sections 5.2 and 8.

### N7. The free-tier caveat is repeated and not tied to a decision point - Severity: Nit
* **IDs:** `style-1-23`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 270, 278
* **Discrepancy Description:** "Verify before use" doesn't say when.
* **Rationale & Recommendation:** Move the check to the two points where it matters: choosing the judge model in Phase 2, and enabling the CI eval subset.

### N8. Risk table wording - Severity: Nit
* **IDs:** `style-1-24`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 277, 280
* **Discrepancy Description:**
  * Line 277 says "7B models" and "tool calling", but the provisional model is 8B and the plan uses structured output.
  * Line 280's "measure before adopting" doesn't say what is adopted.
* **Rationale & Recommendation:**
  * Line 277: "Small (7-8B) local models may return invalid structured output."
  * Line 280: point to the Phase 2 experiment at line 235.

### N9. Phase 0 wording - Severity: Nit
* **IDs:** `style-1-25`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 207-210
* **Discrepancy Description:**
  * "Bootstrap documentation" is EGM jargon.
  * Line 208 is a plain bullet inside a checklist, and line 210 repeats it.
  * "Gold dataset v0" can be confused with the `v0.x` tags.
* **Rationale & Recommendation:** Name the outputs (per-package READMEs, `CLAUDE.md`, `docs/backlog.md`), remove the repetition, and consider "gold dataset, version 0".

### N10. Unclear qualifiers on lines 223 and 226 - Severity: Nit
* **IDs:** `style-1-26`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 223, 226
* **Discrepancy Description:**
  * On line 223, "draft" can be read as the status of `eval_notes.md` or as an instruction.
  * On line 226, "target hardware" and "quality" are unreferenced.
* **Rationale & Recommendation:** Write "(draft brainstorm notes)". Point "target hardware" to section 11 and "quality" to the section 8 metrics.

### N11. Memory pressure in Phase 4 isn't in the risk table - Severity: Nit
* **IDs:** `implementation-readiness-1-15`
* **Reviewer Lens:** `implementation-readiness`
* **Affected Scope:** Lines 269, 274-280
* **Discrepancy Description:** Phase 4 runs a local cluster (UI, API, worker, Postgres and Redis) next to native Ollama with an 8B model, on a 16 GB machine.
* **Rationale & Recommendation:** Add the risk, with resource limits on the cluster and a smaller `local` model as mitigation.

### N12. The "no unbounded loops" exit ignores loops that already exist - Severity: Nit
* **IDs:** `codebase-details-1-14`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Line 238
* **Discrepancy Description:**
  * `search_agent/api_client.py:86-89` retries HTTP 429 with no limit.
  * `ui_app.py:144-165` polls with no timeout.
  * Loop 1 adds more OpenAlex calls on top of the unlimited retry.
* **Rationale & Recommendation:** Add a Phase 2 task to cap OpenAlex retries, or extend the exit criterion to cover it.

### N13. A FAISS edge case for short papers will disappear unnoticed in the pgvector move - Severity: Nit
* **IDs:** `codebase-details-1-15`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Lines 216, 236
* **Discrepancy Description:** For a paper with fewer than 5 chunks, FAISS returns -1 and `chunks[-1]` silently picks the last chunk (`document_processing_node.py:152-157`).
* **Rationale & Recommendation:** Note this in the Phase 2 eval design, so differences between baseline and new results on short papers are explained.

### N14. Checkpoints will carry chunk text, and the pre_* nodes add checkpoint writes - Severity: Nit
* **IDs:** `codebase-details-1-16`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Line 217
* **Discrepancy Description:**
  * Up to 25 chunks of 1200 characters per paper are stored twice in graph state (`document_processing_node.py:213-218`).
  * The `pre_*` nodes add one checkpoint write per stage.
* **Rationale & Recommendation:** Keep only chunk IDs in state once chunks are in Postgres. Consider replacing the `pre_*` nodes with streamed custom events in Phase 3.

### N15. Phase 0 is marked documented, but the bootstrap docs contain wrong statements - Severity: Nit
* **IDs:** `codebase-details-1-17`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Lines 207, 210
* **Discrepancy Description:**
  * `CLAUDE.md` lists `extract_agent.py`, `extraction_agent.py` and `extraction_main.py`, which don't exist (confirmed by the synthesizer).
  * `README.md:240-241` says `SCREENING_MODEL` overrides the model per stage, but `nodes.py:62` hardcodes it.
* **Rationale & Recommendation:** Add these corrections to `docs/backlog.md`. `CLAUDE.md` is loaded into every session.

### N16. There are no existing Kubernetes manifests to reuse in Phase 4 - Severity: Nit
* **IDs:** `codebase-details-1-18`
* **Reviewer Lens:** `codebase-details`
* **Affected Scope:** Line 252
* **Discrepancy Description:** The repo has no Kubernetes manifests. `deploy/NOTES.md` describes a cluster-hosted Ollama, which the plan moves out of the cluster.
* **Rationale & Recommendation:** Treat all Phase 4 manifests as new work. The `host.docker.internal` pattern (`docker-compose.yml:9,14-15`) and the pinned frontend requirements can be reused.
