# Goldfish Review Report

**Target:** `/Users/mohamedelsayed/PycharmProjects/literature-review-mas-neu/docs/plan_v2.md` (`Lines 1-200`: sections 1-9, goal through deployment and operations. Lines 201-294 were read for context only.)

**Mode:** REVIEW
**Standards applied:** `feature-spec-standard.md` (design, structural). The style lens had no document standard.
**Baseline context given to each reviewer:** `README.md`, `docs/backlog.md`, `docs/eval_notes.md`, `Orchestration/graph.py`, `Orchestration/state.py`

## Reviewer Status

| Reviewer | Status | Raw findings |
| --- | --- | --- |
| `design` (egm:egm-design) | completed | 28 (1 Blocker, 18 Major, 9 Nit) |
| `structural` (egm:egm-structural) | completed | 15 (1 Blocker, 7 Major, 7 Nit) |
| `style` (egm:egm-style) | completed | 30 (1 Blocker, 14 Major, 15 Nit) |

After deduplication there are 52 consolidated findings: **2 Blocker, 26 Major, 24 Nit**.

Severity notes:
- The design lens rated the field-status problem (B-2) as Major. The style lens rated it Blocker. It is kept as a Blocker because the Phase 2 exit criterion ("eval shows fewer empty fields", line 238) is met automatically as the plan is written.
- The design lens rated the Excel export mismatch (M-22) as a Nit. The style lens rated it Major. It is kept as Major because the mismatch is in the scope of a Must feature.

Every finding has a stable ID. Merged findings use the ID of the reviewer whose report was most complete, and list the other IDs under "Also reported as".

Two claims were checked against the baseline files before triage:
- The v1 README says local Ollama inference was too slow and was moved to a GPU cluster (README lines 67-70). The ~5 min figure comes from that cluster (README lines 101-109).
- `docs/eval_notes.md` is marked "draft, no decisions yet" (line 3), proposes recall@k (line 95), and makes the local results file the source of truth (line 104).

---

## Prioritized Findings (Blockers -> Major -> Nits)

### B-1. No alternatives considered for any major decision - Severity: Blocker
* **ID:** `design-1-1` (also reported as `structural-1-1`)
* **Reviewer Lens:** `design`, `structural`
* **Affected Scope:** Lines 43-199 (sections 5, 5.2, 6, 7, 7.1, 9)
* **Discrepancy Description**: The feature-spec standard fails a spec that proposes one path without naming rejected alternatives. Each major decision lists one option and nothing that was rejected:
  * a single Postgres + pgvector instance for library data, vectors, and checkpoints, instead of v1's in-memory FAISS or a separate store
  * SSE inside `POST /chat`, instead of v1's background job with polling, or a reconnectable event stream
  * Streamlit for streaming chat with `interrupt()`/resume
  * a hybrid LLM-plus-rule router, instead of rules only or an embedding classifier
  * moving inference from v1's GPU cluster to native Ollama on the laptop
  * OpenAlex as the only source
  * Groq for summary and judge
  * full-paper context versus chunk retrieval
  * async execution in the API until a Phase 4 queue exists

  Lines 192-193 give reasons in passing but do not name or reject an alternative.
* **Rationale & Recommendation**: Add an "Alternatives considered" section, either as an H2 after section 5 or as an H3 inside each affected section. For each decision, give at least one rejected option and a concrete trade-off: memory on 16 GB, operational complexity, latency, or lock-in.

### B-2. Field status conflates "paper does not report it" with "system failed to find it" - Severity: Blocker
* **ID:** `style-1-1` (also reported as `design-1-9`, `style-1-10`)
* **Reviewer Lens:** `style`, `design`
* **Affected Scope:** Section 5.3 Loop 2 (lines 88-91); section 8 Extraction row (line 173)
* **Discrepancy Description**: Line 89 defines three statuses, `found | not_reported | empty`, but gives no definition for any of them. Line 91 then sets every field still `empty` after two iterations to `not_reported`. This has three effects:
  * After a run, no field is `empty`, so the "share of empty fields" metric (line 173) is zero by construction. The Phase 2 exit criterion (line 238) is therefore met automatically.
  * A retrieval failure is stored as a claim about the paper's content. Because `extractions` are shared (line 125), that wrong claim is reused by every later review and user.
  * `eval_notes.md` scores `found`/`not_reported` against the paper's content, so these system failures would be scored against the wrong gold label.
* **Rationale & Recommendation**:
  * Define each status in one place, including what produces it (null output, failed validation, low confidence).
  * Add a separate terminal status, for example `not_found_after_retry`, and keep `not_reported` for "the paper does not contain it".
  * Measure the share of `not_found_after_retry`, and measure `not_reported` accuracy against gold.

---

