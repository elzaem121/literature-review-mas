# Consolidated Review Report — `docs/plan_v2.md`

**Target:** `docs/plan_v2.md` (294 lines, unchanged during the review)
**Mode:** Consolidated report, all five stages run without stopping
**Split:** FeatureRange lines 1-200 (sections 1-9). DetailedRange lines 201-294 (section 10 "Phases" through section 14). The plan has no "Implementation Plan" heading, so section 10 was used as the work breakdown.
**Context files given to reviewers** (Stage 6 excepted): `README.md`, `docs/backlog.md`, `docs/eval_notes.md`, `Orchestration/graph.py`, `Orchestration/state.py`

## Stage reports

| Stage | Reviewers | Status | Raw result | Report |
| --- | --- | --- | --- | --- |
| 5 Initial Zoom Out | zoom-out, inventive-catalyst | completed | 0 B / 16 M / 6 N | `zoom_out_report.md` |
| 6 Comprehension | comprehension | completed | 0 B / 8 M / 6 N | `comprehension_report.md` |
| 7 Critic | design, structural, style | completed | 2 B / 26 M / 24 N | `critic_report.md` |
| 8 Intermediate Zoom Out | zoom-out | completed | 0 B / 12 M / 2 N | `intermediate_zoom_out_report.md` |
| 9 Implementation Readiness | implementation-readiness, codebase-details, style | completed (first run cut off when the machine slept; the retry finished) | 2 B / 24 M / 16 N | `implementation_readiness_report.md` |

The stages produced 144 findings in total. This report merges them into **42 actions: 3 Blockers, 33 Major, 6 Nit.**

## Overall verdict

The plan is the right kind of document: a short reference plan with phases, exit criteria and working rules. The reviewers did not find a wrong direction. They found three kinds of problems:

1. **Phase 1 cannot start cleanly.** The plan does not say what happens to the running v1 code. The Phase 1 exit ("a restart loses nothing") cannot be checked, and the listed tasks cannot reach it. Several decisions that set the first database migration are open, while section 14 says nothing is open.
2. **The core data rule for extraction is broken.** After two retries Loop 2 turns every `empty` field into `not_reported`. As a result the Phase 2 exit ("fewer empty fields") passes automatically, and one weak run tells every later review that a paper lacks the field. This was found independently in Stages 5, 6, 7 and 9.
3. **Scope is larger than the stated situation needs.** One user on a 16 GB laptop with no deadline. Multi-user auth, Redis, evals in CI, a research summary on a second provider, and a router-level `interrupt()` each add design work and drive many of the other findings.

**A warning on how to apply this report.** Stage 8 checked what happens if all the earlier findings are written into the plan. The plan would turn into the design spec for Phases 1-3, and line 3 requires every design doc to stay consistent with it, so each added detail is one more thing that can drift. This report follows Stage 8: each action says where the fix belongs. **Plan** means one sentence or one invariant in `plan_v2.md`. **Phase N design** means a doc under `docs/designs/`. **Backlog** means `docs/backlog.md`. **Drop** means no change. About a third of the actions need plan text, and most of those are one or two sentences.

## Decisions only the plan owner can make

These eight decisions block or reshape other actions. They should be settled first, since several actions below assume an answer.

| # | Decision | Options | Reviewer lean | Unblocks |
| --- | --- | --- | --- | --- |
| D1 | What "a restart loses nothing" means, and when the checkpointer arrives | (a) Phase 1 keeps the checkpointer; completed results and checkpoints survive; interrupted runs are marked failed. (b) Move the checkpointer to Phase 3, where chat memory first needs it; the Phase 1 exit becomes "no completed results lost". (c) Runs resume automatically (queue, resume loop, dead-letter state). | (a) or (b). (c) was judged too much machinery for one user. | A3, A12 |
| D2 | What the Phase 2 baseline is | (a) The Phase 1 system with provisional models; the v1-to-Phase-1 model swap is not measured. (b) Keep v1 runnable at `v0.1` and build a v1 eval adapter. (c) Phase 1 keeps the v1 models and embedder; new models come only after the benchmark. | No consensus. (a) is cheapest; (c) is the only option that gives a real v1 delta. | A4 |
| D3 | Multi-user and auth before v1.0 | Keep in Phase 4, or move to the backlog and stay single-user (keeping the `user_id` column) | Backlog, unless a multi-user demo is a hard portfolio goal | A22, A31 |
| D4 | Research summary | Keep it as a Should in Phase 3, or move it to the backlog | Backlog: it is the only reason Groq is called at runtime and the reason the judge grades its own output | A16 |
| D5 | Loop 2 priority | Keep it a Must, or make it conditional on the measured empty-field share and the full-paper experiment | Conditional, the same rule line 236 already applies to reranking | A20 |
| D6 | Router "search for new papers?" | `interrupt()` plus `/chat/resume`, or an ordinary chat reply whose answer is routed as the next message | Ordinary reply. That also removes the dependency of a Must (router) on a Should (HITL). | A21 |
| D7 | Phase size | Keep Phases 2 and 3 as they are, or split each one (2a eval and benchmark, 2b pipeline; 3 Musts only) | Split | A29 |
| D8 | Excel export | Add `xlsx` to the API and Phase 3, or drop it from section 3 | Drop | A28 |

