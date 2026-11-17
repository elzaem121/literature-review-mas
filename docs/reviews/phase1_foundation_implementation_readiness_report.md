# Implementation Readiness Report — Stage 9

*   **Target**: `docs/designs/phase1_foundation.md`, DetailedRange lines 413–808 (`## Detailed Implementation Plan` through end of file)
*   **Round**: 1
*   **Reviewers**: `egm-implementation-readiness` (completed), `egm-codebase-details` (completed), `egm-style` (completed)
*   **Standards**: implementation-readiness-standard (implementation-readiness, codebase-details); persona-only (style)
*   **Goldfish context**: `docs/plan_v2.md`, `concepts_brief.md`; codebase-details additionally verified claims against the v1 source tree
*   **Date**: 2026-11-16

## Summary

2 Blockers, 12 Majors, 17 Nits after deduplication (3 cross-reviewer merges).

The plan's claims about the existing code are mostly accurate: the codebase-details reviewer confirmed the hardcoded model at `Orchestration/nodes.py:62`, the email at `search_agent/new_main.py:16`, the module-import-time client in `rag_extraction_main.py`, the hand-rolled screening retry loop, the full 1c.1 deletion list, and the Create/Modify/Move/Delete markers. The failures are concentrated in two places: (1) two sequencing/architecture gaps that make the plan's own per-commit green check impossible as written (B1, B2), and (2) a cluster of spots where the plan names a mechanism without designing it, leaving the implementer a decision the standard says the plan must make (M1–M9).

## Blockers

### B1 — Post-2b, the fake e2e and golden-transcript tests cannot run where the plan says they run

*   **Source**: impl-readiness #1
*   **Lines**: 749–760 (2b.1), 776–780 (2b.4), 788–801 (Verification Plan); context 199–204, 277–288
*   **Finding**: Commit 2b rewrites ingestion onto Postgres + pgvector, but the fake surface fakes exactly four seams (LLM, embedder, OpenAlex, PDFs) and has no database seam. The Verification Plan keeps the fake e2e (1a.15) and golden-transcript diff (1a.17) in `make test` (`-m "not integration"`) and CI, and requires the fake e2e to pass after every commit — while the design and brief state CI unit tests need no database. After 2b, the graph-level fake run invokes ingestion, which requires pgvector. The implementer must choose between: a fake repository/DB seam, Postgres in the CI unit job (contradicts the CI architecture), or demoting the e2e/golden tests to the `integration` marker (contradicts "unintended behaviour change fails CI" and the per-commit check). The plan must pick one and specify it.

### B2 — Commit 1a as specified fails its own per-commit check: removing root `tracing.py` breaks five modules still at v1 paths

*   **Source**: codebase-details #1
*   **Lines**: 506–510 (1a.3), 570–574 (1a.12), 576–581 (1a.13), 590–594 (1a.15), 800–801
*   **Finding**: `tracing.py` exports `traceable_stage`, `root_trace`, and `tracing_enabled` in addition to `maybe_wrap_openai`, imported at module level by `Backend/main.py:10`, `Orchestration/nodes.py:12`, `extract_agent/document_processing_node.py:11`, and `extract_agent/rag_extraction_main.py:13`. 1a.3 removes the root module, but in commit 1a those files are still at v1 locations and their step entries do not authorize rewriting the `tracing` import (`Backend/main.py` appears in no 1a step at all). `Orchestration/graph.py:14` imports `document_processing_node`, so the graph cannot compile and the 1a.15 smoke — the declared per-commit green check — fails at commit 1a. 1a.3 also documents moving only `maybe_wrap_openai`, omitting the other three public helpers the move must carry.

## Majors

### M1 — The "four buckets" node test cannot be built from the specified fake-LLM contract