### M-1. No problem statement or measurable success criteria - Severity: Major
* **ID:** `design-1-2` (also reported as `structural-1-2`)
* **Reviewer Lens:** `design`, `structural`
* **Affected Scope:** Section 1 Goal (lines 6-12); section 2 (lines 14-21); section 3 (lines 23-37)
* **Discrepancy Description**: Section 1 describes the product, and section 2 lists engineering gaps. Neither says what user problem the change from v1's one-shot screening table to a chat assistant with a growing library solves. The v1 README had a stated problem: screening for systematic reviews. No section gives v1.0 success thresholds for latency per run, faithfulness, empty-field share, or router accuracy. Line 188 only asks for a delta.
* **Rationale & Recommendation**: Add a short problem statement that names the user's pain, for example rerunning searches from zero, follow-up questions, and tracking a topic over time. Add a table of v1.0 success thresholds. Values may be placeholders marked "set after the Phase 2 baseline".

### M-2. Local-laptop inference contradicts v1's measured finding; the v1 baseline is misstated - Severity: Major
* **ID:** `design-1-3` (also reported as `style-1-3`)
* **Reviewer Lens:** `design`, `style`
* **Affected Scope:** Section 2 (lines 16-21); section 7 (lines 141-156); section 9 (lines 192-193)
* **Discrepancy Description**: The v1 README (lines 67-70) says local Ollama was too slow, so inference moved to a GPU cluster. The ~5 min figure on line 16 is for a 5-paper run on that cluster (README lines 101-109). v2 runs router, screening, and extraction on a fanless 16 GB MacBook Air, and it adds two retry loops, full-paper context, a default target of 10 papers, and a router call on every message.

  The plan has:
  * no latency or token budget per run
  * no estimate of calls per run, including the worst case for the loops
  * no statement on whether the GPU cluster is still available
  * no fallback if no local model meets an acceptable speed

  Line 21's "almost no tests" also understates what the README records: one suite, 11 tests, 3 failing.
* **Rationale & Recommendation**:
  * Line 16: say the ~5 min figure is from a 5-paper GPU-cluster run and has not been measured locally.
  * Say whether the cluster is still an option.
  * Add a per-run budget, for example "10 papers under N minutes on M4", and an estimate of calls per run.
  * Name the fallback if the budget is missed: GPU host, fewer papers, or chunk-only extraction.
  * Replace "almost no tests" with the concrete figure.

### M-3. Groq free tier and the shared summary/judge model - Severity: Major
* **ID:** `design-1-4` (also reported as `style-1-26`)
* **Reviewer Lens:** `design`, `style`
* **Affected Scope:** Section 7 (lines 147-148); section 8 (lines 181, 187)
* **Discrepancy Description**:
  * Summary and judge use the same Groq model, so interactive summaries, eval runs, and CI all draw on one free-tier quota.
  * A summary built from a 10-paper evidence table may exceed per-request or per-minute token caps. It would then always fall back to the local 8B model, and nothing in the output would show it.
  * Using the same model as summarizer and judge breaks the plan's own rule on line 181, "Judge model must be stronger than the system model."
  * The judge entry looks final, while `eval_notes.md` makes Groq conditional on the free tier.
  * `fallback: ollama` names no model.
* **Rationale & Recommendation**:
  * Estimate tokens per summary and per eval run, and check them against current limits. Section 11 already says limits change.
  * Use a different, stronger judge for the summary and chat-answer evals, or document the exception.
  * Mark the judge `# provisional` and name the fallback model.
  * Record in the output when a summary fell back to the local model.

### M-4. The checkpointer does not make async in-API execution safe; the run is tied to the SSE request - Severity: Major
* **ID:** `design-1-5` (also reported as `style-1-14`)
* **Reviewer Lens:** `design`, `style`
* **Affected Scope:** Section 9 (line 197); section 5.1 (lines 62-63)
* **Discrepancy Description**: A checkpointer saves state at node boundaries. It does not restart a run that was in progress when the API process died. Something must find unfinished threads and invoke the graph again, and the node that was running is lost.

  If the pipeline runs inside the `POST /chat` SSE response, a client disconnect, a Streamlit rerun, or a proxy timeout can cancel it. There is no endpoint to reconnect to a running pipeline or read its status. The plan also does not say how progress from the Phase 4 worker reaches the API's SSE stream. This puts the Must feature "conversations survive restarts" at risk.
* **Rationale & Recommendation**:
  * Decouple the run from the request: start it as a background task keyed by `thread_id`.
  * Add a reconnectable events endpoint, for example `GET /chat/{thread_id}/events`, and a run-status endpoint.
  * Define what happens at startup for threads with an incomplete checkpoint: resume, or mark them failed.
  * Name the progress channel between worker and API, for example Redis pub/sub or Postgres LISTEN/NOTIFY.
  * Rewrite line 197 to describe what the checkpointer actually provides.

