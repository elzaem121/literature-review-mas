Status: resolved (2026-11-17 — auto accept: 28 PROPOSE FIX applied; M12 contested; N1, N12 declined; B1 additionally added a `get_repository()` row to the fake-surface table at the author's request)

# Goldfish Annotated Review Report

**Target:** `docs/designs/phase1_foundation.md` (lines 413–808, Detailed Implementation Plan)
**Round:** 1 (Stage 9 — Implementation Readiness)
**Source findings:** `docs/reviews/phase1_foundation_implementation_readiness_report.md`

Categories: 28 PROPOSE FIX · 1 CONTEST (M12) · 2 DECLINE (N1, N12) · 0 ESCALATE.
Elephant verification: reviewer claims behind B2, M4, M7, M8, M9, N2, N13 and the M12 contest were re-checked against the repository before categorization.

## Prioritized Findings & AI Suggestions

### [B1] [`egm-implementation-readiness`] - Severity: Blocker
*   **Affected Scope:** [Lines 749–801](docs/designs/phase1_foundation.md#L749-L801) (2b.1, 2b.4, Verification Plan)
*   **Discrepancy Description:** After commit 2b, the fake e2e (1a.15) and golden-transcript test (1a.17) invoke ingestion, which requires Postgres + pgvector — but the fake surface has no database seam, and the plan keeps both tests in `make test` and CI, which must run with no database.
*   **Rationale:** The implementer must make an architecture decision the plan reserves for itself (fake DB seam vs. Postgres in CI vs. demoting the tests); each option contradicts a stated property.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the contradiction is real. The fix that preserves every stated property (DB-free CI, golden transcript as a CI gate, per-commit smoke) is a fifth fake seam at the repository layer, which 2a.4 already isolates ("keeps SQL out of nodes and API"). Note: the fake-surface table at lines 199–204 (FeatureRange, outside this resolution's range) should gain a matching row in a follow-up edit — flagged for the author.
*   ***Proposed Edit:***
    *   Location: 2a.4 Proposed Changes (line ~712) — append: "Also defines the repository seam: `get_repository()` returns the Postgres implementation on the `local` profile and an in-memory fake on `test` (built in 2b.1); nodes and API call only this seam."
    *   Location: 2b.1 Proposed Changes (line ~760) — append: "`test` profile: an in-memory fake repository (same functions as 2a.4; retrieval is brute-force cosine over the fake embedder's vectors) backs the fake e2e and golden-transcript tests, which therefore stay in `make test` and CI with no Postgres."
    *   Location: Verification Plan, Unit Tests bullet (line ~791) — append: "(post-2b, ingestion runs against the in-memory fake repository)".

### [B2] [`egm-codebase-details`] - Severity: Blocker
*   **Affected Scope:** [Lines 506–510](docs/designs/phase1_foundation.md#L506-L510) (1a.3); knock-on at 1a.12, 1a.13, 1a.15
*   **Discrepancy Description:** 1a.3 removes root `tracing.py`, but it exports `traceable_stage`, `root_trace`, `tracing_enabled` besides `maybe_wrap_openai`, imported at module level by `Backend/main.py:10`, `Orchestration/nodes.py:12`, `extract_agent/document_processing_node.py:11`, `extract_agent/rag_extraction_main.py:13` — files still at v1 paths in commit 1a whose step entries do not authorize the import rewrite (`Backend/main.py` appears in no 1a step). The graph cannot compile; the 1a.15 per-commit check fails.
*   **Rationale:** Zero-Decision Rule and write-allowlist violation; the plan's own green check is unsatisfiable at commit 1a.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified: `grep` confirms all four exports and six import sites (the two in `search_agent/agent.py` and `Screening_Agent/screening_agent.py` disappear anyway in 1a.6/1a.9 when those files switch to `get_llm`). The four remaining sites must be rewritten in the same commit, and `Backend/main.py` must be named as a touched file.
*   ***Proposed Edit:***
    *   Location: 1a.3 Proposed Changes (lines 509–510) — replace with: "All four public helpers (`maybe_wrap_openai`, `traceable_stage`, `root_trace`, `tracing_enabled`) moved unchanged; the four remaining v1-path imports — `Backend/main.py` (first touched here; moved in 1b), `Orchestration/nodes.py`, `extract_agent/document_processing_node.py`, `extract_agent/rag_extraction_main.py` — are rewritten to `from src.llm.tracing import ...` in this commit; the root module is then removed so only one import path exists. (`search_agent/agent.py` and `Screening_Agent/screening_agent.py` lose their tracing imports via 1a.6/1a.9.)"

### [M1] [`egm-implementation-readiness` + `egm-style`] - Severity: Major
*   **Affected Scope:** [Lines 583–588](docs/designs/phase1_foundation.md#L583-L588) (1a.14), 512–519 (1a.4), 439–445 (0.3)
*   **Discrepancy Description:** 1a.14 requires "the four buckets via sentinels," but the fake defines only two sentinels plus a canned `include` — no mechanism produces `failed` (v1 populates it only on a raised exception). The fixture roster (paper count, sentinel assignment, DOI pair) is unspecified yet determines the committed golden transcript.
*   **Rationale:** The claim outruns the specified mechanism; two implementers would commit different golden baselines.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on both counts; four buckets plus a both-included DOI pair needs five papers.
*   ***Proposed Edit:***
    *   Location: 1a.4 Proposed Changes (line ~516) — after `[FAKE:UNCERTAIN]` add: "`[FAKE:FAIL]` (the registry callable raises a simulated API error, populating `failed_papers` exactly as a v1 LLM failure did)".
    *   Location: 0.3 Proposed Changes (lines 442–445) — replace "3–5 papers … mixed screening buckets" with: "exactly 5 papers: P1 plain abstract (include), P2 `[FAKE:EXCLUDE]`, P3 `[FAKE:UNCERTAIN]`, P4 `[FAKE:FAIL]`, P5 plain abstract (include); P1 and P5 are the two OpenAlex records sharing one DOI, both included so the G1 upsert merge is exercised downstream."

### [M2] [`egm-implementation-readiness`] - Severity: Major
*   **Affected Scope:** [Lines 602–608](docs/designs/phase1_foundation.md#L602-L608) (1a.17), 776–780 (2b.4)
*   **Discrepancy Description:** The golden-transcript diff leaves open: allow-list representation, volatile-field normalization, and the post-regeneration allow-list contents.
*   **Rationale:** The design's central drift guard would be built differently by different implementers.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; all three are specifiable in a few lines.
*   ***Proposed Edit:***
    *   Location: 1a.17 Proposed Changes (line ~607) — append: "Mechanics: before diffing, volatile fields (run/job ids, timestamps, filesystem paths) are replaced with fixed placeholders; the allow-list is a list of JSON-path prefixes per register entry, defined beside the test; any difference outside an allowed prefix fails."
    *   Location: 2b.4 Proposed Changes (line ~780) — replace "the allow-list in the test shrinks accordingly" with: "the allow-list empties: V1–V3/V5 are baked into the regenerated baseline, V6 predates the original capture, and V4 is API-layer state invisible in graph-level output."

### [M3] [`egm-implementation-readiness`] - Severity: Major
*   **Affected Scope:** [Lines 691–697](docs/designs/phase1_foundation.md#L691-L697) (2a.2), 699–705 (2a.3)
*   **Discrepancy Description:** 2a.2 defers to a column table headed "key ones" — PK types, FK `ON DELETE`, chunk uniqueness, timestamps, and nullability are undecided.
*   **Rationale:** The standard requires DDL-level schema decisions; the brief promised them.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Proposed defaults follow the design's own conventions (uuid only where it is the public `job_id`).
*   ***Proposed Edit:***
    *   Location: 2a.2 Proposed Changes (line ~697) — append: "Completing the table to DDL level: PKs — `runs.id` uuid, all other tables integer identity. FKs — `chunks.paper_id` ON DELETE CASCADE; all other FKs RESTRICT. Uniques — `chunks (paper_id, ordinal)`, `papers.openalex_id`, `papers.doi` (nullable unique). `papers` gains `created_at`/`updated_at`. Columns not listed in the Technical Plan's table plus these do not exist."

### [M4] [`egm-codebase-details` + `egm-style`] - Severity: Major
*   **Affected Scope:** [Lines 490–496](docs/designs/phase1_foundation.md#L490-L496) (1a.1), 610–614 (1a.18), 685–689 (2a.1), 782–786 (2b.5)
*   **Discrepancy Description:** `openalex_email` is required and validated at startup, but nothing adds `OPENALEX_EMAIL` (or `PROFILE`) to the compose environment or the CI compose job, so the `/health` check fails. 1a.1 vs 1a.18 also contradict on when `DATABASE_URL` exists.
*   **Rationale:** Verified: the compose backend env today passes only `OLLAMA_BASE_URL` + LangSmith vars; the plan's additions never include the required setting.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on both counts.
*   ***Proposed Edit:***
    *   Location: 1a.1 Proposed Changes (line ~495) — change "`database_url`" to "`database_url` (optional until 2a — no Postgres exists before it; required from 2a)".
    *   Location: 1a.18 Proposed Changes (lines 613–614) — replace "2a adds `DATABASE_URL`" with: "lists `DATABASE_URL` commented out from the start; 2a uncomments it with the compose default."
    *   Location: 2a.1 Proposed Changes (line ~688) — append: "backend env also gains `OPENALEX_EMAIL` and `PROFILE` passthrough."
    *   Location: 2b.5 Proposed Changes (line ~786) — change "dummy `OLLAMA_BASE_URL`" to "dummy `OLLAMA_BASE_URL` and dummy `OPENALEX_EMAIL` (e.g. `ci@example.invalid`)".

### [M5] [`egm-codebase-details`] - Severity: Major
*   **Affected Scope:** [Lines 439–445](docs/designs/phase1_foundation.md#L439-L445) (0.3), 512–518 (1a.4)
*   **Discrepancy Description:** The stub OpenAlex client sits at a seam that returns raw OpenAlex work dicts (`abstract_inverted_index`, `primary_location`, …), but the 0.3 fixture is in the formatted `{"papers": [...]}` shape, which a screening test also consumes. One fixture cannot feed both.
*   **Rationale:** The seam location and fixture shape are a design choice left to the implementer.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Stubbing at `execute_retrieval` keeps the agent's formatting loop exercised by the fake e2e; two shape-specific fixtures derived from the same 5 papers resolve the conflict.
*   ***Proposed Edit:***
    *   Location: 0.3 header and Proposed Changes (lines 439–445) — extend the step to create two files: `tests/fixtures/openalex_works.json` (the same 5 papers as raw OpenAlex work dicts — `abstract_inverted_index`, `authorships`, `primary_location`, `best_oa_location` — feeding the stub) and `tests/fixtures/search_results.json` (the formatted shape, feeding the screening tests).
    *   Location: 1a.4 Proposed Changes (line ~518) — replace "stub OpenAlex client returning 0.3's fixture" with: "stub OpenAlex client replacing `OpenAlexClient.execute_retrieval`, returning raw work dicts from `tests/fixtures/openalex_works.json` so the agent's formatting loop runs unmodified."

### [M6] [`egm-codebase-details`] - Severity: Major
*   **Affected Scope:** [Lines 528–535](docs/designs/phase1_foundation.md#L528-L535) (1a.6); feeds 2a.4, 2b.3
*   **Discrepancy Description:** `pdf_url`'s source expression and `openalex_id` normalization (full URL vs bare ID) are unspecified, yet `openalex_id` is a unique column and one leg of the upsert SELECT, and register V1 depends on the pdf-url ordering.
*   **Rationale:** Verified: `api_client.execute_retrieval` computes `primary_loc.get("pdf_url") or best_oa.get("pdf_url")` and discards it; OpenAlex `id` is a full URL.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; both decisions are one clause each.
*   ***Proposed Edit:***
    *   Location: 1a.6 Proposed Changes (line ~534) — append: "`pdf_url` = `primary_location.pdf_url or best_oa_location.pdf_url` (the expression `execute_retrieval` already computes); `openalex_id` stored bare (strip the `https://openalex.org/` prefix at formatting time) — the form `papers.openalex_id` uses."

### [M7] [`egm-codebase-details`] - Severity: Major
*   **Affected Scope:** [Lines 556–561](docs/designs/phase1_foundation.md#L556-L561) (1a.10)
*   **Discrepancy Description:** "Consumers (`Backend/schemas.py`, `ui_app.py`) updated in the same commit" — but neither file references `ResearchPaper`: `Backend/schemas.py` holds buckets as `List[Dict[str, Any]]`, `ui_app.py` reads raw JSON.
*   **Rationale:** Verified against `Backend/schemas.py`. The directed update has no definition; an implementer either guesses or distrusts the plan.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the honest statement is that no consumer change is needed.
*   ***Proposed Edit:***
    *   Location: 1a.10 Proposed Changes (lines 560–561) — replace "Consumers (`Backend/schemas.py`, `ui_app.py`) updated in the same commit." with: "No consumer edits needed: `Backend/schemas.py` carries papers as `List[Dict[str, Any]]` and `ui_app.py` reads raw JSON, so the added optional fields flow through unchanged."

### [M8] [`egm-codebase-details`] - Severity: Major
*   **Affected Scope:** [Lines 422–437](docs/designs/phase1_foundation.md#L422-L437) (0.1, 0.2)
*   **Discrepancy Description:** "Fix the duplicate `screening_schemas` import" does not say which import becomes canonical, and 0.2's shim does not say which directory it inserts — the wrong choice reproduces the dual-identity bug being fixed.
*   **Rationale:** Verified: the test imports flat (`from screening_schemas import ...`) while `screening_agent.py:11` imports `Screening_Agent.screening_schemas`; inserting `Screening_Agent/` on the path keeps both identities importable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Package-qualified test imports from the repo root give one module identity; 0.4's `pythonpath = ["."]` already makes repo-root collection work, so 0.2's shim is unnecessary and its dangerous half (inserting the package dir) is avoided entirely.
*   ***Proposed Edit:***
    *   Location: 0.1 Proposed Changes (line ~427) — replace "fix the duplicate `screening_schemas` import so Pydantic sees one `ResearchPaper` class" with: "rewrite the test's flat imports to the package-qualified `Screening_Agent.screening_agent` / `Screening_Agent.screening_schemas` — the identity `screening_agent.py` itself uses — so Pydantic sees one `ResearchPaper` class".
    *   Location: 0.2 (lines 433–437) — replace the step body with: "Dropped: 0.4's `pythonpath = ["."]` already makes repo-root collection resolve the package-qualified imports; a shim inserting `Screening_Agent/` would re-create the dual module identity 0.1 removes." (keep the heading as a tombstone so numbering is stable).

### [M9] [`egm-codebase-details`] - Severity: Major
*   **Affected Scope:** [Lines 667–676](docs/designs/phase1_foundation.md#L667-L676) (1c.1)
*   **Discrepancy Description:** "the now-empty v1 directories" is false as written: tracked leftovers (`Backend/__init__.py`, `Orchestration/__init__.py`, `search_agent/__init__.py`, `extract_agent/.gitignore`) are unnamed, and untracked leftovers are unstated.
*   **Rationale:** Verified: those four tracked files exist (`Screening_Agent/` and `extract_agent/` have no `__init__.py`). The standard requires an explicit deletion path list.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: 1c.1 Proposed Changes (line ~675) — replace "the now-empty v1 directories" with: "the remaining tracked leftovers `Backend/__init__.py`, `Orchestration/__init__.py`, `search_agent/__init__.py`, `extract_agent/.gitignore`; then the emptied `Backend/`, `Orchestration/`, `search_agent/`, `Screening_Agent/`, `extract_agent/` directories (untracked leftovers — `Screening_Agent/screening_results.json`, `search_agent/.mas_runs/`, the two gitignored `search_results.json` — are deleted locally; they were never tracked)".

### [M10] [`egm-style`] - Severity: Major
*   **Affected Scope:** [Lines 415–417](docs/designs/phase1_foundation.md#L415-L417) (preamble)
*   **Discrepancy Description:** "Every touched file appears once …; later steps that touch it again say so" is contradicted by `ci.yml` (three entries), `docker-compose.yml` (two), `golden_run.json` (two), and `src/api/main.py` (1b.3 + 2a.5, no note).
*   **Rationale:** A reader trusting the stated convention stops searching after a file's first entry.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the actual convention (first entry forward-references later touches, later touches get their own entries) is fine — the text just misstates it. 1b.3's missing forward reference to 2a.5 also needs the one-word fix.
*   ***Proposed Edit:***
    *   Location: Lines 416–417 — replace "Every touched file appears once, under the step that first touches it; later steps that touch it again say so." with: "A file's first entry sits under the step that first touches it and names the later steps that touch it again; those later touches get entries of their own."
    *   Location: 1b.3 heading (line 647) — change "(Modify — within the move)" to "(Modify — within the move; touched again in 2a.5)".

### [M11] [`egm-style` + `egm-codebase-details`] - Severity: Major
*   **Affected Scope:** [Line 711](docs/designs/phase1_foundation.md#L711) (2a.4), [lines 773–774](docs/designs/phase1_foundation.md#L773-L774) (2b.3)
*   **Discrepancy Description:** "the 3.1 algorithm" / "the 3.1 merge rule" — no §3.1 exists in this document; 3.1 is a `concepts_brief.md` decision ID, a scheme the design never introduces.
*   **Rationale:** Unresolvable cross-reference for the document's declared fresh-reader audience.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the content lives in-document under "Ingestion and retrieval" step 1.
*   ***Proposed Edit:***
    *   Location: Line 711 — replace "paper upsert (3.1 algorithm — used from 2b)" with "paper upsert (the Technical Plan's 'Ingestion and retrieval' step 1; concepts_brief.md decision 3.1 — used from 2b)".
    *   Location: Lines 773–774 — replace "under the 3.1 merge rule" with "under the upsert merge rule ('Ingestion and retrieval' step 1; concepts_brief.md decision 3.1)".

### [M12] [`egm-style`] - Severity: Major
*   **Affected Scope:** [Lines 580–581](docs/designs/phase1_foundation.md#L580-L581) (1a.13), 680–681 (1c.2)
*   **Discrepancy Description:** The claim that replacing the hardcoded model "closes backlog #14's second item" conflicts with the supplied evidence, which describes #14 as a documentation item.
*   **Rationale:** `docs/backlog.md` was not in the reviewer's supplied context; against `plan_v2.md` alone the citation looked miscalibrated.
*   ***AI Suggestion:*** CONTEST
*   ***Justification:*** `docs/backlog.md` item 14 (readable in the repository) lists two clauses; the second is: "`README.md:240-241` says `SCREENING_MODEL` overrides the screening model, but `Orchestration/nodes.py:62` hardcodes it." 1a.13's settings replacement closes exactly that clause, and 1c.2's doc rewrite closes the first — the design's two citations ("second item" at 1a.13, "doc items" at 1c.2) map onto the backlog entry as written. The reviewer's conclusion came from not consulting `docs/backlog.md`, which its own report acknowledges.
*   ***Proposed Edit:*** None (contested).

### [N1] [`egm-implementation-readiness`] - Severity: Nit
*   **Affected Scope:** [Lines 707–713](docs/designs/phase1_foundation.md#L707-L713) (2a.4)
*   **Discrepancy Description:** Repository functions listed by name only; the preamble promises "signatures and schemas only."
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Parameters and return types are derivable from decisions already in the document (the reviewer says so); adding seven full signatures lengthens the plan without removing a real decision. Recorded, not fixed.

### [N2] [`egm-implementation-readiness` + `egm-codebase-details`] - Severity: Nit
*   **Affected Scope:** [Lines 447–452](docs/designs/phase1_foundation.md#L447-L452) (0.4), 481–486 (0.9)
*   **Discrepancy Description:** Ruff rule set, pin versions, and Python version unstated; and "Batch 0 adds `ruff` and `pytest` pins" is wrong — `pytest==9.1.0` is already pinned (`requirements.txt:42`).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** The false claim is worth one line; the Python-version single source prevents CI/Docker/pyproject drift.
*   ***Proposed Edit:***
    *   Location: 0.9 Proposed Changes (line ~484) — replace "Batch 0 adds `ruff` and `pytest` pins." with "Batch 0 adds a `ruff` pin (`pytest==9.1.0` is already pinned)."
    *   Location: 0.4 Proposed Changes (line ~452) — append: "`requires-python` matches the Dockerfile's Python base; CI's `python-version` uses the same value."

### [N3] [`egm-implementation-readiness`] - Severity: Nit
*   **Affected Scope:** [Lines 461–466](docs/designs/phase1_foundation.md#L461-L466) (0.6), 685–689 (2a.1), 731–738 (2a.7)
*   **Discrepancy Description:** No Postgres host port, no test-DSN source, no statement whether `make integration` assumes `make up`/`make migrate`.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Three short clauses save a fresh session a stumble.
*   ***Proposed Edit:***
    *   Location: 2a.1 Proposed Changes (line ~688) — append: "Postgres published on host port 5432."
    *   Location: 0.6 Proposed Changes (line ~465) — append: "`integration` assumes `make up` and `make migrate` have run; the test DSN comes from `DATABASE_URL`, defaulting to the compose service on localhost:5432."

### [N4] [`egm-implementation-readiness`] - Severity: Nit
*   **Affected Scope:** [Lines 757–759](docs/designs/phase1_foundation.md#L757-L759) (2b.1)
*   **Discrepancy Description:** The chunked-skip rule reads chunk-level columns (`embedding_model`, `chunker_version`) without saying which chunk row is consulted.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: 2b.1, chunking bullet (line ~759) — append: "(checked on any single chunk row of the paper — uniform by the delete-then-insert invariant)".

### [N5] [`egm-implementation-readiness`] - Severity: Nit
*   **Affected Scope:** [Lines 731–738](docs/designs/phase1_foundation.md#L731-L738) (2a.7)
*   **Discrepancy Description:** The `failed → current_step="error"` mapping and the `pending/running` partial-payload composition are never asserted by any test.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: 2a.7 Proposed Changes (line ~738) — append: "also asserts the `failed → current_step=\"error\"` mapping via one forced-failure run, completing coverage of the status-mapping table."

### [N6] [`egm-style`] - Severity: Nit
*   **Affected Scope:** [Lines 541–542](docs/designs/phase1_foundation.md#L541-L542) (1a.7)
*   **Discrepancy Description:** "harmless now" asserts harmlessness with no named evidence.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: Lines 541–542 — replace "(obsolete once 1b moves it, harmless now)" with "(obsolete once 1b moves it; the 1a fake-e2e smoke covers the removal)".

### [N7] [`egm-style`] - Severity: Nit
*   **Affected Scope:** [Lines 567–568](docs/designs/phase1_foundation.md#L567-L568) (1a.11)
*   **Discrepancy Description:** "(the real defect behind the old 'sync' claim)" references editorial history a fresh reader has never seen.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: Lines 567–568 — delete the parenthetical "(the real defect behind the old \"sync\" claim)".

### [N8] [`egm-style`] - Severity: Nit
*   **Affected Scope:** [Lines 599–600](docs/designs/phase1_foundation.md#L599-L600) (1a.16)
*   **Discrepancy Description:** Claims the PDFs exercise page-aware chunking in 1a, but that does not exist until 2b.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: Lines 599–600 — replace "so page-aware chunking and the partition invariant are exercised offline" with "so that 2b's page-aware chunking and partition test run offline (in 1a they feed v1's FAISS path)".

### [N9] [`egm-style`] - Severity: Nit
*   **Affected Scope:** [Lines 715–722](docs/designs/phase1_foundation.md#L715-L722) (2a.5)
*   **Discrepancy Description:** V4 is the only register entry with no tag at its implementing step.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: 2a.5 Proposed Changes (line ~718) — after "`JOBS` dict removed." insert "(register V4)".

### [N10] [`egm-style`] - Severity: Nit
*   **Affected Scope:** [Lines 797–798](docs/designs/phase1_foundation.md#L797-L798) (Verification Plan)
*   **Discrepancy Description:** The "optional" live smoke run has no trigger or pass condition.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: Lines 797–798 — replace "one optional live smoke run with real Ollama + MiniLM" with "one non-gating live smoke run with real Ollama + MiniLM (recommended before tagging; exit criteria do not depend on it)".

### [N11] [`egm-style`] - Severity: Nit
*   **Affected Scope:** [Lines 805–807](docs/designs/phase1_foundation.md#L805-L807)
*   **Discrepancy Description:** The hidden HTML provenance comment duplicates the visible "*Drafted with EGM*" line.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: Line 805 — delete the HTML comment line.

### [N12] [`egm-style`] - Severity: Nit
*   **Affected Scope:** [Lines 415, 442, 466](docs/designs/phase1_foundation.md#L415)
*   **Discrepancy Description:** Minor filler ("unified", "real", vague "subjects").
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Pure word-level style with no effect on implementability; line 466's "subjects" is additionally superseded by N3's rewrite of 0.6. Recorded, not fixed.

### [N13] [`egm-codebase-details`] - Severity: Nit
*   **Affected Scope:** [Lines 475–479](docs/designs/phase1_foundation.md#L475-L479) (0.8)
*   **Discrepancy Description:** The existing ignore patterns are path-anchored and do not match `tests/fixtures/` or `eval/snapshots/`; the step is a no-op with a false rationale.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified against `.gitignore:36–38`. Recast as a check, not an edit.
*   ***Proposed Edit:***
    *   Location: 0.8 Proposed Changes (lines 478–479) — replace with: "Verify (no expected edit): the existing path-anchored ignores (`Screening_Agent/…`, `extract_agent/…`) do not match `tests/fixtures/` or `eval/snapshots/`; the step exists to confirm the new fixture paths are tracked, and `git add` failing loudly is the backstop."

### [N14] [`egm-codebase-details`] - Severity: Nit
*   **Affected Scope:** [Lines 464–466](docs/designs/phase1_foundation.md#L464-L466) (0.6) vs 791–793
*   **Discrepancy Description:** 0.6 labels `test` "(unit)" while `make test` also runs the fake e2e and golden-transcript tests.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: Line 465 — change "`test` (unit)" to "`test` (unit + fake e2e)".

### [N15] [`egm-codebase-details`] - Severity: Nit
*   **Affected Scope:** [Lines 757–759](docs/designs/phase1_foundation.md#L757-L759) (2b.1)
*   **Discrepancy Description:** The `chunker_version` constant's name, module, and initial value are undefined despite carrying the "one-constant bump" promise.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: 2b.1, chunking bullet (line ~759) — append: "`CHUNKER_VERSION = \"v1\"` is defined in `chunking.py` and written to every chunk row."

### [N16] [`egm-codebase-details`] - Severity: Nit
*   **Affected Scope:** [Lines 521–526](docs/designs/phase1_foundation.md#L521-L526) (1a.5)
*   **Discrepancy Description:** "Moved byte-identical" glosses over the screening/extraction user prompts being per-call f-strings; the template mechanism is unspecified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: 1a.5 Proposed Changes (line ~525) — append: "Interpolated v1 prompts become `.format` templates with a per-role `render_*` function; rendered output is byte-identical to v1's f-strings."

### [N17] [`egm-codebase-details`] - Severity: Nit
*   **Affected Scope:** [Lines 512–519](docs/designs/phase1_foundation.md#L512-L519) (1a.4), 776–780 (2b.4)
*   **Discrepancy Description:** The fake embedder's algorithm is undefined (golden-transcript chunk selection depends on it), and the FAISS→pgvector metric change is unnamed in 2b.4's regeneration justification.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: 1a.4 Proposed Changes (line ~517) — replace "deterministic 384-dim fake embedder" with "deterministic 384-dim fake embedder (vector seeded from the SHA-256 of the input text, L2-normalized)".
    *   Location: 2b.4 Proposed Changes (lines 779–780) — change "with register entries V1–V3, V5 as the documented justification" to "with register entries V1–V3, V5 and the FAISS→pgvector retrieval swap as the documented justification".
