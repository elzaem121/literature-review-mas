# Goldfish Review Report

**Target:** `/Users/mohamedelsayed/PycharmProjects/literature-review-mas-neu/docs/plan_v2.md` (lines 1-294, full file)

**Stage:** 8 (Intermediate Zoom Out). Focus: altitude and scope. Part (a) looks at what happens to the plan if the Stage 5-7 findings are applied. Part (b) covers scope and simplicity issues those stages missed.

**Inputs:** the Stage 5 report (`zoom_out_report.md`), the Stage 6 report (`comprehension_report.md`) and the Stage 7 report (`critic_report.md`). The reviewer also read the v1 baseline files: `README.md`, `docs/backlog.md`, `docs/eval_notes.md`, `Orchestration/graph.py` and `Orchestration/state.py`. The plan has not been edited since those reports were written. `docs/designs/` contains only `.gitkeep`.

**ID notation for earlier findings:**
- `Z5-n`: Stage 5 Zoom Out
- `C-n`: Stage 6 Comprehension
- `B-n`, `M-n`, `N-n`: Stage 7 Critic (Blocker, Major and Nit)

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `zoom-out` (egm:egm-zoom-out, single instance) | completed |

## Summary

- **Severity breakdown:** 0 Blocker, 12 Major, 2 Nit.
- **Main conclusion:** The plan is at the right level for a north-star document. The main risk is in how the earlier findings get applied. Stages 5-7 produced about 88 findings. If all of them were written into the plan, it would become the design spec for Phases 1-3. The rule on line 3 says design docs must stay consistent with the plan, so every extra detail in the plan is one more thing that can drift. About a quarter of the earlier findings need plan text, usually one sentence or one invariant. Most of the rest belong in phase design docs under `docs/designs/`. A few belong in the backlog or should be dropped.
- **Net effect of following this report:** the plan gains about 15-20 sentences and loses about the same amount: section 7.1, the YAML block, the endpoint list, the layout tree, the column table, Redis, evals in CI and the `cloud` profile.
- **Needs your decision:** Findings zoom-out-8-6, -7, -8 and -12 propose cutting or deferring features the plan currently lists as approved (multi-user, research summary, Loop 2 as a Must, the router-level `interrupt()`). They are proposals and need the plan owner's decision before anyone applies them.

## Prioritized Findings (Blockers -> Major -> Nits)

No Blockers.

---

### zoom-out-8-1: Applying the schema findings would turn section 6 into a data-model spec - Severity: Major
* **Reviewer Lens:** `zoom-out` (part a)
* **Affected Scope:** Lines 113-135 (section 6), 89-93 (Loop 2 status and state)
* **Discrepancy Description:** Fourteen earlier findings touch the schema: Z5-2, Z5-13, Z5-15, Z5-16, Z5-17, B-2, M-6, M-8, M-12, M-13, N-5, N-6, C-1 and C-2. Applied together, they add the following to section 6:
  - a `chunk_embeddings` table
  - an external-ID mapping table
  - an ingestion status column with a retry policy
  - append-only extraction keys with a "current" view
  - a fourth field status
  - the shape of the `criteria` jsonb
  - the values of `screenings.decision`
  - the full list of extraction fields
  - a rule for how long checkpoints are kept

  Z5-17 already says the column table is too detailed for this plan. Applying the other findings there would contradict it.
* **Rationale & Recommendation:** Replace the column table with a list of entities, each marked shared or private. Then add four invariants of one sentence each:
  1. Shared extractions hold only fields that do not depend on a review. Judgments tied to one review are stored per review.
  2. LLM outputs are append-only and record `model` and `prompt_version`. A re-run adds rows and never overwrites.
  3. A paper is stored once, whatever its OpenAlex ID or DOI variants.
  4. "Not found after retries" is stored separately from `not_reported`.

  Keys, enums, ingestion status and ID mapping go in a Phase 1 data-model design doc. The field list and the meaning of each status go in the Phase 2 extraction design doc.