### M-5. Full-paper context: silent truncation risk and an unproven caching claim - Severity: Major
* **ID:** `design-1-6` (also reported as `style-1-27`)
* **Reviewer Lens:** `design`, `style`
* **Affected Scope:** Section 7 (line 156); section 7.1 (lines 158-164)
* **Discrepancy Description**:
  * "When it fits the context window" does not say which window. The limit that matters is Ollama's configured `num_ctx`, which is usually much smaller than the model's maximum.
  * Ollama truncates an over-long prompt without an error. With the stable → variable order on line 160, the system prompt and schema can be the parts that are lost.
  * Raising `num_ctx` costs KV-cache memory on a 16 GB machine that also runs Docker and Postgres.
  * Line 160 says the ordering "enables prefix/prompt caching" but gives no evidence that Ollama or Groq reuses the prefix for these models.
  * "CAG" is never expanded.
  * Line 164's "data from different users" is unclear, because library data is shared.
* **Rationale & Recommendation**:
  * Make the fit check a token count against the configured `num_ctx` minus an output reserve, and fail loudly instead of truncating.
  * State the `num_ctx` value and its memory cost.
  * Describe caching as an expected optimisation to be measured.
  * Expand CAG.
  * Change line 164 to "private data (reviews, screenings, conversations)".

### M-6. Shared extractions have no versioning or review scoping - Severity: Major
* **ID:** `design-1-7`
* **Reviewer Lens:** `design`
* **Affected Scope:** Section 6 (lines 115, 125, 135); section 4 (line 41)
* **Discrepancy Description**: `extractions` is shared across reviews and users, has no `review_id`, and has no uniqueness rule.
  * The v1 field `relevance_to_research_question` only makes sense per review.
  * Nothing says which row is current when the same (paper, field) is extracted again with a new `model` or `prompt_version`. That will happen right after the Phase 2 benchmark.
  * A Loop 2 outcome in one review becomes the answer for every later review.
* **Rationale & Recommendation**:
  * List the extraction field set and move review-specific fields to a per-review table.
  * Add a uniqueness or versioning rule, for example unique (`paper_id`, `field`, `model`, `prompt_version`) plus a rule for which row is current.
  * Define when shared extractions are recomputed.

### M-7. A fixed extraction schema contradicts "domain-agnostic" - Severity: Major
* **ID:** `design-1-8`
* **Reviewer Lens:** `design`
* **Affected Scope:** Section 1 (line 10); section 4 (line 41)
* **Discrepancy Description**: Custom fields are a non-goal, so the schema is fixed. The v1 schema (`paper_type`, `method`, `dataset`, `task`, ...) is shaped for ML and CS papers. For the social-science and civil-engineering topics in `eval_notes.md`, many fields will legitimately be `not_reported`. That inflates the empty-field metric and makes the evidence table less useful.
* **Rationale & Recommendation**: List a generic, cross-domain field set in the plan, or narrow the "domain-agnostic" claim until custom fields are supported.

### M-8. Key enumerations and schemas are undefined - Severity: Major
* **ID:** `structural-1-8`
* **Reviewer Lens:** `structural`
* **Affected Scope:** Section 6 table (lines 117-125); section 3 Evidence table (line 32)
* **Discrepancy Description**: The plan does not define:
  * the allowed values of `screenings.decision` (v1 has included, excluded, uncertain, failed)
  * the shape of `reviews.criteria` (jsonb)
  * the fixed list of extraction fields, which determines the evidence table's columns

  By contrast, `extractions.status` is listed (line 89).
* **Rationale & Recommendation**: Add an H3 under section 6, for example "Enumerations and schemas", listing the decision values, the criteria shape, and the extraction field list. Mark which fields need evidence.

### M-9. "Every cell links to its source passage" cannot hold as designed - Severity: Major
* **ID:** `design-1-10` (also reported as `style-1-5`)
* **Reviewer Lens:** `design`, `style`
* **Affected Scope:** Section 3 (line 32); section 6 (lines 125, 130-131); section 7.1 (lines 161, 163)
* **Discrepancy Description**:
  * In full-paper mode no chunk is retrieved, so `evidence_chunk_id` has nothing to reference.
  * Cells with status `not_reported` or `empty` have no passage.
  * `eval_notes.md` notes that fields such as `relevance_to_research_question` and `confidence` have no evidence page.
* **Rationale & Recommendation**:
  * Narrow the requirement to "every cell with status `found` links to its evidence chunk and page", and list the exempt fields.
  * In full-paper mode, require a verbatim quote from the model and map it to a chunk and page by string matching.
  * If matching fails, force `status != found`.
  * Add a page-correctness check to section 8.

### M-10. Library QA: the context mechanism contradicts itself and the scope is undefined - Severity: Major
* **ID:** `design-1-11`
* **Reviewer Lens:** `design`
* **Affected Scope:** Section 5 (line 52); section 5.2 (line 79); section 6 (line 115); section 7.1 (lines 161-162)
* **Discrepancy Description**:
  * Line 79 says the library route retrieves chunks. Line 161 says library QA puts the evidence table in context. These are two different designs.
  * An evidence table for a growing library will not fit an 8B context, and line 162 itself says growing data should be retrieved.
  * "The library" is not scoped. Retrieving over all shared chunks shows users which papers other users' reviews pulled in, which is an information leak once there are multiple users.