## Prioritized actions

### 🔴 Blockers

#### A1. Separate "not found after retries" from "not reported in the paper"
- **Problem:** Line 91 sets every field still `empty` after two Loop 2 tries to `not_reported`. After a run no field is `empty`, so the "share of empty fields" metric (line 173) is zero by construction and the Phase 2 exit (line 238) passes automatically. `extractions` are shared (line 125), so a retrieval failure is stored as a fact about the paper for every later review and user. The three statuses are never defined.
- **Action:**
  - **Plan:** add an invariant to section 6: "a field not found after retries is stored as a separate status, never as `not_reported`". Rewrite the Phase 2 exit as checks against gold data, for example "fewer gold-`found` fields reported as missing than the recorded baseline".
  - **Phase 2 extraction design:** define what produces each status. Map v1 sentinel strings ("not specified") to statuses.
  - **Backlog:** a re-extraction queue built from unresolved rows.
- **Sources:** Critic B-2, Z5-13, C-2, IR M14, Z8-1.

#### A2. State the Phase 1 end state and what happens to v1 code
- **Problem:** "New repository layout" (line 213) is one checkbox. v1 packages import each other as root-level packages (`Orchestration/nodes.py`, `Backend/main.py`, `tracing`, the `sys.path` workarounds), and the Dockerfiles assume that layout. The plan does not say:
  - whether the v1 pipeline is ported into `src/pipeline/` in Phase 1;
  - which entry point works at the end of Phase 1;
  - which graph the checkpointer attaches to;
  - what happens to modules with no place in the new layout (`App_Main/`, `search_agent/archiv/`, the legacy extract CLI scripts, `screening_main.py`, `export_graph.py`).

  Rule 1, "the system runs after every step", has no definition of "runs".
- **Action:**
  - **Plan:** add a "Phase 1 end state" paragraph that names the working entry point at the end of the phase and states "the v1 linear pipeline is ported into `src/pipeline/` with unchanged behaviour, using `get_llm(role)` and Postgres". Add the rule "v1 modules not used by the graph are deleted, not moved". Define "runs" as a smoke check: the graph compiles, a fake-LLM end-to-end run succeeds, and `docker compose up` serves the API.
  - **Phase 1 design:** a table marking each v1 module Move (with its target path), Delete or Keep, and whether the move is one commit or one package at a time. Close backlog items 2 and 3 by deleting the code.
- **Sources:** IR B1, IR M5, Z8-14, Z5-6 (layout-move part).

#### A3. Make the Phase 1 restart exit checkable and reachable
- **Problem:** "A restart loses nothing" (line 220) uses four undefined terms. Adding `PostgresSaver` (line 217) cannot satisfy it:
  - job state lives in the in-memory `JOBS` dict (`Backend/main.py:24`);
  - runs are FastAPI `BackgroundTasks`, which die with the process;
  - `astream` is called without a `thread_id`;
  - an unknown job returns 404, which `ui_app.py` polls forever;
  - the graph is compiled at import time with no checkpointer (`Orchestration/graph.py:49`).

  The live nodes are async, so the sync `PostgresSaver` is the wrong class (`AsyncPostgresSaver`, opened in the FastAPI lifespan, is the matching one). Line 197 also overstates what a checkpointer provides: it saves state at node boundaries but does not restart an interrupted run. In v2 the run lives inside the `POST /chat` SSE response, so a client disconnect can cancel it.
- **Action (after D1):**
  - **Plan:** add one decision sentence: "A pipeline run is decoupled from the HTTP request. Its status is stored in Postgres. On restart, unfinished runs are marked interrupted and the user can re-run them." Rewrite line 197 to match. Narrow the Phase 1 exit, for example: "Running the pipeline twice with the same question and criteria leaves one `papers` row and one set of `chunks` per paper. After restarting the API and Postgres, all library rows (and checkpoints, if D1 = a) are present. Both checks are automated tests."
  - **Phase 1 design:** a `build_graph(checkpointer=None)` factory; who calls `setup()` relative to Alembic; the `job_id` to `thread_id` mapping; making `ui_app.py` stop polling on a non-200 response.
  - **Phase 3 design:** status and reconnect endpoint shapes.
  - **Drop:** automatic resume, `SKIP LOCKED`, LISTEN/NOTIFY and dead-letter handling.
- **Sources:** IR B2, IR M7, Z5-6, Critic M-4, Z8-2, Z8-9.

### 🟡 Major

#### Phase 1 foundations and decisions that set the first migration

**A4. Define the Phase 2 baseline (D2).** Phase 1 changes three things before anything is measured: the model (`qwen2.5-coder:7b` to `qwen3:8b`), the embedder (MiniLM to `nomic-embed-text`) and the store (FAISS to pgvector). The Phase 2 "baseline" (line 225) is therefore not v1, and rule 6's metric delta can never be shown for the swap. Phase 0 is titled "Baseline" but measures nothing. The plan does not say what the gold dataset labels, although the Phase 2 exit depends on it. **Plan:** one sentence that records D2. Rename Phase 0 to "v1 documentation". Say in one line what the gold dataset contains. *Sources: Z5-1, IR M1, C-8.*