### zoom-out-8-2: Applying the run-lifecycle findings would put a job-system design into the plan - Severity: Major
* **Reviewer Lens:** `zoom-out` (part a)
* **Affected Scope:** Lines 62-63, 193, 197, 217-220
* **Discrepancy Description:** Z5-6, Z5-7, Z5-8, M-4, M-13 and N-11 together describe a durable job queue with automatic resume. Z5-6 includes the Inventive Catalyst proposal: `SKIP LOCKED`, LISTEN/NOTIFY, an attempt counter and a dead-letter state. That is a lot of machinery for one user on a laptop. The only Must that needs persistence is "conversations survive restarts" (line 27); nothing requires in-flight pipeline runs to resume. Ingestion is already idempotent: papers are upserted and each paper is chunked once (line 129). Re-running an interrupted run therefore reuses most of the stored work.
* **Rationale & Recommendation:** Add one decision sentence to the plan:

  > "A pipeline run is decoupled from the HTTP request. Its status is stored in Postgres. On restart, unfinished runs are marked interrupted and the user can re-run them."

  Drop the automatic-resume loop, `SKIP LOCKED`, LISTEN/NOTIFY and dead-letter handling. Put the status and reconnect endpoint shapes in the Phase 3 design. This is related to zoom-out-8-9 and zoom-out-8-6, which remove Redis and the worker.

### zoom-out-8-3: Applying the evaluation findings would copy `eval_notes.md` into section 8 - Severity: Major
* **Reviewer Lens:** `zoom-out` (part a)
* **Affected Scope:** Lines 166-188 (section 8), 199, 238
* **Discrepancy Description:** M-1 (thresholds table), M-9 (the metric part), M-16, M-17, M-24, M-25, M-26, Z5-9 and C-8 each add more evaluation detail to section 8:
  - M-17 adds recall@k, evidence-page accuracy and per-loop yield.
  - M-25 adds kappa thresholds.
  - M-26 adds a noise-based decision rule.

  `docs/eval_notes.md` is still a draft, and these questions are meant to be settled in Phase 2. Each one added to the plan becomes a second copy that can disagree with the first. Section 8 already disagrees with the notes (M-17).
* **Rationale & Recommendation:** Reduce section 8 to about six principles:
  - The judge always sees the source.
  - Calibrate the judge before trusting it.
  - The judge must not be the model that generated the output.
  - Datasets are fixed and versioned.
  - The local results file is the record; the LangSmith upload is optional.
  - Live evals run at each phase exit, not in CI.

  Link to the Phase 2 eval design doc. Metrics, thresholds and decision rules go there.

### zoom-out-8-4: Stage 7 judged a roadmap by the feature-spec standard (B-1, M-19) - Severity: Major
* **Reviewer Lens:** `zoom-out` (part a)
* **Affected Scope:** Sections 3 and 5-9
* **Discrepancy Description:** Stage 7 checked the plan against `feature-spec-standard.md`. B-1 asks for rejected alternatives for nine decisions. M-19 asks for one H3 section per feature and the missing endpoints. Together that is the content of the design docs, written into the plan.
* **Rationale & Recommendation:** For this document type, downgrade B-1 from Blocker.
  - The plan should hold a "Key decisions" list of at most three rows, one for each decision that is expensive to reverse: one Postgres store; local inference instead of the GPU cluster or an API; chat-first instead of batch. Give one rejected alternative per row.
  - For M-19, add a "Designed in" column to the section 3 table instead of per-feature H3 sections.
  - Alternatives for the other decisions go in each phase's design doc or decision record.

### zoom-out-8-5: The security and privacy findings are sized for a multi-user deployment that does not exist yet - Severity: Major
* **Reviewer Lens:** `zoom-out` (part a)
* **Affected Scope:** Lines 115, 132, 164, 198
* **Discrepancy Description:** M-14 asks for a full "Failure modes and security" subsection covering an SSRF allowlist, prompt-injection handling, ownership checks and fallbacks. M-15 and N-8 add more privacy detail. Until Phase 4 the system runs for one user on a laptop.
* **Rationale & Recommendation:** Add two lines to the plan:
  - The API is single-user and bound to localhost until auth exists.
  - User data leaves the machine only to Groq and LangSmith, and both can be turned off.

  Change line 198 so the `user_id` filter applies only to private tables. Placement of the remaining items:
  - Download size and time limits: Phase 2 ingestion design.
  - Ownership checks: Phase 4 design.
  - Prompt injection: backlog.
  - Full security subsection: drop.

