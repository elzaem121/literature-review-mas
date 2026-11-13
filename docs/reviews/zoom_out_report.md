# Goldfish Review Report

**Target:** `/Users/mohamedelsayed/PycharmProjects/literature-review-mas-neu/docs/plan_v2.md` (full file, lines 1-294; the file has 295 lines)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-zoom-out` | completed |
| `egm-inventive-catalyst` | completed |

Both reviewers read the same baseline material first: `README.md`, `docs/backlog.md`, `docs/eval_notes.md`, `Orchestration/graph.py` and `Orchestration/state.py`. The Zoom Out reviewer also checked how the v1 code reuses components (`tracing.py`, the three instructor client setups, `extract_agent/extraction_schemas.py`, `extract_agent/document_processing_node.py`, `Backend/main.py`, `requirements.txt`).

## Severity Summary

| Severity | Count |
| --- | --- |
| Blocker | 0 |
| Major | 16 |
| Nit | 6 |

Raw findings: Zoom Out 14 (9 Major, 5 Nit), Inventive Catalyst 13 (10 Major, 3 Nit). After deduplication: 22 findings. Five findings were merged across the two lenses, and one of those (Loop 1 counting) was raised to Major because the merged scope is larger than either report alone.

No reviewer proposed a Blocker. Zoom Out found that the plan passes its context check and that nothing stops Phase 1 from starting. Under its persona, Inventive Catalyst can only use Major or Nit in REVIEW mode. Several Major findings affect the Phase 1 schema and migrations (findings 1, 2, 3, 6, 7, 13, 15, 16). They are cheaper to settle before the Alembic models exist than after.

## Prioritized Findings (Blockers -> Major -> Nits)

Findings are grouped by reviewer lens. A finding raised by both lenses appears once, under Zoom Out, and lists both lenses.

---

## Zoom Out findings

### 1. Phase 1 changes models before the baseline exists, and the plan says it has no open questions - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Lines 156, 214, 223-227, 289, 294 (section 7, Phase 1, Phase 2 "Evaluation first", rule 6, section 14)
* **Discrepancy Description**: Phase 1 switches the LLM from `qwen2.5-coder:7b` to `qwen3:8b`, switches the embedder from in-process `all-MiniLM-L6-v2` to `nomic-embed-text` through Ollama, and moves storage from FAISS to pgvector. The baseline is measured only at the start of Phase 2. By then the system differs from v1 in model, embedder and storage, so the baseline does not describe v1, and the v1-to-v2 change has no metric delta (rule 6). Section 14 says there are no plan-level open questions, but `eval_notes.md` questions 6 (what the baseline is) and 7 (re-embedding and changing vector dimension) decide what Phase 1 builds.
* **Rationale & Recommendation**: Either keep Phase 1 behavior-preserving (v1 models and embedder on the new storage, new models only after the Phase 2 benchmark), or state that the baseline is the Phase 1 system with provisional models. Move eval_notes questions 6 and 7 into section 14 until they are settled. See also finding 15 (the storage schema for embeddings).

### 2. Shared extractions conflict with review-dependent fields and have no versioning key - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`, `egm-inventive-catalyst`
* **Affected Scope:** Lines 115, 125, 135, 160 (section 6 scope rule, `extractions` row, "Future" rule; section 7.1 prompt order)
* **Discrepancy Description**: `extractions` has no `review_id` and is shared across users. In v1, `extract_from_retrieved_chunks(paper, research_question)` puts the review question into the prompt, and the schema includes `relevance_to_research_question`, which only makes sense for one review. The prompt order in 7.1 ends with "question", which suggests the review question is still included. The plan treats review-specific extraction as a future feature, but current behavior already depends on the review. No key is defined for repeat runs either: re-extracting with a new model or prompt version would either overwrite rows or create duplicates.
* **Rationale & Recommendation**: Split the fields. Fields that do not depend on the review (method, dataset, findings, limitations) stay shared. Review-dependent fields such as relevance go into a per-review table or the screening record. Remove the review question from shared extraction prompts. Make shared extractions append-only, keyed by (`paper_id`, `field`, `model`, `prompt_version`), and add a "current" view. Decide this before the Phase 1 Alembic models, because it sets how much reuse the persistent library can actually deliver. Cost: one extra join for the evidence table and a rule for choosing the current version.