**A5. Correct section 14.** It says "None at plan level", but D1-D8, the baseline, the embedding migration, the Phase 1 table scope and the CI eval environment are all open. A session that reads section 14 will treat the plan as complete. **Plan:** list the open questions until each is resolved; keep the pointer to `eval_notes.md` for questions at design level. *Sources: IR M2, Z5-1.*

**A6. Set a latency budget for the target hardware.** The v1 README says local Ollama was too slow, so inference moved to a GPU cluster. The ~5 min figure (line 16) is from a 5-paper run on that cluster. v2 moves inference to a fanless 16 GB MacBook Air and adds two loops, a target of 10 papers, possibly full-paper context, and a router call on every message, all with no time budget. Extraction already takes 51% of runtime, and parallel extraction, the speedup v1 measured, is not mentioned. A local cluster plus native Ollama may not fit in 16 GB. **Plan:**
- correct line 16 ("5 papers, GPU cluster, not measured locally");
- state whether the cluster is still an option;
- add a per-run latency budget to section 11 and the Phase 2 exit;
- add a memory-pressure risk row.

**Phase 2 design:** call estimates, fallback order, extraction concurrency as a candidate change. *Sources: Critic M-2, Z5-11, IR N11.*

**A7. Shared extractions: split by review dependence and make them append-only.** `extractions` has no `review_id`, but v1 puts the review question into the extraction prompt and has a `relevance_to_research_question` field. No rule says which row is current after re-extraction with a new model or prompt version. **Plan:** two invariants in section 6:
1. "Shared extractions hold only fields that do not depend on the review; judgments tied to one review are stored per review."
2. "LLM outputs are append-only with `model` and `prompt_version`; a re-run adds rows and never overwrites."

**Phase 1 data design:** keys and the "current" rule. *Sources: Z5-2, Critic M-6, Z8-1.*

**A8. Fix the extraction field set.** The document never names the fields that make up the evidence table's columns, although custom fields are a non-goal. The v1 schema (`paper_type`, `method`, `dataset`, `task`, ...) is shaped for ML papers, which conflicts with "domain-agnostic" (line 10). In v1, `FIELD_QUERIES` covers only 5 of 8 fields, and extraction is one call per paper with no chunk IDs. **Plan:** one sentence: "a fixed, domain-generic field set, defined in the Phase 2 extraction design". **Phase 2 design:** the list of fields, which fields need evidence, how the model cites a chunk, and per-paper or per-field calls. *Sources: C-1, Critic M-7, Critic M-8, IR M17.*

**A9. Define library scope, the review lifecycle and how criteria are collected.** The plan leaves these open:
- "Library QA" answers from "the evidence table" (one review, line 161) and from "the library as a whole" (retrieval, line 162).
- Shared `chunks` include papers other users added and papers this user excluded.
- `conversations` has one `review_id`, but `new_topic` starts a new review inside a conversation.
- The pipeline needs `min_year`, inclusion and exclusion criteria and a target, but nothing says how a chat message becomes a `reviews` row with criteria.

**Plan:** two sentences:
1. Library QA retrieves over papers included in the user's own reviews.
2. Either a conversation holds many reviews, or `new_topic` opens a new conversation.

Add one sentence on how criteria are collected. **Phase 3 design:** the flow. *Sources: Z5-3, C-4, Critic M-10, Critic M-11.*

**A10. One canonical stage list, with ingestion defined.** The stages are listed three ways (lines 17, 53, 101). None of the lists has the download, parse, chunk and embed step that line 129 requires and v1 has (`document_processing_node`). The v1 code does not fit the planned ingestion:
- the OpenAlex ID is stored in `url`;
- `ResearchPaper` has no `openalex_id`;
- `pdf_url` is dropped and looked up again by DOI;
- pages are joined without markers;
- chunks have no overlap, so Phase 2's "evidence (chunk, page)" has no page to cite.

Adding overlap in Phase 2 means re-chunking the shared library, which contradicts "chunk each paper once". Phase 1 also lists no dependency changes (add sqlalchemy, alembic, pgvector, psycopg, pydantic-settings, a linter; remove sentence-transformers, faiss-cpu, libgomp). pgvector retrieval must filter by `paper_id`, which FAISS-per-paper gave for free. **Plan:** one stage list including an ingestion stage, used in the diagram and section 5.4. **Phase 1 design:**
- carry `openalex_id` and `pdf_url` through the paper contract;
- chunk page by page with ordinals;
- store PDFs keyed by paper id;
- decide chunk overlap now, or declare the Phase 2 re-chunk a one-time migration;
- list the dependency changes and the `paper_id` filter.

*Sources: C-5, Critic M-21, IR M8, IR M10.*