### zoom-out-8-6: Multi-user and auth are speculative for v1.0 and drive much of the design - Severity: Major
* **Reviewer Lens:** `zoom-out` (part b)
* **Affected Scope:** Lines 37, 41, 115, 119-121, 132, 164, 198, 255
* **Discrepancy Description:** Deployment is a local `kind`/`k3d` cluster on one laptop (line 193), and "scaling for many concurrent users" is a non-goal (line 41). The multi-user work therefore has no second user. Several earlier findings exist only because of it:
  - M-10's concern about data leaking between users
  - M-14's ownership checks
  - the cross-user cache rule on line 164
  - the contradiction between line 198 and the shared paper tables on line 115
* **Rationale & Recommendation:** Keep the system single-user through v1.0 and move "Multi-user + auth" to the backlog. Keep the `user_id` column, which costs almost nothing. Delete lines 164 and 198. If a multi-user demo is a hard portfolio goal, say so in section 1; nothing in the current goal requires it. **Needs the plan owner's decision.**

### zoom-out-8-7: The research summary (a Should) brings in a second provider, the self-judging conflict and data leaving the machine - Severity: Major
* **Reviewer Lens:** `zoom-out` (part b)
* **Affected Scope:** Lines 35, 147, 174, 244
* **Discrepancy Description:** The research summary is the only reason for the `summary` role and for calling Groq at runtime. It also causes:
  - the conflict where the judge grades its own output (Z5-10, M-3, C-6)
  - the summary part of M-15 (user data sent off the machine)

  The evidence table already shows the state of research for a review.
* **Rationale & Recommendation:** Move the research summary to the backlog, or make it an optional item after the Phase 3 exit. Groq is then used only as the eval judge, and the self-judging conflict goes away for v1.0. **Needs the plan owner's decision.**

### zoom-out-8-8: Loop 2 is a Must with no measured need, while other retrieval changes must prove themselves first - Severity: Major
* **Reviewer Lens:** `zoom-out` (part b)
* **Affected Scope:** Lines 30, 88-93, 234, 236
* **Discrepancy Description:** The plan applies two different standards:
  - Line 236 allows hybrid search and reranking "only if metrics improve".
  - Loop 2 is a Must with no such condition.

  Loop 2 adds extraction calls to extraction, which is already the slowest stage (51% of runtime). Three earlier findings, B-2, Z5-13 and Z5-14, are entirely about how Loop 2 behaves.
* **Rationale & Recommendation:** Keep Loop 1 as a Must; it is cheap and was already on the v1 roadmap. Make Loop 2 conditional on two results: the share of empty fields measured in the Phase 2 baseline, and the outcome of the full-paper versus chunk experiment (line 235). Most of the design work for Z5-13 and Z5-14 then waits until it is needed. Do parallel extraction first, since it is the speedup that has been measured. **Needs the plan owner's decision.**

### zoom-out-8-9: The Phase 1 checkpointer has no consumer until Phase 3 - Severity: Major
* **Reviewer Lens:** `zoom-out` (part b)
* **Affected Scope:** Lines 133, 197, 217, 220
* **Discrepancy Description:** `PostgresSaver` is needed for chat memory and `interrupt()`, and both arrive in Phase 3. In Phases 1-2 a pipeline run is a single call. Requiring the checkpointer in Phase 1, together with the Phase 1 exit "a restart loses nothing" (line 220), creates the restart problem that Z5-6 and M-4 discuss. Line 197 also uses the checkpointer to justify running async in the API until Phase 4.
* **Rationale & Recommendation:** Move the checkpointer to Phase 3. Change the Phase 1 exit to "a restart loses no completed results". The library tables plus a run-status row (zoom-out-8-2) already meet that.