* **Rationale & Recommendation**: Pick one mechanism for library QA. Scope retrieval to papers included in the user's own reviews, or in the current review, and enforce that in the query.

### M-11. The chat flow never collects the inputs the pipeline needs - Severity: Major
* **ID:** `design-1-12`
* **Reviewer Lens:** `design`
* **Affected Scope:** Section 3 (lines 28-29, 36); section 6 (lines 120-121)
* **Discrepancy Description**:
  * The pipeline needs `min_year`, inclusion and exclusion criteria, and a target count (`Orchestration/state.py`). The plan does not say how a `new_topic` message becomes a `reviews` row with criteria.
  * "Confirm query" is only a Should.
  * `conversations` has one `review_id`. The plan does not say what happens when a second `new_topic` arrives in the same conversation.
* **Rationale & Recommendation**:
  * Specify how criteria are collected: the `clarify` route, a form, or LLM-proposed criteria plus a confirmation `interrupt()`.
  * Make that confirmation Must if the pipeline cannot run without it.
  * Define conversation-to-review as one-to-many, or say that a new topic starts a new conversation.

### M-12. Paper deduplication and ingestion state are incomplete - Severity: Major
* **ID:** `design-1-13`
* **Reviewer Lens:** `design` (the ingestion-failure part was also raised in `structural-1-3`)
* **Affected Scope:** Section 3 (line 29); section 6 (lines 123, 129)
* **Discrepancy Description**:
  * `ON CONFLICT ... DO UPDATE` targets one constraint. An upsert on `openalex_id` still fails on the unique `doi` when two OpenAlex works share a DOI.
  * OpenAlex merges and redirects IDs, and preprint and journal versions get different IDs, so "no duplicates" is not guaranteed. `eval_notes.md` already found a duplicate.
  * `papers` has no ingestion status (pending, downloaded, chunked, PDF unavailable, failed). Without one, "download and chunk each paper once" cannot be implemented idempotently, and failures cannot be retried or skipped.
  * Loop 1 counts papers without a usable PDF toward the target of 10.
* **Rationale & Recommendation**:
  * Choose one conflict key and handle DOI collisions explicitly.
  * Add a status column and a retry policy to `papers`.
  * Count only extractable papers toward the Loop 1 target, or report both counts.

### M-13. Checkpoint tables will grow without bound - Severity: Major
* **ID:** `design-1-14`
* **Reviewer Lens:** `design`
* **Affected Scope:** Section 5.1 (line 68); section 5.3 (line 93); section 6 (line 133)
* **Discrepancy Description**: `PostgresSaver` writes channel values at every step. v1 state carries full paper dicts and screening results. If v2 state carries full text or chunks, the checkpoint tables will grow quickly in the same database as the library, and there is no retention rule.
* **Rationale & Recommendation**: State that graph state holds IDs and small values only, and that payloads are read from library tables. Define a checkpoint retention or pruning rule.

### M-14. No failure-mode or security analysis; the auth rule contradicts the shared tables - Severity: Major
* **ID:** `design-1-15` (also reported as `structural-1-3`, `style-1-15`)
* **Reviewer Lens:** `design`, `structural`, `style`
* **Affected Scope:** Sections 5, 6, 7, 9 (lines 43-199), in particular lines 62-65, 123, 132, 148, 198
* **Discrepancy Description**: Sections 1-9 do not discuss security or failure modes. Specific gaps:
  * **Untrusted downloads:** PDFs come from arbitrary publisher URLs, with possible redirects to internal addresses when running inside the cluster, no size limit, and untrusted files parsed by PyMuPDF.
  * **Prompt injection:** paper text goes straight into prompts, and shared extractions spread a poisoned result to every user.
  * **Unauthenticated API:** endpoints run without auth until Phase 4, although `users.email` and private reviews exist from Phase 1.
  * **No ownership checks:** checkpoint tables have no `user_id`, so `/chat/resume` and `GET /reviews/{id}/...` need explicit ownership checks.
  * **Auth rule contradicts the schema:** line 198, "every query filters by `user_id`", cannot be true for `papers`, `chunks`, and `extractions`, which have no `user_id`. "Simple authentication" is not specified.
  * **No fallbacks:** none is defined for OpenAlex outages or rate limits, or for the judge.
* **Rationale & Recommendation**:
  * Add a "Failure modes and security" subsection covering:
    * a URL allowlist or no-redirect downloads, with size and time limits
    * how paper text is handled to limit prompt injection
    * ownership checks on every `thread_id` and `review_id` endpoint
    * OpenAlex and judge fallbacks
  * Rewrite line 198 as "every query on private tables (`reviews`, `conversations`, `screenings`) filters by `user_id`", or consider Postgres row-level security.
  * Name the auth mechanism, or defer it explicitly to the Phase 4 design.