**A11. Paper identity across OpenAlex IDs and DOIs.** Both `openalex_id` and `doi` are unique, but the upsert targets only `openalex_id`. Two OpenAlex records with one DOI make ingestion fail instead of deduplicating, and `eval_notes.md` already found such a duplicate. `papers` has no ingestion status (pending, downloaded, chunked, PDF unavailable, failed), so "download and chunk once" cannot be retried idempotently. **Plan:** the invariant "a paper is stored once, whatever its OpenAlex ID or DOI variants". **Phase 1 design:** the upsert key (DOI first, OpenAlex ID otherwise), the ingestion status column, and an exit test with two IDs that share a DOI. *Sources: Z5-16, Critic M-12, Z8-1.*

**A12. Graph state holds IDs, not payloads.** v1 carries full paper dicts and up to 25 chunks of 1200 characters per paper through graph state, twice. `PostgresSaver` writes state at every step, and each `pre_*` node adds a write. Checkpoint tables would grow without limit in the same database as the library. **Plan:** one constraint in 5.3: "graph state holds IDs, counters and per-field statuses; nodes load content from the library tables". Remove the `seen_ids` line, since it can be read from `screenings`. **Phase 3 design:** checkpoint retention, and whether to replace `pre_*` nodes with streamed events. *Sources: Z5-7, Critic M-13, IR N14, Z5-18.*

**A13. Treat full-paper context as a hypothesis and narrow the evidence promise.** Section 7.1 states "full paper if it fits" as a rule, but Phase 2 lists it as an experiment and the risk table says "measure before adopting". In full-paper mode no chunk is retrieved, so `evidence_chunk_id` and "every cell links to its source passage and page" (line 32) have no mechanism. Ollama silently truncates prompts longer than `num_ctx`. The prompt-caching claim is not measured, and Loop 2's "re-retrieval" has no meaning in full-paper mode. **Plan:**
- reduce 7.1 to the ordering rule (stable content first) and mark full-paper context as a Phase 2 experiment;
- narrow line 32 to "every cell with status `found` links to its evidence chunk and page";
- drop the cross-user caching line and the unexpanded "CAG".

**Phase 2 design:** a token-count fit check against `num_ctx`, a quote-to-chunk matching rule, and Loop 2 behaviour per mode. *Sources: Z5-4, Critic M-5, Critic M-9, C-11, Z5-14, C-10.*

**A14. Decide what `get_llm(role)` returns.** v1 builds clients in four places, all `instructor` on an OpenAI-SDK client wrapped by `tracing.maybe_wrap_openai`. `nodes.py:62` hardcodes the model. The plan's example (LangChain `with_fallbacks`) would replace instructor with `with_structured_output` in every agent, and `langchain-openai` is not installed. The `embedding` role is not a chat client. Search query expansion has no role and is not benchmarked. **Plan:** one sentence: `get_llm` returns an instructor-patched OpenAI-compatible client; embeddings come from a separate `get_embedder()`; fallback uses `tenacity`, which v1 already depends on. Add a `search` role. **Phase 1 design:** the list of call sites to change, and whether `tracing.py` stays. *Sources: Z5-5, Critic N-7, IR M9.*

**A15. Plan the embedding-model change after the benchmark.** Line 156 accepts that a new embedder means re-embedding and migrating the vector column, but Phase 2 has no task for it. Router score thresholds are also tied to the embedding model. **Plan:** a conditional Phase 2 task: "If the embedding model changes: migrate the vector column, re-embed stored chunks, check one `embedding_model` across `chunks`, recalibrate the router threshold." **Contested:** Z5-15 proposed a separate `chunk_embeddings` table so that models can be compared side by side. Stage 8 recommended dropping that, because the benchmark runs on frozen snapshots outside the production database and re-embedding a small library is cheap. This report follows Stage 8. *Sources: IR M11, Z5-15, Critic N-5, Z5-22.*

#### Evaluation and CI

**A16. The summary model is also its judge (D4).** `summary` and `judge` are both Groq `llama-3.3-70b`, yet line 181 requires the judge to be stronger than the system model. Summary, evals and CI draw on one free-tier quota. A 10-paper summary may exceed token caps and fall back silently to the local model. `fallback: ollama` names no model. **Plan:** "the judge is never the model that generated the output". If D4 keeps the summary, use a different judge or label summary faithfulness as same-model judged. **Phase 3 design:** token estimates, the named fallback model, and recording when a summary fell back. *Sources: Z5-10, Critic M-3, C-6, Z8-7.*

**A17. Remove live evals from hosted CI.** Hosted runners cannot reach local Ollama. A fake-LLM eval measures nothing. The judge needs a Groq secret and quota on every merge. CI cannot deploy to a `kind`/`k3d` cluster on a laptop. Line 256's step order also differs from line 199. **Plan:** "CI runs lint and unit tests with the fake LLM. Live evals run locally at each phase exit and the results file is committed. CI builds images; deployment is a local script." **Backlog:** replaying recorded responses in CI. *Sources: Z5-9, Critic M-16, IR M22, C-13.*