### zoom-out-8-10: Phases 2 and 3 are each really two phases - Severity: Major
* **Reviewer Lens:** `zoom-out` (part b)
* **Affected Scope:** Lines 222-249
* **Discrepancy Description:**
  - **Phase 2** covers: labeling the gold dataset, the eval harness, the model benchmark, the decision record, the subgraph, both loops, an experiment and chunk overlap.
  - **Phase 3** covers: the router, two answer routes, the evidence table, export, the screening log, the summary, SSE, the chat UI, `interrupt()`/resume and a router test set.

  Rule 2 (line 285) says each phase ends with a working, tagged system. Phases this large weaken that checkpoint, and with no deadline nothing forces cuts (see the risk row on line 279).
* **Rationale & Recommendation:** Split Phase 2 into "Eval baseline + benchmark", with its own tag, and "Pipeline". Limit Phase 3 to the Must features; the Shoulds go after the Phase 3 exit or to the backlog.

### zoom-out-8-11: A router-level `interrupt()` is probably unnecessary in a chat app - Severity: Major
* **Reviewer Lens:** `zoom-out` (part b)
* **Affected Scope:** Lines 36, 63, 79, 246
* **Discrepancy Description:** In a chat, every user turn is already a pause. "I have little on this. Search for new papers?" (line 79) can be an ordinary assistant reply. The user's next message ("yes") then goes through the router to `new_topic`, using `rewritten_query`. This settles two earlier findings without adding text:
  - M-18: a Must (the router) depends on a Should (human-in-the-loop).
  - C-3: it is unclear which route handles "yes".

  `/chat/resume` would then be needed only if pauses inside the pipeline are adopted.
* **Rationale & Recommendation:** Rewrite rule 2 in section 5.2 as a normal reply. Keep `interrupt()` and `/chat/resume` only under the human-in-the-loop Should, for pauses inside the pipeline. **Needs the plan owner's decision.**

### zoom-out-8-12: Several non-goals are implied but not stated - Severity: Major
* **Reviewer Lens:** `zoom-out` (part b)
* **Affected Scope:** Lines 8, 10, 39-41
* **Discrepancy Description:** "Track the state of research" (line 10) and "growing library" (line 8) suggest features nobody has scoped, such as scheduled re-searches or alerts for new papers. Several earlier findings also assume features the plan never mentions:
  - automatic resume of interrupted runs
  - searching the library before OpenAlex (Z5-21)
  - a full PRISMA flow diagram (N-6)
  - more than one embedding model in production (Z5-15)
  - remote or GPU inference hosting

  In addition, Excel export is listed as a feature (line 33) but has no endpoint (line 64).
* **Rationale & Recommendation:** Add these to section 4, each with a short reason:
  - scheduled re-search or alerts
  - automatic resume of interrupted runs
  - reusing library papers before searching OpenAlex
  - a PRISMA flow diagram (only a reason per paper is stored)
  - Excel export (remove it from line 33)
  - more than one embedding model in production
  - multi-user before v1.0 (if zoom-out-8-6 is accepted)

---

### zoom-out-8-13: Some sections hold detail that is known to change soon - Severity: Nit
* **Reviewer Lens:** `zoom-out` (part b, extends Z5-17)
* **Affected Scope:** Lines 61-65 (endpoints), 95-111 (layout tree), 141-149 (YAML)
* **Discrepancy Description:** Each of these blocks is already out of date or will change soon:
  - The endpoint list disagrees with the feature list on Excel (M-22).
  - The layout tree is incomplete (N-13).
  - The YAML values are marked provisional and will be replaced at Phase 2.

  M-19 and N-13 suggest completing these blocks. That is the wrong fix.
* **Rationale & Recommendation:** Replace each block with one line:
  - "FastAPI with SSE streaming"
  - "the pipeline is its own subgraph package; prompts are versioned files"
  - "one model per role, set in settings"

  Move the details to the Phase 1 design doc.