### M-15. Private data is sent to external services without saying so - Severity: Major
* **ID:** `design-1-16`
* **Reviewer Lens:** `design`
* **Affected Scope:** Section 5.1 (line 69); section 7 (lines 147-148)
* **Discrepancy Description**:
  * Summary requests send review questions, criteria, and conversation content to Groq.
  * LangSmith traces contain every prompt, including user conversations.
  * The v1 README says no external LLM API is used. v2 changes this without stating it, which matters once there are multiple users.
* **Rationale & Recommendation**: Add a short data-flow section that says where user data goes. Add a per-deployment flag to turn off external providers and tracing. Update the README claim.

### M-16. The CI eval subset may not be feasible - Severity: Major
* **ID:** `design-1-17` (also reported as `style-1-29`)
* **Reviewer Lens:** `design`, `style`
* **Affected Scope:** Section 8 (line 187); section 9 (line 199)
* **Discrepancy Description**:
  * CI runners have no Ollama and no GPU. With the fake LLM, the eval measures nothing. With a real 8B model on CPU, it is slow.
  * The judge depends on the Groq free tier and the results depend on LangSmith, so an outside rate limit can block merges.
  * "Small subset" and "deploy" have no size or target.
* **Rationale & Recommendation**:
  * Specify the CI eval inputs: frozen recorded LLM outputs, or a self-hosted runner.
  * Make the LangSmith upload optional, as `eval_notes.md` line 104 proposes.
  * When the judge is rate-limited, skip and mark the run instead of failing it.
  * Give the subset size or time budget, and the deploy target.

### M-17. Section 8 reads as final but conflicts with `eval_notes.md` and has metric gaps - Severity: Major
* **ID:** `design-1-18` (also reported as `structural-1-7`, `style-1-11`)
* **Reviewer Lens:** `design`, `structural`, `style`
* **Affected Scope:** Section 8 (lines 166-188); header line 4; section 7 (line 156)
* **Discrepancy Description**: Line 4 says "approved direction", but `eval_notes.md` is "draft, no decisions yet" (line 3) and disagrees with section 8:
  * **Screening:** line 172 uses judge agreement. The notes score screening deterministically against gold labels, and their weak point 1 shows that plain accuracy misleads when classes are imbalanced.
  * **Results store:** line 186 logs results as LangSmith experiments. The notes make the local results file the source of truth.
  * **Missing metrics:** section 8 has no retrieval recall@k, although line 156 relies on a benchmark to choose the embedding model. It also has no metric for evidence-page correctness (a Must feature) and none for whether the loops help.
* **Rationale & Recommendation**:
  * Add a status line under the section 8 heading: "Provisional; settled at the start of Phase 2 from `docs/eval_notes.md`."
  * Add recall@k, evidence-page accuracy, and per-loop yield.
  * Align the screening metric with include and exclude recall.

### M-18. Router: a Must feature depends on a Should, and thresholds are undefined - Severity: Major
* **ID:** `design-1-19` (also reported as `style-1-9`)
* **Reviewer Lens:** `design`, `style`
* **Affected Scope:** Section 3 (lines 28, 31, 36); section 5.2 (line 79)
* **Discrepancy Description**:
  * The Router is Must, but its rule needs `interrupt()`, which is Should.
  * "Below threshold" and "too few papers" have no values or parameter names, unlike Loop 1's `target` (default 10). Similarity thresholds also depend on the embedding model, which is provisional.
  * The `context` route has no rule for carrying forward the citations from earlier turns.
* **Rationale & Recommendation**:
  * Promote the needed `interrupt()` to Must, or define a fallback that does not need it.
  * Name the parameters, for example `library_min_score` and `library_min_papers`, with provisional defaults. Make them configuration set per embedding model and recalibrated when the model changes.
  * Require context-route answers to keep the citations from earlier turns.

### M-19. Most features in the table have no design; HITL scope is open-ended; endpoints are missing - Severity: Major
* **ID:** `structural-1-4` (also reported as `style-1-7`, `design-1-23`)
* **Reviewer Lens:** `structural`, `style`, `design`
* **Affected Scope:** Section 3 table (lines 25-37) against section 5 (lines 58-111) and the API in section 5.1 (lines 62-65)
* **Discrepancy Description**:
  * Only Router (5.2) and Pipeline loops (5.3) have design subsections. Cited answers/Library QA, the context route, the evidence table, the screening log, and the research summary have none.
  * HITL (line 36) says "e.g. confirm query, approve re-search". Only the library-coverage interrupt (line 79) is designed. Loop 1 re-searches with no approval step, and query confirmation is designed nowhere.
  * There are no endpoints to list conversations or reviews, load chat history, or fetch the screening log or summary.