**A18. Shrink section 8 to principles and settle `eval_notes.md` first.** Line 4 says "approved direction", but `eval_notes.md` is a draft with seven open questions and disagrees with section 8:
- **Screening metric:** the notes use deterministic scoring against gold labels; section 8 uses judge agreement.
- **Results store:** the notes make the local results file the source of truth; section 8 uses LangSmith.
- **Missing metrics:** recall@k, evidence-page accuracy and per-loop yield.

Calibration has no pass threshold, and "must show a metric delta" accepts noise (±8-10 points at n = 60). Phase 2 starts building the gold set before those questions are settled. **Plan:** reduce section 8 to about six principles:
- the judge sees the source;
- the judge is calibrated before it is trusted;
- the judge is not the generator;
- datasets are fixed and versioned;
- the local results file is the record;
- live evals run at phase exits.

Mark it provisional. Rule 6 says "a delta beyond run-to-run noise". Make the first Phase 2 task "resolve the `eval_notes.md` open questions and write `docs/designs/eval.md`, including the model-selection rule". **Phase 2 eval design:** metrics, thresholds, kappa and decision rules. *Sources: Critic M-17, Z8-3, IR M13, Critic M-25, Critic M-26.*

#### Pipeline and chat behaviour

**A19. Loop 1 should count usable papers.** "Included papers < target" counts papers whose PDF cannot be downloaded, which produce no extraction. It also ignores `uncertain` and `failed` results, so the guarantee on line 86 does not hold. v1's `target_output_count` (default 25 in the API, 10 in the UI) means search fetch size; reusing it for Loop 1 would silently change its meaning. **Plan:** "Loop 1 counts included papers with a retrievable PDF, against a separate `target_included`." **Phase 2 design:** handling of `uncertain`, the stored decision values, and reusing `matched_exclusion_criteria` for the query rewrite. *Sources: Z5-12, IR M16.*

**A20. Loop 2 must earn its place (D5).** Line 236 allows reranking "only if metrics improve", but Loop 2 is a Must with no such condition. It adds calls to the slowest stage. **Plan:** if D5 = conditional, move Loop 2 behind the Phase 2 baseline and the full-paper experiment, and do parallel extraction first. *Sources: Z8-8.*

**A21. Router: map routes to targets and remove the dependency on `interrupt()` (D6).** The router has four routes, but the diagram shows three targets with different names. `clarify` has no defined behaviour. The research summary is reachable from no route. The Must router depends on the Should `interrupt()`. The "below threshold" and "too few papers" rules have no parameters. The router benchmark is deferred to Phase 3, but Phase 3 has no task for it, and "no tool calling" (line 226) contradicts structured output. **Plan:** a small route-to-target table in 5.2, including `clarify`. Record D6. Add a Phase 3 task: "benchmark router models; decision record; replace the provisional default". **Phase 3 design:** named threshold parameters per embedding model, and whether `context` stays a separate route. *Sources: C-3, Critic M-20, Critic M-18, Z8-11, Z5-19, IR M18, IR N6.*

#### Scope and altitude

**A22. Size security and privacy for one user (D3).** Sections 1-9 contain no failure or security analysis. Line 198, "every query filters by `user_id`", cannot hold for the shared tables. Groq and LangSmith receive user content, while the v1 README says no external API is used. The fixes Stage 7 proposed are sized for a multi-user deployment that does not exist. **Plan:**
- "the API is single-user and bound to localhost until auth exists";
- "user data leaves the machine only to Groq and LangSmith; both can be turned off";
- the `user_id` filter applies only to private tables.

If D3 = backlog, delete lines 164 and 198 and move "Multi-user + auth" to the backlog. **Phase 2 ingestion design:** download size and time limits, no redirects to internal addresses. **Backlog:** prompt-injection handling. **Drop:** a full security subsection. *Sources: Z8-6, Z8-5, Critic M-14, Critic M-15, Critic N-8.*

**A23. Remove Redis and the worker.** "Scaling for many concurrent users" is a non-goal, and line 197 says running inside the API is acceptable. Redis would be a second state store and two more cluster components on a 16 GB laptop. The diagram and 5.1 do not show them anyway. **Plan:** delete them from section 9 and Phase 4. Postgres can serve as a queue if one is ever measured to be necessary. *Sources: Z5-8, Critic N-11.*

**A24. Keep the plan at plan altitude.** Only Router and Loops have design sections, and the HITL scope says "e.g.". The endpoint list, layout tree, YAML block and column table are already out of date or will change soon (Excel mismatch, missing docs, provisional models), and several tool choices are left open ("SQLAlchemy (or SQLModel)", "`kind` or `k3d`"). Completing these blocks, as Stage 7 suggested, is the wrong fix. **Plan:**
- add a "Designed in" column to the section 3 table;
- replace the endpoint list, layout tree and YAML each with one line;
- replace the column table with entities marked shared or private, plus the invariants from A1, A7 and A11;
- mark open tool choices "decided in the Phase N design".

**Phase designs:** the detail. *Sources: Critic M-19, Z8-13, Z5-17, Critic N-13, Critic N-4, Z8-4.*