*   **Source**: impl-readiness #2 + style #2 (merged)
*   **Lines**: 583–588 (1a.14), 512–519 (1a.4), 439–445 (0.3)
*   **Finding**: 1a.14 requires fixture papers to "produce the four buckets via sentinels," but 1a.4 defines only `[FAKE:EXCLUDE]` and `[FAKE:UNCERTAIN]` plus a canned `include` default — three outcomes. The `failed` bucket is populated in v1 only when the LLM call raises; no raising mechanism is defined for the fake. The fixture spec ("3–5 papers") also leaves the roster to the implementer, and that roster determines the committed golden-transcript content: four buckets plus the two-IDs-one-DOI pair cannot fit in 3 papers. Specify the failure mechanism (e.g., a `[FAKE:FAIL]` sentinel whose registry callable raises) and the exact fixture roster (paper count, sentinel-to-paper assignment, which pair shares the DOI).

### M2 — Golden-transcript diff mechanism is named but not designed

*   **Source**: impl-readiness #3
*   **Lines**: 602–608 (1a.17), 776–780 (2b.4)
*   **Finding**: Three decisions are left open: (a) how a register entry like "V2 per-page chunk boundaries" is mechanically expressed as an allow-list (JSON pointer paths, field globs, per-key comparators?); (b) how volatile fields (run UUIDs, timestamps, absolute PDF paths) are normalized so the diff is deterministic; (c) what the post-regeneration allow-list contains ("shrinks accordingly" — to which entries? V6 lands before capture; V4 is API-layer and likely invisible to a graph-level state dump). This test is the design's central drift guard; two implementers would build materially different enforcement.

### M3 — Schema spec defers to a column table that declares itself incomplete

*   **Source**: impl-readiness #4
*   **Lines**: 691–697 (2a.2), 699–705 (2a.3); referenced table at 211–217
*   **Finding**: 2a.2 says models are "exactly as the Technical Plan's column table," but that table is headed "key ones." Undecided: PK types for `users`/`reviews`/`papers`/`chunks` (only `runs.id` is uuid); FK `ON DELETE` behavior (relevant to delete-then-insert on `chunks`); uniqueness on `chunks` (`(paper_id, ordinal)` vs `(paper_id, page, ordinal)`); timestamps on `papers`; nullability of undiscussed columns. The brief's Key Decisions item 8 promised a DDL-level column list; either promote the table to exhaustive or add the missing decisions to 2a.2.

### M4 — Required settings are never wired into compose or CI, so the compose `/health` check fails as specified

*   **Source**: codebase-details #2 + style #5 (merged)
*   **Lines**: 490–496 (1a.1), 610–614 (1a.18), 685–689 (2a.1), 782–786 (2b.5)
*   **Finding**: 1a.1 makes `openalex_email` required with no default and settings validated at startup. The current `docker-compose.yml` backend environment passes only `OLLAMA_BASE_URL` and LangSmith vars; 2a.1 adds only `DATABASE_URL`; 2b.5's CI compose step passes only a dummy `OLLAMA_BASE_URL`. Nothing adds `OPENALEX_EMAIL` (or `PROFILE`) to compose or CI, so startup validation fails and `GET /health` never answers. Related internal contradiction: 1a.1 creates `database_url` in commit 1a, but 1a.18 says `.env.example` lists "every setting from 1a.1" yet "2a adds `DATABASE_URL`" — and no Postgres exists until 2a, so whether `database_url` is required, optional, or defaulted during 1a/1b is unstated.

### M5 — The stub OpenAlex client's seam contradicts the fixture's shape