### 3. "Library" is not defined, and a conversation can hold only one review - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Lines 29, 79, 115, 121, 161-162 (section 3 "Persistent library", 5.2 rule 2, section 6, 7.1)
* **Discrepancy Description**: Section 7.1 says library QA answers from "the evidence table" (one review) and also from "the library as a whole" (retrieval). The shared `papers` and `chunks` tables include papers that this user's screenings excluded and papers other users added. The plan does not say whether library QA searches all papers, the user's included papers, or one review's evidence table. Separately, `conversations` has a single `review_id`, but the `new_topic` route starts a new pipeline run (a new review) inside an existing conversation.
* **Rationale & Recommendation**: Add one sentence defining library scope for QA (Zoom Out suggests: papers included in the user's reviews). Make conversation-to-review one-to-many, or state that `new_topic` opens a new conversation. Both decisions belong in this plan rather than a later design doc. See also finding 21.

### 4. Full-paper context is stated as decided, breaks chunk-level evidence links, and its caching benefit is unproven - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`, `egm-inventive-catalyst`
* **Affected Scope:** Lines 158-164 (section 7.1), versus line 235 (Phase 2 experiment) and line 280 (risk table)
* **Discrepancy Description**: Section 7.1 says "full paper if it fits" as a rule. Phase 2 lists it as an experiment, and the risk table says "measure before adopting". With the full paper in context, no retrieval step produces a chunk, so `evidence_chunk_id` and the requirement that every cell links to its source passage and page (line 32) need another mechanism. The plan does not name one. The prompt-caching argument is not backed by measurement. Local Ollama reuses only the KV cache of the most recent prompt per slot, and alternating screening and extraction calls, plus model swaps on 16 GB RAM, will often evict it. The rule "never mix data from different users in one cached context" guards against a multi-user setup that does not exist until Phase 4.
* **Rationale & Recommendation**: Reduce 7.1 to the ordering rule (stable content first, variable content last), which costs nothing. Label full-paper context as a Phase 2 hypothesis. If the experiment adopts it, require it to state how evidence is linked, for example a returned quote matched to a chunk. Add cache-hit or latency evidence to that experiment. Drop the cross-user caching rule until Phase 4. See also finding 12 (Loop 2 in full-paper mode).

### 5. The `get_llm(role)` return type is undecided and the plan ignores the existing instructor and tracing setup - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Line 67 (section 5.1), lines 151-155 (section 7)
* **Discrepancy Description**: v1 builds clients in three places (`search_agent/agent.py:35`, `Screening_Agent/screening_agent.py:51`, `extract_agent/rag_extraction_main.py:27`). All three use `instructor` on an OpenAI-SDK client wrapped by `tracing.maybe_wrap_openai`. The plan's example, LangChain `with_fallbacks`, would bring in LangChain chat models, replace instructor with `with_structured_output`, and change how tracing is wired. The plan does not say what `get_llm` returns. It also routes the `embedding` role through the same factory, although an embedder is a different kind of client. Every agent and the test fake LLM depend on this choice.
* **Rationale & Recommendation**: State the return type in the plan. The smallest change is to centralize the existing pattern (OpenAI-compatible client, `maybe_wrap_openai`, instructor) and add retry-then-fallback with `tenacity`, which v1 already depends on. Add a separate `get_embedder()`. Adopt LangChain only when a concrete need appears.

### 6. "A restart loses nothing" has no matching API work, and a checkpointer alone does not resume runs - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`, `egm-inventive-catalyst`
* **Affected Scope:** Lines 62, 197, 212-220 (`POST /chat`, section 9 "Job queue", Phase 1 checklist and exit)
* **Discrepancy Description**: v1 keeps job state in the in-memory `JOBS` dict (`Backend/main.py:24`) and runs the graph as a FastAPI background task. Phase 1 adds `PostgresSaver` but lists no API change. A checkpointer saves state at node boundaries. A run interrupted by a restart continues only if something calls the graph again with its `thread_id`, and nothing in the plan does that. In v2 the run also lives inside the SSE response of `POST /chat`, so a client disconnect can cancel it. Section 9's argument that the queue can wait "because the checkpointer persists state" depends on the same gap. Phase 1 also moves everything to `src/` without saying how the v1 API and UI keep working (rule 1, line 284).
* **Rationale & Recommendation**: Define "loses nothing". Keeping completed results after a restart is cheap. Resuming in-flight runs needs a resume step at startup. Add the needed API change to the Phase 1 checklist (for example, replace `JOBS` with a status lookup in Postgres or the checkpoint) and list which entry points must keep working after the layout move. Inventive Catalyst proposes one design: a `runs` table claimed with `SELECT ... FOR UPDATE SKIP LOCKED`, a startup loop that resumes threads with pending next nodes, and an SSE handler that follows progress (LISTEN/NOTIFY or polling) rather than owning the run. Costs: every node must be safe to run twice, and the resume loop needs an attempt counter and a dead-letter state.

### 7. Graph state may carry full payloads into every checkpoint - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Line 93 (section 5.3 "State"), line 133 (section 6 checkpoint rule), lines 161-163 (section 7.1)
* **Discrepancy Description**: In v1, full paper dicts, screening buckets and extraction records travel through graph state (`Orchestration/state.py`). The plan does not say what v2 state may hold. `PostgresSaver` writes state at every step. If paper lists, chunks or full paper text (needed in full-paper mode) sit in state, the checkpoint tables grow with every step and duplicate data already stored in `papers`, `chunks` and `extractions`.
* **Rationale & Recommendation**: Add a rule to 5.3: state holds only IDs, counters and per-field statuses, and nodes load content from the library tables. Costs: extra database reads, and a resumed run reads current table rows rather than a snapshot. See finding 18 for whether `seen_ids` belongs in state at all.

### 8. The Redis queue and worker are not justified by any stated need - Severity: Major
* **Reviewer Lens:** `egm-zoom-out` (Inventive Catalyst reaches the same conclusion through finding 6)
* **Affected Scope:** Lines 193, 197, 254 (section 9 Kubernetes and job queue, Phase 4 checklist)
* **Discrepancy Description**: The non-goals (line 41) exclude scaling for many concurrent users, and line 197 says async execution in the API is acceptable. Redis plus a worker adds two cluster components on a 16 GB fanless laptop that also runs Ollama, Postgres, the API and the UI, with no measured bottleneck behind it. Redis would also be a second state store next to Postgres.
* **Rationale & Recommendation**: Remove Redis and the worker from Phase 4 unless a measured problem appears. A single API deployment that can resume runs (finding 6) is enough. If a queue is needed, Postgres can serve as one.

### 9. Running evals in CI conflicts with local-only inference - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`, `egm-inventive-catalyst`
* **Affected Scope:** Line 187 (section 8 Process), line 199 (section 9 CI/CD), line 256 (Phase 4)
* **Discrepancy Description**: "CI runs a small subset on every merge" requires the system models. They run on local Ollama on a MacBook, which a hosted CI runner cannot reach. Substituting a free API model would evaluate a different model. The judge would need secrets and free-tier quota on every merge, and Groq rate limits make that unreliable.
* **Rationale & Recommendation**: Keep CI to lint and unit tests with the fake LLM. Run live evals locally at each phase exit and commit the results file, as `eval_notes.md` already suggests. Optionally, as Inventive Catalyst proposes, record model responses keyed by a hash of (model, prompt version, input) and replay them in CI to test the harness and scoring. Cost: recordings go stale when prompts change, and CI no longer measures real model quality.

### 10. The summary model also judges summaries - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`, `egm-inventive-catalyst`
* **Affected Scope:** Lines 147-148 (section 7 YAML), lines 174 and 181 (section 8)
* **Discrepancy Description**: The `summary` and `judge` roles both use Groq `llama-3.3-70b`. Section 8 requires the judge to be stronger than the system model and scores summary faithfulness with it. For summaries the judge grades its own output: it is not stronger, and models tend to rate their own output favorably. When the summary falls back to Ollama, eval results also mix two different generators.
* **Rationale & Recommendation**: Use a different model family for either the judge or the summary. If the free budget does not allow that, state the limitation in section 8 and label summary faithfulness as same-model judged. Split eval results by the recorded `model`.

### 11. The plan drops the one bottleneck v1 measured and sets no latency target - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Section 3 (lines 23-37), Phase 2 checklist (lines 222-238), section 12 (lines 272-280)
* **Discrepancy Description**: v1 traces show extraction takes 51% of runtime even on a GPU cluster, and the v1 roadmap lists parallel extraction as the largest available speedup (about a third off total runtime). The plan does not mention it. It adds Loop 2 (more extraction calls), Loop 1 (more screening), possibly full-paper context, and moves inference to a fanless MacBook Air. For a chat product, nothing says how long a `new_topic` run may take.
* **Rationale & Recommendation**: Add an end-to-end latency target for one pipeline run on the target hardware to the Phase 2 exit. Treat extraction concurrency as a Phase 2 candidate that must show a metric delta. Add "local cluster plus native Ollama exceeds 16 GB" to the risk table.

### 12. Loop 1 counts the wrong set of papers - Severity: Major
* **Reviewer Lens:** `egm-zoom-out` (proposed Nit), `egm-inventive-catalyst` (proposed Major)
* **Affected Scope:** Lines 84-86 (section 5.3 Loop 1), line 36 (section 3 "Human-in-the-loop")
* **Discrepancy Description**: The loop condition is "included papers < target". It misses two groups. First, v1 screening also produces `uncertain` (and `failed`) results (`Backend/main.py:119-122`). The plan does not say whether uncertain papers count, trigger an `interrupt()`, or are dropped, and the human-in-the-loop examples no longer include reviewing uncertain papers, the use case in the v1 roadmap. Second, v1 flags included papers whose PDFs cannot be downloaded. Those papers count toward the target but produce no extraction, so the loop can stop with fewer usable papers than the target.
* **Rationale & Recommendation**: Define the count as included papers with a retrievable PDF, and state how `uncertain` papers are handled. Inventive Catalyst suggests resolving PDFs before or alongside the Loop 1 check, so that PDF failures trigger a top-up search within the same two-iteration limit. Cost: PDFs are downloaded earlier, including for papers later dropped, and the loop condition depends on network results. Raised to Major because together the two gaps mean the loop's stated guarantee (line 86, "report the actual count honestly") does not hold.

### 17. The plan carries schema-level detail that belongs in design docs - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Lines 117-135 (section 6), parts of 5.1, 5.3 and 7
* **Discrepancy Description**: Primary keys, `ON CONFLICT`, HNSW indexing, `st.chat_message` and `with_fallbacks` are implementation detail. Line 3 requires design docs to stay consistent with this plan, so each such detail here is one more thing that can drift.
* **Rationale & Recommendation**: Keep entities, scope (shared or private) and rules in the plan. Move column lists and tool choices to `docs/designs/`.

### 18. `seen_ids` duplicates data the database already holds - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Lines 85, 93 (section 5.3)
* **Discrepancy Description**: Papers already screened for a review are recorded in `screenings` (`review_id`, `paper_id`). A separate `seen_ids` in graph state is a second copy of the same fact.
* **Rationale & Recommendation**: Derive it from `screenings` for the current review. Note: Inventive Catalyst's finding 7 lists `seen_ids` as allowed in state. Deriving it from the database is consistent with that finding's goal of keeping state small.

### 19. The `context` route may not need to be separate - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Line 28 (section 3), line 76 (section 5.2)
* **Discrepancy Description**: Library QA with conversation history can answer most follow-ups that "answer from the conversation" would handle. Each extra route adds labeling work and confusion-matrix cells to the 30-50 message router test set.
* **Rationale & Recommendation**: Consider three routes (`library`, `new_topic`, `clarify`) and add `context` only if router evaluation shows a need.

### 20. The `cloud` profile is undefined - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Line 153 (section 7)
* **Discrepancy Description**: The budget is free tiers only, and providers are already set per role. The plan does not say what `cloud` changes compared with `local`.
* **Rationale & Recommendation**: Define it in one line or drop it until needed.

---

## Inventive Catalyst findings

Findings 2, 4, 6, 9, 10 and 12 above also carry this lens. The findings below were raised only by Inventive Catalyst.

### 13. Loop 2 turns retrieval failure into `not_reported` on shared rows - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Lines 88-91 (section 5.3 Loop 2), line 125 (`extractions`)
* **Discrepancy Description**: After two attempts an `empty` field becomes `not_reported`. That treats "the paper does not report this" and "retrieval or the model failed to find it" as the same thing. Because `extractions` is shared, one weak run tells every later review that the paper lacks the field. It also removes the signal `eval_notes.md` wants, which is separating retrieval misses from LLM misses.
* **Rationale & Recommendation**: Add a separate final status such as `unresolved`, stored with `model` and `prompt_version`. Use those rows as the queue for re-extraction when the model or prompt changes. Only real evidence of absence should produce `not_reported`. Cost: a fourth status for the UI and export to handle, and a re-extraction trigger to maintain.

### 14. Loop 2's action is undefined in full-paper mode - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Line 90 (Loop 2 action) versus lines 161-163 (section 7.1) and line 235 (Phase 2 experiment)
* **Discrepancy Description**: Loop 2's action is "targeted re-retrieval: different phrasing, more chunks, specific sections." In full-paper mode there is no retrieval step to vary, so the loop would ask the same model about the same context again, adding latency for little gain. Per-field re-calls are accepted without saying when they apply, while extraction is already the largest share of runtime (finding 11).
* **Rationale & Recommendation**: Define Loop 2 per mode. In chunk mode, re-retrieve. In full-paper mode, skip the loop or ask once for all empty fields of that paper with a section-focused prompt. In both modes, batch a paper's empty fields into one call. Cost: two code paths to test, and batching can lower per-field accuracy.

### 15. One embedding per chunk row blocks the Phase 2 embedding benchmark - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Line 124 (`chunks`), line 156 (section 7 last bullet), line 226 (Phase 2 benchmark)
* **Discrepancy Description**: The plan accepts that changing the embedding model means re-embedding and migrating the vector column. The Phase 2 benchmark needs several embedding models side by side on the same chunks. A single `embedding` column per chunk row makes that impossible without copying tables. The schema is fixed in Phase 1 for a decision made in Phase 2.
* **Rationale & Recommendation**: Use a separate `chunk_embeddings` table (`chunk_id`, `embedding_model`, `embedding`) with a vector column of unspecified dimension until an index is needed. Indexes can then be added per model as partial or expression indexes. Switching models means adding rows and changing a setting, not running a migration. Costs: an extra join on retrieval, a cast to a fixed dimension for each model's index, and more storage while several models coexist. Related to finding 1.

### 16. Paper identity has two unique keys but the upsert uses only one - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Line 123 (`papers`), line 129 (upsert rule), line 220 (Phase 1 exit)
* **Discrepancy Description**: `openalex_id` and `doi` are both unique, and the upsert targets only `openalex_id`. OpenAlex can hold duplicate work records for one paper, and `eval_notes.md` already found a duplicate title in topic 2. Two OpenAlex IDs with the same DOI would raise a unique violation on `doi`, and ingestion would fail instead of deduplicating. The "no duplicates" exit test covers only an identical repeat run.
* **Rationale & Recommendation**: Add an identity-resolution step before the upsert: look up by DOI first, then by `openalex_id`, and keep a mapping table from external IDs to the canonical paper. Extend the Phase 1 exit test to cover two IDs with the same DOI. Cost: an extra lookup per paper and merge logic for records already stored.

### 21. The pipeline does not check the library before searching OpenAlex - Severity: Nit
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Line 53 (section 5 diagram), lines 84-85 (Loop 1)
* **Discrepancy Description**: The `new_topic` path always starts with OpenAlex. Papers already in the shared library, already chunked, are reused only when the upsert happens to match them. The library grows storage but does not reduce search or screening work.
* **Rationale & Recommendation**: Before the OpenAlex search, retrieve candidates from the library and screen them for the new review. Cost: more screening calls on library papers that may not fit, and a ranking rule for merging library and OpenAlex candidates. Depends on the library scope decision in finding 3.

### 22. The router's score threshold depends on the embedding model - Severity: Nit
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Line 79 (section 5.2 rule 2)
* **Discrepancy Description**: The threshold on "top score" is a single fixed value. Similarity scores are not comparable across embedding models, and the model may change in Phase 2.
* **Rationale & Recommendation**: Store the threshold per `embedding_model` in settings and calibrate it on the Phase 3 router test set. Cost: one more value to recalibrate whenever the embedding model changes.