**A25. List alternatives for the three decisions that are hard to reverse.** Stage 7 rated "no alternatives considered" a Blocker under the feature-spec standard. Stage 8 argued that standard is wrong for a roadmap. This report accepts the downgrade to Major. **Plan:** a "Key decisions" list of at most three rows, each with one rejected alternative and a trade-off: one Postgres store versus FAISS or a separate store; local inference versus the GPU cluster or an API; chat-first versus batch. **Phase designs:** alternatives for everything else. *Sources: Critic B-1, Z8-4.*

**A26. Add a problem statement.** Section 1 describes the product, but it does not say what user problem the move from a one-shot screening table to a chat assistant solves. **Plan:** 2-3 sentences, for example "re-running searches from zero, follow-up questions, and tracking a topic over time". Put goals and non-goals together. **Phase 2 eval design:** numeric v1.0 thresholds once the baseline exists. *Sources: Critic M-1, Critic N-10.*

**A27. State the implied non-goals.** "Track the state of research" and "growing library" suggest features nobody has scoped. **Plan (section 4):**
- scheduled re-search or alerts;
- automatic resume of interrupted runs;
- reusing library papers before searching OpenAlex;
- a PRISMA flow diagram (a reason per paper is stored, nothing more);
- more than one embedding model in production;
- multi-user before v1.0, if D3 = backlog.

*Sources: Z8-12, Z5-21, Critic N-6.*

**A28. Export scope (D8).** "CSV/Excel and BibTeX" is a Must, but the API and Phase 3 support only CSV and BibTeX. BibTeX needs authors and venue, which `papers` does not store. v1 captures authors (`search_agent/agent.py`) and computes venue only in the bypassed gatekeeper path. **Plan:** record D8. **Phase 1 data design:** add `authors` and `venue` to `papers`, and carry `primary_location.source.display_name` through search. Reuse the CSV export in `ui_app.py`. *Sources: Critic M-22, IR M20, IR M21.*

**A29. Split the oversized phases (D7).** Phase 2 holds a labeled dataset, an eval harness, a model benchmark, a decision record, the subgraph, two loops, an experiment and chunk overlap. Phase 3 holds the router, two answer routes, the table, export, the log, the summary, SSE, the UI, `interrupt()` and a router test set. Rule 2's "working, tagged system" checkpoint loses force at that size, and with no deadline nothing forces cuts. **Plan:** if D7 = split, create Phase 2a (eval baseline and benchmark, its own tag) and 2b (pipeline), and limit Phase 3 to Musts. *Sources: Z8-10.*

#### Phase checklists and exits

**A30. Repair tests and CI first in Phase 1.** The pytest and CI task comes last (line 218), but rule 5 requires passing tests after every task. Backlog #1 records 3 of 11 tests failing. A fourth test (`test_screening.py:46-52`) reads a gitignored file and will fail in CI. `TestMainEntryContract` checks the source text of a dev script. "CI is green" is satisfied by an empty suite. **Plan:** move test repair and the smoke check to the top of Phase 1, and state the exit as "existing screening tests pass under the new layout". **Phase 1 design:** a committed fixture, and fake-LLM tests for the screening and extraction nodes. *Sources: IR M3.*

**A31. Decide the Phase 1 table scope and the `user_id` rule before auth.** "Migrations (incl. `user_id`)" does not say whether all seven tables are created in Phase 1, or what fills `user_id` before auth. **Plan:** list the tables the first migration creates. Choose one seeded `local` user with `user_id` NOT NULL. If auth stays (D3), add a Phase 4 task to reassign those rows. *Sources: IR M6.*

**A32. Save the eval input data before the layout move.** The topic-2 candidate data (`Screening_Agent/search_results.json`, `extract_agent/search_results.json`) is gitignored and exists on one machine only. **Plan:** a Phase 1 step, before the layout task, that copies these files into the eval snapshot location and records the retrieval date. *Sources: IR M12.*

**A33. Give the Phase 2 pipeline a caller and a store step.** The main graph and router arrive in Phase 3, so in Phase 2 nothing calls the subgraph. No task creates `reviews` rows or writes `screenings` and `extractions`. **Plan:** name the Phase 2 entry point (for example, the existing job endpoint creates a review and calls the subgraph). Add a store-node task that writes rows with `model` and `prompt_version`. *Sources: IR M15.*

**A34. Make the Phase 3, 4 and 5 exits checkable.** The exits have these gaps:
- **Phase 3:** "a full demo conversation" is manual and checks none of the Must criteria (citations, cell evidence, restart survival), two routes, or the interrupt points.
- **Phase 4:** "one command deploys the full stack" does not define the stack.
- **Phase 5:** "every claim in the README is backed by an eval result" includes architecture statements that no eval can back.
- **Citations:** "every claim references a paper" has no definition of a claim.

**Plan:**
- **Phase 3:** a scripted fake-LLM conversation covering all routes, a restart, citation and cell-evidence checks, and the export.
- **Phase 4:** a checklist of components, probes and the migration that must be up.
- **Phase 5:** "every quality or performance number in the README links to a results file".

**Phase 3 design:** a definition of "claim". *Sources: IR M19, IR M24, Critic M-24.*