* **Rationale & Recommendation**:
  * Add an H3 per Must and Should feature, or add a "Designed in" column to the section 3 table.
  * Remove "e.g." and list every interrupt point with its owning section.
  * Add the missing read endpoints.

### M-20. The architecture diagram does not match the router's four routes - Severity: Major
* **ID:** `structural-1-5` (also reported as `style-1-8`)
* **Reviewer Lens:** `structural`, `style`
* **Affected Scope:** Line 28; diagram lines 50-53; section 5.2 (lines 75-79)
* **Discrepancy Description**: The router has four routes (`context`, `library`, `new_topic`, `clarify`), but the diagram shows three differently named targets (Context, Library QA, Pipeline).
  * `new_topic` → Pipeline is implied, not stated.
  * `clarify` has no node, and no section defines its behaviour.
  * The research summary (line 35) is reachable from no route.
  * The library-route interrupt is not drawn.
* **Rationale & Recommendation**: Label each edge with its route value. Add a `clarify` path and define it in 5.2. Show where summary generation sits. Alternatively, add a route → target table in 5.2.

### M-21. Pipeline stages are listed differently in each place; there is no ingestion stage - Severity: Major
* **ID:** `structural-1-6`
* **Reviewer Lens:** `structural`
* **Affected Scope:** Lines 17, 53, 101, 129
* **Discrepancy Description**:
  * Line 53 lists search → screening → retrieval → extraction → store.
  * Line 101 lists search, screening, retrieval, extraction, with no store or ingestion module.
  * Line 129 requires "download and chunk each paper once", but neither list has a download, parse, or chunk stage. v1 has one (`document_processing_node` in `Orchestration/graph.py`).
  * Where Loop 2's re-retrieval sits relative to ingestion is unclear.
* **Rationale & Recommendation**: Define one canonical list of stage names and use it in the diagram, the repository layout, and section 6. Include an explicit ingestion stage (download, parse, chunk, embed) and say which module owns persistence.

### M-22. Excel export is in the feature list but not in the API - Severity: Major
* **ID:** `style-1-6` (also reported as `design-1-23`, `structural-1-4`)
* **Reviewer Lens:** `style`, `design`, `structural`
* **Affected Scope:** Line 33 against line 64
* **Discrepancy Description**: The Must feature promises "CSV/Excel and BibTeX", but the endpoint accepts only `format=csv|bibtex`. The Phase 3 checklist also says "CSV, BibTeX". It is unclear whether Excel is in scope.
* **Rationale & Recommendation**: Remove "Excel" from line 33, or add `xlsx` to the endpoint.

### M-23. "v1" refers to two different things - Severity: Major
* **ID:** `style-1-2`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 1, 4, 14, 39 (and the section 10 tags, for context)
* **Discrepancy Description**: "v1" is the legacy codebase (section 2), while "v1.0" is the release target of this v2 project (line 39, "until v1.0"). The tags run from `v0.1` to `v1.0` under a "v2" title, so "until v1.0" reads ambiguously.
* **Rationale & Recommendation**: Call the old system "v1 (legacy)" throughout. Add one sentence near the top: "Release tags for v2 run from `v0.1` to `v1.0`; `v1.0` is the first v2 release."

### M-24. "Every claim references a paper" cannot be checked as written - Severity: Major
* **ID:** `style-1-4`
* **Reviewer Lens:** `style`
* **Affected Scope:** Section 3 (line 31); section 8 (line 174)
* **Discrepancy Description**: "Claim" is not defined. The requirement says "every", but section 8 measures a rate. It is unclear whether `context`-route answers must cite papers.
* **Rationale & Recommendation**: Define the unit, for example "every sentence stating a finding from the literature cites at least one library paper". Say which routes it applies to, and set the target as a measured rate with a threshold.

### M-25. Judge calibration has no pass condition; "stronger" is not measurable - Severity: Major
* **ID:** `style-1-12`
* **Reviewer Lens:** `style`
* **Affected Scope:** Section 8 Judge rules (lines 181-182)
* **Discrepancy Description**: "Before trusting results" leads to no decision, because no threshold or statistic is given. "Stronger than the system model" has no definition.
* **Rationale & Recommendation**: State the acceptance rule, for example "agreement >= 0.8 or Cohen's kappa >= 0.6; below that, report results as uncalibrated". Define "stronger", for example as a larger model family or higher agreement with human labels on the calibration set.

### M-26. "Must show a metric delta" accepts noise as improvement - Severity: Major
* **ID:** `style-1-13`
* **Reviewer Lens:** `style`
* **Affected Scope:** Section 8 Process (line 188)
* **Discrepancy Description**: `eval_notes.md` (weak point 4, line 84) estimates +/-8-10 points at n = 60. Any delta, including noise, satisfies the rule as written.
* **Rationale & Recommendation**: Require a delta larger than run-to-run variance on the fixed dataset, judged by a decision rule written before the run.

---