### zoom-out-8-14: The plan does not say which v1 code is retired - Severity: Nit
* **Reviewer Lens:** `zoom-out` (part b)
* **Affected Scope:** Line 213 (Phase 1, "New repository layout")
* **Discrepancy Description:** These v1 parts are not used by the graph and have no place in v2:
  - `App_Main/streamlit-app.py` (a second UI)
  - `search_agent/archiv/app.py` (broken)
  - `extract_agent/add_full_text_from_pdfs.py`
  - the script parts of `extract_agent/rag_extraction_main.py`
  - after the move to pgvector, the `faiss-cpu` and `sentence-transformers` dependencies

  Backlog items 2 and 3 treat some of these as things to fix rather than delete.
* **Rationale & Recommendation:** Add one line to Phase 1: "v1 modules not used by the graph are deleted, not moved." Close backlog items 2 and 3 by deleting the code.

---

## Appendix: Where each earlier finding belongs

This table shows where each earlier finding should land. "Plan" means text in `docs/plan_v2.md`. "Phase N design" means a design doc under `docs/designs/`.

| Earlier ID | Placement | Reason |
| --- | --- | --- |
| Z5-1 | Plan: 1-2 sentences | Defines the baseline ("Phase 1 system with provisional models"), which decides phase order. Move eval_notes Q6 to section 14 or settle it there. |
| Z5-2, M-6 | Plan: 1 invariant (zoom-out-8-1). Keys: Phase 1 data design. Field split: Phase 2 extraction design. | Shared versus per-review data is architecture. The key columns are not. |
| Z5-3, M-10, C-4 | Plan: 2-sentence decision | Library scope and the number of reviews per conversation shape the schema and the privacy model. |
| Z5-4, C-10, C-11 | Plan: shorten 7.1 and mark full-paper context as a hypothesis. Evidence linking: Phase 2 design. Expanding CAG: drop. | Shortening removes a claim that has not been tested. Once 7.1 is cut, CAG needs no explanation. |
| Z5-5, N-7 | Plan: 1 sentence on the return type and the embedder. Fallback mechanics: Phase 1 design. | Every agent depends on this interface. |
| Z5-6, M-4 | Plan: 1 decision sentence (zoom-out-8-2). Endpoints: Phase 3 design. Queue and resume machinery: drop. | For one user, marking runs interrupted and letting the user re-run them is enough. |
| Z5-7, M-13 | Plan: 1 constraint (graph state holds IDs and small values). Retention: Phase 3 design. | The constraint applies across layers. Retention is operational detail. |
| Z5-8, N-11 | Plan: delete Redis and the worker | No stated need, and it removes a second place where state is stored. |
| Z5-9, M-16, C-13 | Plan: 1 sentence (CI runs lint and unit tests). Response replay: backlog. | Simpler. Live evals cannot run in hosted CI. |
| Z5-10, C-6, M-3 | Plan: 1 sentence (the judge differs from the generator). Token estimates: Phase 3 design. | Mostly moot if the summary is deferred (zoom-out-8-7). |
| Z5-11, M-2 | Plan: a latency budget in section 11 and the Phase 2 exit, 1 risk row, a corrected "~5 min on GPU" figure, and whether the GPU cluster is available. Call estimates and fallback order: Phase 2 design. | The budget belongs in the plan. The arithmetic does not. |
| Z5-12 | Plan: a 1-line redefinition of the count. Handling of `uncertain`: Phase 2 design. | What the loop guarantees belongs in the plan. |
| Z5-13, B-2, C-2 | Plan: 1 invariant and a corrected exit criterion. Status definitions: Phase 2 design. Re-extraction queue: backlog. | The current exit criterion is met automatically. |
| Z5-14 | Phase 2 design | Depends on the experiment result. Moot if Loop 2 is deferred (zoom-out-8-8). |
| Z5-15 | Drop | The benchmark runs on frozen snapshots outside the production database (eval_notes). Re-embedding a small library is cheap. |
| Z5-16, M-12 | Plan: 1 invariant. Upsert key and ingestion status: Phase 1 design. Mapping table: drop unless duplicates are measured. | Upserting on DOI, or on the OpenAlex ID when there is no DOI, is simpler. |
| Z5-17 | Plan: apply, and extend it to 5.1, 5.4 and the YAML (zoom-out-8-13) | Less to keep in sync. |
| Z5-18 | Phase 2 design | Detail about graph state. Remove line 93 from the plan. |
| Z5-19 | Phase 3 design | Decide using router eval data. |
| Z5-20, N-23 | Plan: delete the `cloud` profile | It has no use when the budget is free tiers only. |
| Z5-21 | Backlog | A new feature. List it as a non-goal (zoom-out-8-12). |
| Z5-22, C-14 (threshold part) | Phase 3 design | Calibration detail. |
| C-1, M-7 | Plan: 1 sentence ("a fixed, domain-generic field set, defined in the Phase 2 design"). Field list: Phase 2 design. | Settles the domain-agnostic claim without listing the fields in the plan. |
| C-3, M-20 | Plan: a short mapping from route to target | Fixes the diagram. The change is small. |
| C-5, M-21 | Plan: one canonical stage list that includes ingestion. PDF failures and abstract-only papers: Phase 2 design. | The pipeline's structure belongs in the plan. |
| C-7 | Plan: 1 sentence | Rules 3-4 cannot be followed without the definition. |
| C-8 | Plan: 1 sentence | The Phase 2 exit depends on what the gold dataset contains. |
| C-9, M-23 | Plan: 1 sentence | Version scheme. |
| C-12, C-14 (PRISMA and fork parts) | Plan: wording | Editorial. |
| B-1 | Design doc for each phase. Plan: a key-decisions list of at most 3 rows. | Wrong standard for a roadmap (zoom-out-8-4). |
| M-1 | Plan: a problem statement of 2-3 sentences. Thresholds: Phase 2 eval design. | Placeholder thresholds add nothing before a baseline exists. |
| M-5 | Phase 2 design. Delete the caching claim from the plan. | `num_ctx` handling is experiment detail. |
| M-8 | Phase 1 data design and Phase 2 extraction design | Enums and the jsonb shape are design detail. |
| M-9 | Plan: limit the requirement to `found` cells. Quote matching: Phase 2 design. Page metric: Phase 2 eval design. | The requirement belongs in the plan. The mechanism does not. |
| M-11 | Plan: 1 sentence on how criteria are collected. The flow: Phase 3 design. | The pipeline cannot run without criteria. |
| M-14, M-15, N-8 | Plan: 2 lines and the line-198 fix (zoom-out-8-5). The rest: Phase 2 or Phase 4 design, or backlog. The full security subsection: drop. | Sized for one user on a local machine. |
| M-17 | Plan: a status line, and shorten section 8 (zoom-out-8-3) | Do not expand section 8. |
| M-18 | Plan: settled by zoom-out-8-11. Parameters: Phase 3 design. | A chat reply removes the dependency on a Should. |
| M-19 | Plan: a "Designed in" column. Per-feature H3s: drop. Endpoints: Phase 3 design. | Wrong level of detail for the plan. |
| M-22 | Plan: delete Excel | The simplest fix. |
| M-24 | Phase 3 design | Defining what counts as a claim is design detail. |
| M-25, M-26 | Phase 2 eval design. Plan: rule 6 adds only "beyond noise". | Weak point 4 in eval_notes already covers this. |
| N-1, N-2, N-3 | Phase 4 design | Kubernetes mechanics. |
| N-4 | Plan: remove the tool choices, or mark them "decided in the Phase N design" | Wrong level of detail for the plan. |
| N-5 | Phase 1 design | Moot with only one embedding model in production. |
| N-6 | Plan: expand "PRISMA" and say "a reason per paper only". History and counts: backlog. | Scope statement. |
| N-13 | Plan: delete the layout tree (zoom-out-8-13) | Better than completing it. |
| N-9, N-10, N-12, N-14 to N-22, N-24 | Plan: editorial | No effect on scope. |