*   **Source**: codebase-details #3
*   **Lines**: 439–445 (0.3), 512–518 (1a.4)
*   **Finding**: The real `OpenAlexClient.execute_retrieval` (`search_agent/api_client.py:47–135`) returns raw OpenAlex work dicts (`abstract_inverted_index`, `authorships`, `primary_location`), which `agent.py:167–191` reformats into `{"papers": [...]}`. The 0.3 fixture is "trimmed from the real v1 output" — the formatted shape — and 0.1 repoints a screening test at the same file, which validates the formatted shape. One fixture cannot feed both the raw-OpenAlex seam and the formatted-paper consumer. The plan must say where the stub plugs in (replace `OpenAlexClient`, or replace `run_precise_retrieval_cycle`'s output) and whether the fixture bypasses the formatting loop.

### M6 — `pdf_url` and `openalex_id` sources and normalization are unspecified, though they feed a unique key

*   **Source**: codebase-details #4
*   **Lines**: 528–535 (1a.6), 707–712 (2a.4), 769–774 (2b.3)
*   **Finding**: The plan gives venue's source expression but not `pdf_url`'s; the code computes `primary_loc.get("pdf_url") or best_oa.get("pdf_url")` inside `api_client.execute_retrieval:109` and discards it, so the formatting loop must re-derive it, and the primary-vs-`best_oa_location` ordering is a real choice that register entry V1 depends on. `openalex_id` comes from `paper.get("id")`, a full URL (`https://openalex.org/W...`); whether `papers.openalex_id` stores the URL or the bare ID is undefined, yet it is a unique column and one leg of the upsert SELECT. The duplicate-DOI test (2b.3) silently depends on this.

### M7 — Directed consumer updates contradict the code: neither named consumer references `ResearchPaper`

*   **Source**: codebase-details #5
*   **Lines**: 556–561 (1a.10)
*   **Finding**: `Backend/schemas.py` models the screening buckets as `List[Dict[str, Any]]` and `ui_app.py` consumes raw JSON dicts over HTTP — neither imports `screening_schemas` nor enumerates paper fields. "Consumers (`Backend/schemas.py`, `ui_app.py`) updated in the same commit" names changes with no definition: adding optional-with-default fields requires no change in either file as the code stands. Either drop the claim or define the actual update.

### M8 — The duplicate-import repair and path shim are underspecified in exactly the dimension that causes the bug being fixed

*   **Source**: codebase-details #6
*   **Lines**: 422–431 (0.1), 433–437 (0.2)
*   **Finding**: The duplicate `ResearchPaper` identity arises because `test_screening.py:6–7` imports top-level modules while `screening_agent.py:11` imports `Screening_Agent.screening_schemas`. The plan does not state which import becomes canonical, and 0.2's shim does not say whether it inserts the repo root or the `Screening_Agent/` directory — the wrong choice keeps both module identities importable, reproducing the exact dual-identity failure (the failure mode Alternative B was rejected for). 0.4's `pythonpath = ["."]` already covers the repo root; the shim's remaining purpose (the package dir) is the dangerous half.

### M9 — Deletion file boundary is not explicit; "the now-empty v1 directories" is false as written

*   **Source**: codebase-details #7
*   **Lines**: 667–676 (1c.1)
*   **Finding**: Every named deletion target exists, but tracked leftovers are unnamed: `Backend/__init__.py`, `Orchestration/__init__.py`, `search_agent/__init__.py` (1b.1 moves only four named files), and `extract_agent/.gitignore`. Until those are deleted the v1 directories are not empty, and the standard requires an explicit path list suitable for a write allowlist. Untracked files (`Screening_Agent/screening_results.json`, `search_agent/.mas_runs/`, the two gitignored `search_results.json`) also affect git-level emptiness and are unstated.

### M10 — The section's organizing claim is contradicted by its own structure

*   **Source**: style #1
*   **Lines**: 415–417 (preamble)
*   **Finding**: "Every touched file appears once, under the step that first touches it; later steps that touch it again say so" is violated repeatedly: `.github/workflows/ci.yml` has three full headed entries (0.5, 1b.5, 2b.5), `docker-compose.yml` two (1b.4, 2a.1), `golden_run.json` two (1a.17, 2b.4), and `src/api/main.py` is modified in 1b.3 and again in 2a.5 with no note at 1b.3. A reader trusting the stated convention stops searching after a file's first entry. Restate the actual convention or enforce the stated one.

### M11 — Bare decision-number cross-references are unresolvable inside this document

*   **Source**: style #3 + codebase-details #10 (merged)
*   **Lines**: 711 (2a.4), 773–774 (2b.3)
*   **Finding**: "the 3.1 algorithm" / "the 3.1 merge rule" — there is no §3.1 in this document; "3.1" is a decision ID from `concepts_brief.md`, a scheme the design never introduces. The content exists in-document (the "Ingestion and retrieval" upsert step); cite it as "concepts_brief.md decision 3.1" or point at the in-document step.

### M12 — The backlog #14 citation conflicts with the supplied evidence

*   **Source**: style #4
*   **Lines**: 580–581 (1a.13), 680–681 (1c.2)
*   **Finding**: The only description of #14 in the supplied context (`docs/plan_v2.md` §10) is a documentation item ("correct `CLAUDE.md` and `README.md` for the new layout"), not a code-hardcoding item; the brief's decision 5.6 attributes the hardcoded-model fix to findings N9/N10. Verify against `docs/backlog.md` and either correct the number or make #14's contents explicit.

## Nits

### N1 — Repository functions get names, not signatures, breaching the plan's own rule

*   **Source**: impl-readiness #5 — Lines 707–713 vs 416–418. The preamble promises "signatures and schemas only"; 2a.4 lists function names without parameters or return types. One line each closes it.

### N2 — Tooling choices left open; one dependency claim is wrong

*   **Source**: impl-readiness #6 + codebase-details #8 (merged) — Lines 447–452 (0.4), 454–459 (0.5), 481–486 (0.9). Ruff rule selection, pin versions, and Python version (Actions `python-version` / `requires-python`) are unstated. Additionally, "Batch 0 adds `ruff` and `pytest` pins" misdescribes current state: `pytest==9.1.0` is already pinned at `requirements.txt:42`; only ruff is missing.

### N3 — Integration-test and Makefile preconditions unspecified

*   **Source**: impl-readiness #7 — Lines 685–689 (2a.1), 731–738 (2a.7), 461–466 (0.6). No host port mapping for the Postgres service, no source for the test DSN (env var, `.env`, hardcoded default), and no statement of whether `make integration` assumes `make up` + `make migrate` or performs them itself.

### N4 — Chunked-skip rule checks chunk-level columns from a paper-level decision

*   **Source**: impl-readiness #8 — Lines 757–759; data model line 217. `embedding_model`/`chunker_version` live on `chunks` rows; specify which row is consulted (the delete-then-insert invariant makes "any one" safe — say so).

### N5 — The `failed` row of the status-mapping table has no test

*   **Source**: impl-readiness #9 — Lines 788–801, 731–738. 2a.7 asserts 404 and `interrupted`; nothing asserts `failed → current_step="error"` or the `pending/running` partial-payload composition. One assertion in 2a.7 (or a unit test on the composer) covers the wire-contract table completely.

### N6 — "harmless now" is an unverified harmlessness claim

*   **Source**: style #6 — Lines 541–542. Name the evidence ("covered by the 1a smoke run") or drop the parenthetical.

### N7 — "(the real defect behind the old 'sync' claim)" is unresolvable editorial history

*   **Source**: style #7 — Lines 567–568. A fresh reader has never seen the "old 'sync' claim"; the parenthetical adds review archaeology, not instruction. Drop.

### N8 — Temporal miscalibration on the fixture PDFs

*   **Source**: style #8 — Lines 599–600. Page-aware chunking does not exist until 2b; in 1a the fixtures feed v1's FAISS path. Recast as "so that 2b's page-aware chunking and partition test run offline."

### N9 — Register entry V4 is the only deviation without a tag at its implementing step

*   **Source**: style #9 — Lines 715–722 (2a.5). V1/V2/V3/V5 are tagged at 2b.1 and V6 at 1a.6/1a.9; 2a.5 lands V4 with no "(register V4)" tag. Add it.

### N10 — "one optional live smoke run" names no decision criterion

*   **Source**: style #10 — Lines 797–798. The only verification step without a checkable outcome. Name the trigger and pass condition, or mark it explicitly non-gating.

### N11 — Duplicate provenance markers

*   **Source**: style #11 — Lines 805–807. The hidden HTML comment restates the visible "*Drafted with EGM*" line. Drop one, preferably the comment.

### N12 — Minor filler

*   **Source**: style #12 — Lines 415 ("unified"), 442 ("real"), 466 ("subjects" — name them). Tighten.

### N13 — The `.gitignore` step is a no-op with a false rationale

*   **Source**: codebase-details #9 — Lines 475–479 (0.8). The existing ignore patterns are path-anchored (`Screening_Agent/search_results.json`, `extract_agent/search_results.json`) and do not match `tests/fixtures/` or `eval/snapshots/`. No modification is actually needed; correct or drop the step.

### N14 — Makefile `test` label contradicts the Verification Plan

*   **Source**: codebase-details #11 — Lines 464–466 vs 791–793. 0.6 describes `test` as "(unit)" while `make test` also runs the fake e2e and golden-transcript tests under `tests/e2e/` (unmarked, so included by `-m "not integration"`). The 0.6 label is what's wrong.

### N15 — `chunker_version` constant undefined

*   **Source**: codebase-details #12 — Lines 757–759. The constant's name, module, and initial value are nowhere defined; 1a.1's settings include `embedding_model` but not `chunker_version`, yet the skip rule and the "one-constant bump" promise hinge on it.

### N16 — "Prompts moved byte-identical" glosses over runtime interpolation

*   **Source**: codebase-details #13 — Lines 521–526 (1a.5). The screening and extraction user prompts are f-strings built per call (`screening_agent.py:192–211`, `rag_extraction_main.py:140–199`); the mechanism for versioned templates with interpolation (function vs `.format` template) is left to the implementer.

### N17 — Fake embedder algorithm undefined; cosine-vs-inner-product shift unnoted in 2b.4

*   **Source**: codebase-details #14 — Lines 512–519 (1a.4), 776–780 (2b.4). Any deterministic 384-dim function is run-to-run stable, but the choice is an undocumented decision chunk selection depends on; and the FAISS-inner-product → pgvector-cosine change will alter selections — worth naming in 2b.4's regeneration justification alongside V1–V3/V5.

## Verified clean (no finding)

Claims the codebase-details reviewer verified against the source tree: `Orchestration/nodes.py:62` hardcoded model and line 75 `pre_excluded=[]`; `search_agent/new_main.py:16` hardcoded email and the `sys.path` workaround; the module-import-time client at `rag_extraction_main.py:27–33`; the hand-rolled retry loop and semaphore at `screening_agent.py:214–239`; the sync client and tokenized-query fallback in `agent.py:35–86`; `FIELD_QUERIES`/`k=5` and the `%PDF` check; `ResearchResponse` without a `status` field and per-`astream`-step `JOBS` updates; every 1c.1 deletion path exists; `pyproject.toml`, `Makefile`, `.github/workflows/`, `Screening_Agent/conftest.py` correctly marked Create; the Dockerfile CMD and `pdfs_auto` volume; the Batch 0 test-repair details match the actual test file; the batch phasing satisfies the standard's stable-checkpoint requirement.

## Traceability matrix

| Consolidated | Reviewer finding(s) |
| --- | --- |
| B1 | impl-readiness #1 |
| B2 | codebase-details #1 |
| M1 | impl-readiness #2, style #2 |
| M2 | impl-readiness #3 |
| M3 | impl-readiness #4 |
| M4 | codebase-details #2, style #5 |
| M5 | codebase-details #3 |
| M6 | codebase-details #4 |
| M7 | codebase-details #5 |
| M8 | codebase-details #6 |
| M9 | codebase-details #7 |
| M10 | style #1 |
| M11 | style #3, codebase-details #10 |
| M12 | style #4 |
| N1–N5 | impl-readiness #5–#9 |
| N6–N12 | style #6–#12 |
| N13–N17 | codebase-details #8 (merged into N2), #9, #11–#14 |