### N-1. A single `/health` endpoint for both liveness and readiness - Severity: Nit
* **ID:** `design-1-20`
* **Reviewer Lens:** `design`
* **Affected Scope:** Line 195
* **Discrepancy Description**: If `/health` checks dependencies, pods restart whenever Postgres or Ollama is down. If it does not, the readiness probe tells you nothing.
* **Rationale & Recommendation**: Split liveness and readiness.

### N-2. Kubernetes does not run a Job before a Deployment - Severity: Nit
* **ID:** `design-1-21`
* **Reviewer Lens:** `design`
* **Affected Scope:** Line 196
* **Discrepancy Description**: Kubernetes has no ordering between a Job and a Deployment, so the API can start before migrations have run.
* **Rationale & Recommendation**: Use an initContainer that waits for or runs the migration, or a Helm hook.

### N-3. Postgres as a Deployment with no persistent storage - Severity: Nit
* **ID:** `design-1-22`
* **Reviewer Lens:** `design`
* **Affected Scope:** Line 193
* **Discrepancy Description**: On kind or k3d, data is lost without a PVC.
* **Rationale & Recommendation**: Use a StatefulSet with a PVC, or run Postgres outside the cluster.

### N-4. Open choices and rules without a trigger - Severity: Nit
* **ID:** `structural-1-11` (also reported as `style-1-25`, `design-1-24`)
* **Reviewer Lens:** `structural`, `style`, `design`
* **Affected Scope:** Lines 36, 134, 154, 193
* **Discrepancy Description**: These are left open:
  * "SQLAlchemy (or SQLModel)"
  * "e.g. LangChain `with_fallbacks`"
  * "`kind` or `k3d`"
  * "e.g. confirm query"
  * the HNSW index added "when chunk volume requires it", with no measurable trigger

  Open choices make it hard to check later whether the code has drifted from the plan.
* **Rationale & Recommendation**: Decide each one, or mark it "decided in the Phase N design doc". Give the HNSW trigger as a chunk count or a query latency.

### N-5. Queries over mixed embedding models - Severity: Nit
* **ID:** `design-1-25`
* **Reviewer Lens:** `design`
* **Affected Scope:** Lines 124, 156
* **Discrepancy Description**: There is one vector column with a per-row `embedding_model`, so every similarity query must filter by model. The plan does not say so.
* **Rationale & Recommendation**: State the filter rule.

### N-6. The screening log has no history and "PRISMA-style" is undefined - Severity: Nit
* **ID:** `design-1-26` (also reported as `style-1-22`)
* **Reviewer Lens:** `design`, `style`
* **Affected Scope:** Lines 34, 122
* **Discrepancy Description**: The (`review_id`, `paper_id`) primary key keeps no history across re-runs. PRISMA implies counts per stage, including papers removed by the year prefilter and counts per search iteration. The feature only stores a reason per paper.
* **Rationale & Recommendation**: Expand the acronym and state the subset delivered. Add search-iteration columns or a table if counts are intended.

### N-7. The `embedding` role in `get_llm` is not a chat model - Severity: Nit
* **ID:** `design-1-27`
* **Reviewer Lens:** `design`
* **Affected Scope:** Lines 146, 151
* **Discrepancy Description**: `get_llm(role)` also covers `embedding`, which is not a chat model, and the plan does not say what it returns for that role.
* **Rationale & Recommendation**: State the return type per role.

### N-8. Ollama is a single point of failure - Severity: Nit
* **ID:** `design-1-28`
* **Reviewer Lens:** `design`
* **Affected Scope:** Lines 143-146
* **Discrepancy Description**: Router, screening, and extraction have no fallback, so if Ollama is down the whole app is down.
* **Rationale & Recommendation**: State that this is accepted at this scale.

### N-9. Bold labels are used as headings - Severity: Nit
* **ID:** `structural-1-9`
* **Reviewer Lens:** `structural`
* **Affected Scope:** Lines 21, 83, 88, 127, 177, 184
* **Discrepancy Description**: "**Known gaps:**", "**Loop 1 ...**", "**Rules**", "**Judge rules**", and "**Process**" are bold labels, not headings, so they do not appear in a table of contents or as anchors.
* **Rationale & Recommendation**: Turn them into numbered H3 or H4 headings.

### N-10. Goals and non-goals are split and formatted differently - Severity: Nit
* **ID:** `structural-1-10`
* **Reviewer Lens:** `structural`
* **Affected Scope:** Line 8; line 41
* **Discrepancy Description**: The goal is one compound sentence with no measurable outcome. The non-goals are a single line separated by middle dots, two sections later. "(until v1.0)" does not say whether they are deferred or excluded permanently.
* **Rationale & Recommendation**: Pair them as H3s under one H2, write the non-goals as a bulleted list, and give each a reason.