**A35. Add a short glossary and a version-scheme sentence.** These terms are undefined: "EGM cycle", "drift report", "drift-free", "task", "step" and "major topic", which collides with research topics and `new_topic`. "v1" means the legacy code, while `v1.0` is the first v2 release tag. Rule 4's "agent session" can be mistaken for the system's own agents. **Plan:** a glossary of about five lines and one version-scheme sentence near the top. *Sources: C-7, Critic M-23, IR M23, C-9, IR N1.*

**A36. Let sessions find the backlog and eval notes.** Rule 4 limits a session to "this plan, the relevant design doc, and the relevant code". `docs/backlog.md` assigns items 1, 2, 3 and 5 to Phase 1 and item 6 to Phase 2, but none appear in the checklists. **Plan:** rewrite rule 4 to include "the backlog items assigned to the current phase and any inputs the design doc names". Reference the backlog items by number in the checklists. Use the path `docs/backlog.md` in rule 7. *Sources: IR M4.*

### 🟢 Nits

**A37. Kubernetes mechanics go to the Phase 4 design.** Split the liveness and readiness probes. A Job does not run before a Deployment (use an initContainer). Run Postgres as a StatefulSet with a PVC. No manifests exist yet; the `host.docker.internal` pattern can be reused. *Sources: Critic N-1, N-2, N-3; IR N16.*

**A38. Cap the unbounded v1 retries.** `api_client.py:86-89` retries HTTP 429 with no limit, and `ui_app.py` polls with no timeout. Loop 1 adds OpenAlex calls on top. Add a Phase 2 task, or extend "no unbounded loops" to cover these. *Sources: IR N12.*

**A39. Correct the bootstrap docs.** `CLAUDE.md` lists `extract_agent.py`, `extraction_agent.py` and `extraction_main.py`, which do not exist. `README.md:240-241` says `SCREENING_MODEL` overrides the model per stage, but `nodes.py:62` hardcodes it. `CLAUDE.md` is loaded into every session, so add these to the backlog or fix them now. *Sources: IR N15.*

**A40. Note the FAISS short-paper edge case.** With fewer than 5 chunks, FAISS returns -1 and the code silently picks the last chunk (`document_processing_node.py:152-157`). Record this in the Phase 2 eval design so that differences between baseline and new results on short papers are explained. *Sources: IR N13.*

**A41. Define or delete the `cloud` profile.** With free tiers only and providers set per role, it has no stated meaning. *Sources: Z5-20, Critic N-23.*

**A42. Editorial fixes.**
- Bold labels become headings.
- Tag the code blocks as `text`.
- Priority and Phase become separate columns.
- "North-star" becomes "reference plan".
- "Approved direction" names the approver.
- "Open-access papers from OpenAlex only".
- Remove the overlaps in the known-gaps list, and name the modules on line 19.
- Make "follow-up questions work" testable.
- Drop "honestly" (line 86).
- Remove repeated statements (factory rule, versioned prompts, one phase at a time).
- "Rule", not "rules", on line 73.
- Expand PRISMA, and say what "fork" means.
- Rewrite line 236 to separate overlap from reranking.
- Use one eval term ("eval harness").
- Write "API keys from `.env`" on line 214.
- Rule 6 reuses line 188's wording.
- Tie the free-tier check to decision points.
- Risk table: "7-8B" and "structured output".
- Name the Phase 0 outputs.
- Clarify "draft" on line 223, and "target hardware" and "quality" on line 226.

*Sources: Critic N-9, N-12, N-14 to N-22, N-24; C-12, C-14; IR N2, N3, N4, N5, N7, N8, N9, N10.*

## Suggested order of work

1. Decide D1-D8. They change the text of about 15 actions.
2. Fix the Blockers A1-A3 and the plan-level sentences that shape the first migration: A4, A5, A7, A9, A11, A12, A14, A31, A32.
3. Apply the scope cuts the decisions allow (A16, A20-A23, A27, A29) and the altitude reduction (A24, A25). Done in this order, the plan shrinks before anything is added.
4. Fix the phase checklists and exits (A30, A33-A36), then the remaining Majors.
5. Create the Phase 1 design doc in `docs/designs/` and move the design-level items listed under "Phase 1 design" there before implementation starts.
6. Nits last, in one editorial pass.

Applying all plan-level text should add about 25-35 sentences and remove about the same amount (7.1, the YAML, the endpoint list, the layout tree, the column table, Redis, evals in CI, the `cloud` profile). If the plan grows by much more than that, the fixes have probably been placed at the wrong level.

## Traceability matrix

Each raw finding maps to the consolidated action that covers it.

**Stage 5: Initial Zoom Out (`zoom_out_report.md`, numbered 1-22)**

| Raw ID | Action | Raw ID | Action | Raw ID | Action |
| --- | --- | --- | --- | --- | --- |
| Z5-1 | A4, A5 | Z5-9 | A17 | Z5-17 | A24 |
| Z5-2 | A7 | Z5-10 | A16 | Z5-18 | A12 |
| Z5-3 | A9 | Z5-11 | A6 | Z5-19 | A21 |
| Z5-4 | A13 | Z5-12 | A19 | Z5-20 | A41 |
| Z5-5 | A14 | Z5-13 | A1 | Z5-21 | A27 |
| Z5-6 | A3, A2 | Z5-14 | A13, A20 | Z5-22 | A15, A21 |
| Z5-7 | A12 | Z5-15 | A15 (contested; Stage 8 view adopted) | | |
| Z5-8 | A23 | Z5-16 | A11 | | |

**Stage 6: Comprehension (`comprehension_report.md`, numbered 1-14)**

| Raw ID | Action | Raw ID | Action |
| --- | --- | --- | --- |
| C-1 | A8 | C-8 | A4 |
| C-2 | A1 | C-9 | A35 |
| C-3 | A21 | C-10 | A13 |
| C-4 | A9 | C-11 | A13 |
| C-5 | A10 | C-12 | A42 |
| C-6 | A16 | C-13 | A17 |
| C-7 | A35 | C-14 | A42 (threshold part: A21) |

**Stage 7: Critic (`critic_report.md`)**

| Raw ID | Action | Raw ID | Action | Raw ID | Action |
| --- | --- | --- | --- | --- | --- |
| B-1 | A25 (downgraded to Major) | M-12 | A11, A19 | M-24 | A34 |
| B-2 | A1 | M-13 | A12 | M-25 | A18 |
| M-1 | A26 | M-14 | A22 | M-26 | A18 |
| M-2 | A6 | M-15 | A22 | N-1, N-2, N-3 | A37 |
| M-3 | A16 | M-16 | A17 | N-4 | A24 |
| M-4 | A3 | M-17 | A18 | N-5 | A15 |
| M-5 | A13 | M-18 | A21 | N-6 | A27 |
| M-6 | A7 | M-19 | A24 | N-7 | A14 |
| M-7 | A8 | M-20 | A21 | N-8 | A22 |
| M-8 | A8 | M-21 | A10 | N-10 | A26 |
| M-9 | A13 | M-22 | A28 | N-11 | A23 |
| M-10 | A9 | M-23 | A35 | N-13 | A24 |
| M-11 | A9 | | | N-23 | A41 |
| | | | | N-9, N-12, N-14 to N-22, N-24 | A42 |

**Stage 8: Intermediate Zoom Out (`intermediate_zoom_out_report.md`)**

| Raw ID | Action | Raw ID | Action |
| --- | --- | --- | --- |
| zoom-out-8-1 | A7, A11, A1, A24 | zoom-out-8-8 | A20 (D5) |
| zoom-out-8-2 | A3 | zoom-out-8-9 | A3 (D1) |
| zoom-out-8-3 | A18 | zoom-out-8-10 | A29 (D7) |
| zoom-out-8-4 | A25, A24 | zoom-out-8-11 | A21 (D6) |
| zoom-out-8-5 | A22 | zoom-out-8-12 | A27 |
| zoom-out-8-6 | A22 (D3) | zoom-out-8-13 | A24 |
| zoom-out-8-7 | A16 (D4) | zoom-out-8-14 | A2 |

**Stage 9: Implementation Readiness (`implementation_readiness_report.md`)**

| Raw ID | Action | Raw ID | Action | Raw ID | Action |
| --- | --- | --- | --- | --- | --- |
| IR B1 | A2 | IR M11 | A15 | IR M22 | A17 |
| IR B2 | A3 | IR M12 | A32 | IR M23 | A35 |
| IR M1 | A4 | IR M13 | A18 | IR M24 | A34 |
| IR M2 | A5 | IR M14 | A1 | IR N1 | A35 |
| IR M3 | A30 | IR M15 | A33 | IR N6 | A21 |
| IR M4 | A36 | IR M16 | A19 | IR N11 | A6 |
| IR M5 | A2 | IR M17 | A8 | IR N12 | A38 |
| IR M6 | A31 | IR M18 | A21 | IR N13 | A40 |
| IR M7 | A3 | IR M19 | A34 | IR N14 | A12 |
| IR M8 | A10 | IR M20 | A28 | IR N15 | A39 |
| IR M9 | A14 | IR M21 | A28 | IR N16 | A37 |
| IR M10 | A10 | | | IR N2-N5, N7-N10 | A42 |

## Severity changes made in consolidation

- **Critic B-1 (no alternatives) went from Blocker to Major (A25).** The feature-spec standard asks for alternatives for every decision. For a roadmap whose phase designs will hold those choices, a three-row key-decisions list is the right size. Stage 8 made the same argument.
- **IR B1, IR B2, Critic B-2 and the merged findings stay Blockers (A1-A3).** Each was confirmed against the code (`Backend/main.py:24`, `:38`, `:96`; `Orchestration/graph.py:49`) or by the logic of the plan's own text (lines 91, 173 and 238), and each stops a phase from ending cleanly.
- **Z5-12 (Loop 1 count) stays Major (A19).** Stage 5 had already raised it from Nit, and IR M16 confirmed the `target_output_count` clash in `Backend/schemas.py:10`.