### N-11. The architecture diagram leaves out components named elsewhere - Severity: Nit
* **ID:** `structural-1-12`
* **Reviewer Lens:** `structural`
* **Affected Scope:** Lines 45-56; lines 193, 197
* **Discrepancy Description**: Line 55 lists three components with no connectors. The worker, Redis, and LangSmith are missing, and 5.1 does not mention the worker.
* **Rationale & Recommendation**: Draw consumer edges to OpenAlex, Postgres, and the LLM layer. Add the Phase 4 components, or say they are left out on purpose.

### N-12. Code blocks have no language tag - Severity: Nit
* **ID:** `structural-1-13`
* **Reviewer Lens:** `structural`
* **Affected Scope:** Lines 45, 97
* **Discrepancy Description**: These two blocks are untagged. The block at line 141 is tagged `yaml`.
* **Rationale & Recommendation**: Tag both as `text`.

### N-13. The repository layout is incomplete - Severity: Nit
* **ID:** `structural-1-14`
* **Reviewer Lens:** `structural`
* **Affected Scope:** Section 5.4 (lines 98-108)
* **Discrepancy Description**: `docs/` leaves out `backlog.md` and `eval_notes.md`, and no module is given for the worker.
* **Rationale & Recommendation**: List the tracked docs and add a worker entry, marked as Phase 4.

### N-14. The Priority column mixes scales - Severity: Nit
* **ID:** `structural-1-15`
* **Reviewer Lens:** `structural`
* **Affected Scope:** Line 37
* **Discrepancy Description**: "Later (Phase 4)" mixes a priority with a phase. Phase 4 (`v0.5`) is before v1.0, which conflicts with both "Later" and the "until v1.0" framing.
* **Rationale & Recommendation**: Use one priority scale and add a separate Phase column.

### N-15. "North-star document" is jargon - Severity: Nit
* **ID:** `style-1-16`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 3
* **Discrepancy Description**: "North-star" is jargon a new reader may not know.
* **Rationale & Recommendation**: Use "Reference plan for v2."

### N-16. "Approved direction" does not say who approved it - Severity: Nit
* **ID:** `style-1-17`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 4
* **Discrepancy Description**: The status names no approver.
* **Rationale & Recommendation**: Name the approver, or use "Status: active".

### N-17. "OpenAlex (open access) only" is ambiguous - Severity: Nit
* **ID:** `style-1-18`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 12
* **Discrepancy Description**: It is unclear whether "open access" describes OpenAlex or the papers.
* **Rationale & Recommendation**: "Open-access papers from OpenAlex only."

### N-18. The known-gaps list overlaps itself - Severity: Nit
* **ID:** `style-1-19`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 21
* **Discrepancy Description**: "Linear graph with no conditional routing" says the same thing twice. "Every run starts from zero" partly overlaps "no persistence".
* **Rationale & Recommendation**: Use "linear graph (no conditional edges)" and "papers are not reused across runs".

### N-19. Line 19 is vague and does not say why it matters - Severity: Nit
* **ID:** `style-1-20`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 19
* **Discrepancy Description**: "Raw" and "several files" are imprecise, and the line does not connect to the `get_llm` design.
* **Rationale & Recommendation**: Name the modules and add "(motivates `get_llm`, section 7)".

### N-20. "Follow-up questions work" cannot be measured - Severity: Nit
* **ID:** `style-1-21`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 27
* **Discrepancy Description**: The feature description gives no testable condition.
* **Rationale & Recommendation**: "Follow-ups are resolved against earlier turns in the same thread (`rewritten_query`); conversation state survives an API restart."

### N-21. "Report the actual count honestly" contains filler - Severity: Nit
* **ID:** `style-1-23`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 86
* **Discrepancy Description**: "Honestly" adds nothing to the instruction.
* **Rationale & Recommendation**: "Report the included count and, if it is below target, state the shortfall."

### N-22. Repeated statements - Severity: Nit
* **ID:** `style-1-24`
* **Reviewer Lens:** `style`
* **Affected Scope:** Lines 67 and 151; lines 102 and 111; lines 161 and 163
* **Discrepancy Description**: The factory rule, the versioned-prompts rule, and the full-paper versus chunks rule are each stated twice.
* **Rationale & Recommendation**: Keep each statement once and cross-reference it.

### N-23. Profiles are not defined - Severity: Nit
* **ID:** `style-1-28`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 153
* **Discrepancy Description**: The plan does not say which roles change between the `local` and `cloud` profiles.
* **Rationale & Recommendation**: Add one line per profile.

### N-24. "Rules" is plural, but only one rule is given - Severity: Nit
* **ID:** `style-1-30`
* **Reviewer Lens:** `style`
* **Affected Scope:** Line 73
* **Discrepancy Description**: "Deterministic rules" is followed by a single rule (step 2).
* **Rationale & Recommendation**: Use "rule", or list the other rules.

---

## Categories with no findings

- Skipped heading levels, broken tables, and unclosed code blocks: none (`structural`).
- Promotional or marketing language: none, apart from "honestly" in N-21 (`style`).
- Caveats with no decision attached: none (`style`).
