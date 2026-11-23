# Phase 2a — Evaluation baseline

*   **Author:** Mohamed Elsayed
*   **Status:** Proposed
*   **Date:** 2026-11-23

--------------------------------------------------------------------------------

## Overview

Phase 2a builds the evaluation harness and measures the baseline: the Phase 1
system with the v1 models (`qwen2.5-coder:7b` for every LLM role,
`all-MiniLM-L6-v2` for embeddings). It produces four things:

1.  **A gold set (v0).** 60 papers across three test topics. Each paper has
    yes / no / not stated answers to a few checks, judged on its title and
    abstract only. Six of the papers also have extraction gold: the fields the
    paper reports, each with a page and a short quote.
2.  **A harness.** One command runs screening, search, retrieval and extraction
    on frozen inputs, saves every model output, and scores the outputs against
    the gold set.
3.  **Baseline numbers.** A results file in `eval/results/` with screening
    recall, search precision@10, retrieval recall and extraction field status,
    plus how much screening changes between two identical runs.
4.  **An error analysis.** The baseline's wrong outputs, grouped by cause for each
    agent, with examples. This is the main input to the Phase 2b agent review.

Phase 2a changes no pipeline behaviour, with one possible exception: if the
truncation check shows that Ollama cuts extraction prompts short, the context
length is set explicitly for every run, including the baseline. The model
benchmark, the search judge and the faithfulness judge are Phase 2b work. They
use this harness, so this design also writes down the rule Phase 2b uses to
choose models.

The three test topics are test cases only; the system stays domain-agnostic:

1.  Social media and adolescents (social science).
2.  How LLM-based multi-agent systems are evaluated (computer science).
3.  Mobile money and household welfare in Sub-Saharan Africa (economics).

How these choices were reached is recorded in `docs/eval_notes.md` (brainstorm
record) and `concepts_brief.md` (Goldfish review). This document is the source
of truth for the evaluation from now on.

## The Problem

*   **No quality number in this repository can be trusted.** The v1 README
    claims precision@10 above 0.85 and 90–95% accuracy, but no data, script or
    labels stand behind these numbers. Phase 2b changes the agents, and each
    change has to show an improvement over a baseline (`plan_v2.md`, section 8
    and working rule 6). Without a measured baseline, no Phase 2b change can be
    judged.
*   **Inputs move.** OpenAlex's index changes over time, and query expansion runs
    at temperature 0.1, so two runs of the same search return different papers.
    A score is only comparable with another score if both were computed on the
    same frozen inputs.
*   **One person, about two hours, no domain expertise for two of the three
    topics.** The labeler built an LLM-based multi-agent system, so they can
    judge topic 2. They are not an expert in topics 1 and 3. Labels must
    therefore be checks that a careful non-expert can answer from the title and
    abstract, and most labels have to come from a model, with a human sample as
    the independent check.
*   **Several failure modes would quietly corrupt the numbers if not designed
    out:**
    *   A model that answers `uncertain` loses the paper: ingestion reads only
        `included_papers` (backlog #37).
    *   A failed call caused by infrastructure (Ollama down, model not pulled)
        would look like a wrong answer.
    *   Ollama may cut an extraction prompt short without an error.
    *   A gold quote taken from a different text extraction than the
        pipeline's would never match a retrieved chunk.
*   **v1 extraction output has no field status.** `ExtractedPaperInfo` holds eight
    free-text fields, and absence is written as phrases such as "not specified".
    The Phase 2b exit compares field status against the baseline, so the
    baseline needs a defined way to read a status out of v1's text.

## Goals

The Phase 2a exit checks each goal with a script result or a committed file.

*   **G1 — Gold screening set.**
    *   **Contents:** 60 papers, 20 per topic. Each topic's set contains its
        frozen baseline top-10 search results.
    *   **Labels:** every paper has an answer per check, a derived decision, and
        a label source (`human`, `model` or `model_verified`).
    *   **Mix:** each topic has 8–12 gold includes and at most 4 gold
        `uncertain`, or the gold file records why not (see Open Question 3).
    *   **Check:** a validation script confirms the counts, re-derives every
        decision from its check answers, and finds no unlabeled paper and no
        duplicate study.
*   **G2 — Human check on the model labels.**
    *   **Sample:** the human blind-labels about 20 papers, including borderline
        ones.
    *   **Reporting:** agreement is reported as counts per topic and check.
    *   **Escalation:** the escalation rule has been applied, and every label it
        changed is marked `model_verified`.
*   **G3 — Extraction gold.**
    *   **Papers:** 6 papers, 3 from topic 1 and 3 from topic 2.
    *   **Fields:** only fields the paper reports (`found`), each with a 1-based
        PDF page index and a one-sentence quote.
    *   **Check:** a script finds every quote on its stated page in the frozen
        PyMuPDF text (kept in the local eval data folder), after whitespace
    normalization.
*   **G4 — One command, saved outputs, separate scoring.**
    *   **Run:** one command runs the eval for a given configuration and writes
        one results file to `eval/results/`.
    *   **Provenance:** the file records the models, prompt versions, context
        length, embedding model, chunker version, retrieval top-k, gold-set
        version and snapshot dates.
    *   **Saved outputs:** every model output is saved per paper in the local
        eval data folder, which is backed up to a separate private GitHub
        repository.
    *   **Scoring:** scoring reads the saved outputs. A corrected gold label is
        re-scored without re-running a model, and Phase 2b can judge the saved
        baseline extraction outputs, on any machine that has the data folder.
*   **G5 — Failures are not scored as answers.**
    *   **Before the run:** the run stops with a clear error if a configured
        model is unreachable.
    *   **Structured-output failures:** these are counted and reported
        separately.
    *   **Infrastructure errors:** a run that hits an infrastructure error is
        marked incomplete and is not scored.
*   **G6 — Baseline numbers.** The committed results file reports:
    *   **Screening, per topic and pooled:** the gold × model table, include
        recall, exclude recall and hard include↔exclude errors, as counts and
        rates. A model `uncertain` and a failed call count as include misses.
        Gold `uncertain` papers are reported as counts only.
    *   **Run-to-run noise:** the number of screening decisions that flip
        between two identical baseline runs.
    *   **Search:** precision@10 per topic, where only gold includes count as
        relevant.
    *   **Retrieval:** recall@5 per extraction field: whether the gold quote is
        in the retrieved chunks.
    *   **Extraction field status:** the share of gold `found` fields that the
        baseline reports as found, using a fixed mapping from v1's text.
*   **G7 — Truncation checked.** One logged run records the prompt token counts
    of extraction calls. Either it shows that Ollama does not truncate, or the
    context length is set explicitly for every run and the truncation is a
    backlog item.
*   **G8 — Error analysis.**
    *   **Contents:** wrong baseline outputs for search, screening, retrieval and
        extraction, grouped by cause, with at least one example per group.
    *   **Backlog #37:** the number of gold includes that the baseline marks
        `uncertain`.
*   **G9 — Latency budget.** The per-run latency budget (`plan_v2.md`,
    section 11) is recorded from the measured baseline (see Open Question 4).
*   **G10 — Selection rule for Phase 2b.** The paired model-selection rule is
    written down here, with its gates, before any Phase 2b benchmark run.

## Non-Goals

*   **No model benchmark and no model decision record.** These are Phase 2b work
    and use this harness (author decision, 2026-11-23).
*   **No judge in Phase 2a.** The search judge and the faithfulness judge,
    including their calibration, are Phase 2b tasks. The Phase 2b faithfulness
    judge scores the saved baseline extraction outputs after the fact, so a
    before/after number still exists.
*   **No pipeline behaviour changes.** The screening prompt, the search logic, the
    v1 extraction schema and chunking stay as they are. The only allowed change
    is an explicit context length if G7 finds truncation.
*   **No `missing` vs. `not_reported` distinction in the baseline.** v1 cannot
    express it; the baseline reports found / not found only.
*   **No `not_reported` extraction gold.** Absence claims need a full read of the
    paper and are left out of v0.
*   **No router, chat or summary evaluation.** These come in Phase 3.
*   **No merging of duplicate studies in the pipeline.** Duplicates are removed
    only when the gold set is built.
*   **No LangSmith requirement.** The local results file is the record; a
    LangSmith upload is optional.
*   **No live evals in CI.** CI runs the harness's scoring logic only, with the
    fake LLM and fixtures.
*   **None of the "Later" items** in `docs/eval_notes.md`: double labeling,
    weighted agreement, lenient precision, and the others listed there.

## Open Questions

None open. The four questions raised while drafting were decided by the author
(2026-11-23) and are recorded in the Technical Plan:

*   **Frozen inputs:** gold files and results in git; page text, PDFs and raw
    outputs in a local data folder backed up to a private repository
    (Technical Plan, "Where data lives").
*   **Harness shape:** a contract owned by the harness, with one adapter per
    pipeline version ("Harness").
*   **Top-10 and sample mix:** a separate search set and screening set per topic
    ("Gold set").
*   **Latency budget:** built from the harness's stage timings; one end-to-end
    smoke run is timed for reporting only ("Latency budget").

## Critical User Journeys (CUJs)

### CUJ 1: Build the gold set

*   **Given**: the three topic configs are written, Ollama serves the v1 search
    model, and OpenAlex is reachable.
*   **When**: the author runs the gold-set build steps in order: freeze search,
    build the candidate pool, model labeling, sample selection, blind labeling,
    escalation, and extraction gold.
*   **Then**: the following are in `eval/`:
    *   `eval/gold/v0/` holds the frozen search output, the candidate pool, the
        screening gold and the extraction gold. The validation script passes.
    *   Page text and PDFs are in the local eval data folder, and the data
        folder has been synced to its private backup repository.
    *   The labeling provenance (model, Claude Code version, prompt) is
        committed.
    *   The agreement counts per topic and check are recorded.

### CUJ 2: Measure the baseline

*   **Given**: the gold set v0 is committed, and Ollama serves the v1 models.
*   **When**: the author runs one command with the Phase 1 adapter and the v1
    settings.
*   **Then**: the command:
    *   checks that every model is reachable;
    *   screens the 60 screening-set papers twice;
    *   retrieves and extracts the 6 extraction-gold papers;
    *   saves every output under `outputs/<run_id>/` in the local eval data
        folder;
    *   writes `eval/results/<run_id>.json` with the scores, timings and
        provenance.

    The author then runs the sync step, which pushes the data folder to its
    private backup repository.

    A rerun of only the scoring step on the saved outputs gives the same file.

### CUJ 3: Phase 2b compares a change against the baseline

*   **Given**: the baseline results file is committed, the baseline outputs are
    in the eval data folder (or restored from its backup), and a Phase 2b change
    exists. The change is either a new adapter (new pipeline code) or new
    model settings.
*   **When**: the author runs the same command with the new adapter or settings.
*   **Then**: the new results file is scored by the same scoring code against the
    same gold set. The paired selection rule (below) compares it with the
    baseline paper by paper.

## Technical Plan (Architecture)

### Overview of the parts

```text
 eval/topics/*.json ──► render criteria ──► screener input ─┐
        │                                                     │
        └──► labeling prompt ──► Claude (fresh context/paper) │
                                     │                        │
 OpenAlex ──► search adapter ──► eval/gold/v0/ search+pool   │
                                     │                        │
                      candidate pool, dedup                   │
                                     │                        │
                         model labels ──► human blind sample  │
                                     │        └─► escalation  │
                                     ▼                        │
                              eval/gold/v0/                   │
                                     │                        │
 run command ──► precheck ──► adapter (phase1) ◄──────────────┘
                                │   screen ×2 · retrieve · extract
                                ▼
                <data folder>/outputs/<run_id>/  (raw records)
                                │                 └─► sync ─► private backup repo
                             scoring ──► eval/results/<run_id>.json
```

The harness is Python code under `eval/`, next to `src/` as plan section 5.4
says. It imports from `src/`; nothing in `src/` imports from `eval/`. Scoring
never imports `src/`, so it stays the same across pipeline versions.

### Topic configs: one source for labeler and screener

Each topic is one file, `eval/topics/<topic>.json`. It holds:

*   **Identity:** a topic id and the research question.
*   **`min_year`:** 2020 for all three topics.
*   **The checks:** each check has an id (`c1`, `c2`, ...), the question, and a
    "yes" statement and a "no" statement.

The checks are the ones accepted in `docs/eval_notes.md`:

*   topic 1: five checks
*   topic 2: four checks
*   topic 3: five checks

Two renderings are generated from this file, both by harness code:

*   **Screener input:**
    *   `inclusion_criteria`: one line per check, the "yes" statement.
    *   `exclusion_criteria`: one line per check, the "no" statement.
    *   `additional_info`: empty.

    This is passed to the unchanged screening prompt (`v1`). The v1 topic configs,
    including `tests/fixtures/review_config.json`, stay untouched and are no
    longer eval inputs. The report states that the baseline input differs
    from v1's in wording and in the dropped "Be conservative" instruction.
*   **Labeling prompt:** the question, the checks with their yes/no meaning,
    and the instruction to answer each check with `yes`, `no` or `not_stated`
    from the title and abstract only, with a one-line reason per answer.

The decision is derived by one function, in the same way for gold and for
anything else that has check answers:

*   any `no` gives `exclude`;
*   all `yes` gives `include`;
*   otherwise the decision is `uncertain`.

### Where data lives (author decision: gold and results in git, everything else in a local data folder)

**In this repository (public):**

| What | Where | Holds |
| --- | --- | --- |
| Search snapshot | `eval/gold/v0/<topic>/search.json` | The ranked papers as the search node returns them; the synthetic abstract; whether the query-expansion fallback was used; the OpenAlex request parameters; search model and prompt version; retrieval timestamp |
| Candidate pool | `eval/gold/v0/<topic>/pool.json` | Every paper considered for the gold set: the metadata the screener sees (title, abstract exactly as the screener receives it, year, authors, DOI, OpenAlex id) and its origin (`search` with rank, `search_extended`, or `link_list`) |
| Gold labels | `eval/gold/v0/screening.json`, `extraction.json`, `provenance.json` | See "Gold files" below. Extraction gold holds one-sentence quotes only, never full text |
| Results | `eval/results/<run_id>.json` | Scores, timings and provenance of one run |

The search snapshot and the pool are committed with the gold labels because
they define the gold set: the ranks precision@10 uses and the exact abstracts
that were labeled. Titles and abstracts come from OpenAlex, whose data is
published under CC0.

**In the local eval data folder (outside this repository):**

| What | Path inside the folder | Holds |
| --- | --- | --- |
| PDFs | `pdfs/<openalex_id>.pdf` | The 6 extraction-gold PDFs |
| Page text | `pages/<openalex_id>.json` | PyMuPDF text per page (1-based index), PyMuPDF version, PDF URL, PDF SHA-256 |
| Raw outputs | `outputs/<run_id>/` | Every record of a run, including retrieved chunk text and extraction values, plus the run's provenance file |
| Labeling work files | `labeling/` | The inputs-only folder for model labeling, the raw model answers, and the human's blind-labeling sheet |

*   **Location:** the folder's path comes from a new setting, `EVAL_DATA_DIR`
    (`src/llm/settings.py`), so no path is hard-coded.
*   **Backup:** the folder is a clone of a separate private GitHub repository.
    A sync command commits everything in the folder and pushes it. It is run
    after every gold-set build step that writes to the folder, and after every
    baseline or Phase 2b run. The run command prints a reminder when it
    finishes.
*   **Integrity:** each PDF's URL and SHA-256 are also recorded in
    `eval/gold/v0/extraction.json`. A restored or re-downloaded PDF can then be
    checked against the gold set.
*   **Licensing:** because full text never enters the public repository, the
    extraction-gold papers need no license restriction; any downloadable
    paper works.

The existing v1 snapshots in `eval/snapshots/v1/` stay as they are. They are no
longer inputs to the gold set: topic 2 gets a fresh search, and its 24 v1 papers
are mostly formal verification of classic multi-agent systems, which the author
cannot label.

**Search output capture.** Today the search agent only prints the synthetic
abstract and the fallback message. The snapshot needs both. One additive change
in `src/pipeline/search/agent.py`: the search result also returns the synthetic
abstract and a `fallback_used` flag next to `papers`. The search node keeps
reading only `papers`, so pipeline behaviour does not change. This is the only
change to `src/` that the harness needs, apart from a context length if G7
requires one.

### Gold set (author decision: separate search set and screening set)

Each topic has two overlapping sets of labeled papers:

*   **Search set:** the first 10 papers of the frozen search output. They are
    always labeled and never replaced, and precision@10 is computed on them. If
    two of them are the same study, the second copy counts as not relevant.
*   **Screening set:** 20 papers with 8–12 gold includes and at most 4 gold
    `uncertain`. Screening metrics are computed on them.

**Build steps, in order.** Each step is a harness command or a documented manual
step.

1.  **Write the topic configs.** The checks must be final before any search,
    because search adds the inclusion criteria to its query
    (`src/pipeline/search/new_main.py:40-42`).
2.  **Freeze search.** Run the search adapter once per topic with the v1 search
    model. Store `eval/gold/v0/<topic>/search.json`. If `fallback_used` is true, discard the run and
    repeat it: a fallback run does not represent the baseline search.
3.  **Build the candidate pool.**
    *   All papers of the frozen search output (20–25 per topic).
    *   For topic 1: the v1 link list, mapped to OpenAlex ids (by DOI where
        there is one, by hand otherwise).
    *   If a topic's pool cannot reach 8 gold includes after labeling, it is
        extended with the next results of the same frozen OpenAlex query
        (`search_extended`).
    *   Papers from before 2020 and papers without an abstract are left out of
        the pool, except in the search set, which is never filtered.
4.  **Remove duplicates.** Titles are compared after lowercasing and removing
    punctuation and whitespace. One record is kept per study: the journal
    version if there is one, otherwise the first seen. The dropped OpenAlex id
    is recorded as an alias.
5.  **Model labeling.** Claude labels every pool paper in a fresh context (one
    headless call per paper). Each call receives only the labeling prompt and
    that paper's title and abstract, from a folder that holds only these
    inputs (`labeling/` in the data folder). The raw answer per paper is
    saved there. Every answer gets source `model`.
6.  **Select the screening set.** A seeded script does the selection:
    *   It takes the search-set papers first, skipping gold-`uncertain` papers
        once the cap of 4 is reached.
    *   It fills up to 20 papers from the rest of the pool, drawing includes and
        excludes so that the include count lands in 8–12.
    *   It records the seed and every skipped paper.

    Topic 1 draws includes from both the link list and the search pool, and
    records each paper's origin.
7.  **Human blind sample.** About 21 papers, 7 per topic, labeled by the
    human without seeing the model's answers, in shuffled order. The sheet is
    kept in the data folder's `labeling/`, not in this repository.
    *   **Borderline part:** up to 3 per topic, among papers that have a
        `not_stated` answer, or a decision that rests on one check. "Rests on
        one check" means an exclude with exactly one `no`, or, for topic 2, any
        paper whose decision changes if check 3 changes.
    *   **Random part:** the rest, drawn from that topic's search set, so the
        Phase 2b search judge has human labels from every topic.
8.  **Compare and escalate.** Agreement is counted per topic and check, on the
    check answer (`yes`, `no`, `not_stated`). The escalation rule:
    *   **Trigger:** 2 or more disagreements on the same check within one
        topic.
    *   **Scope:** every paper of that topic, in either set, whose decision
        would change if that check's answer changed.
    *   **Action:** the human re-answers only that check, with the model's
        answer hidden.
    *   **Label source:** an answer the human confirms becomes
        `model_verified`; an answer the human changes becomes `human`.
    *   **Time limit:** about 20 minutes. Papers not reached keep source
        `model`, and the report gives their number.
9.  **Extraction gold.**
    *   **Papers:** 3 papers each from topics 1 and 2. They must be gold
        includes in the screening set and have a downloadable PDF.
    *   **Freezing:** the PDF and its PyMuPDF page text go to the data folder.
        The PDF's URL and SHA-256 go to the gold file.
    *   **Pre-filling:** Claude, from the page text only, fills each of the five
        scored fields that the paper reports with a 1-based page index and a
        one-sentence quote. The fields are `method`, `dataset`, `task`,
        `main_findings` and `limitations`.
    *   **Checks:** the quote-check script finds every quote on its stated page
        after whitespace normalization; failures go back to Claude. The human
        then checks each value against its quote and page; confirmed fields
        become `model_verified`.
10. **Validate.** The validation script checks:
    *   the set sizes and the mix;
    *   that every decision re-derives from its check answers;
    *   that every answer has a source;
    *   that there are no duplicate studies;
    *   that every quote is found on its page.

**Gold files.**

*   **`eval/gold/v0/screening.json`:** one record per pool paper, containing:
    *   the topic, OpenAlex id, aliases and origin;
    *   `search_rank` (or null) and `in_screening_set`;
    *   per check: the answer, the source and the reason;
    *   the derived decision.
*   **`eval/gold/v0/extraction.json`:** one record per paper, with the PDF URL
    and SHA-256. It holds one entry per `found` field, with the field, value,
    page, one-sentence quote and source.
*   **`eval/gold/v0/provenance.json`:** the labeling model id, the Claude Code
    version, the labeling prompt, the seeds, the dates, the agreement counts,
    and the escalation log.

### Harness (author decision: contract owned by the harness, one adapter per pipeline version)

**Contract.** Four calls, each returning record types defined by the harness:

*   `search(topic) -> SearchRecord`: ranked papers, synthetic abstract,
    `fallback_used`.
*   `screen(papers, topic) -> [ScreeningRecord]`: per paper, a decision
    (`include`, `exclude`, `uncertain` or `failed`), the error text if it
    failed, the reasoning, and the matched criteria.
*   `retrieve(paper_pages) -> [RetrievedChunk]`: per field, the retrieved chunks
    with field, rank, page, ordinal and text.
*   `extract(paper, chunks, topic) -> [FieldRecord]`: per scored field, a status
    (`found` or `not_found`) and the value.

**Phase 1 adapter.** It calls the graph's own code wherever possible, so that it
measures the system and not a copy of its glue:

*   **`search`:** calls `src/pipeline/search/new_main.main`, the function the
    search node calls, with the rendered criteria.
*   **`screen`:** calls `screening_node` with a state built from the topic and
    the papers, so the criteria formatting and `pre_excluded=[]` are the node's
    own. It maps `included_papers`, `excluded_papers`, `uncertain_papers` and
    `failed_papers` to records.
*   **`retrieve`:** runs `chunk_pages` on the frozen page text and embeds the
    chunks with `get_embedder()`. It stores them in an `InMemoryRepository`
    and calls `retrieve_field_chunks`. That function returns text only, so the
    adapter maps each returned text back to its chunk's page and ordinal by
    exact match within that paper's chunks. This is glue the harness adds; no
    node does it.
*   **`extract`:** calls `extract_from_retrieved_chunks` with the retrieved
    texts. It maps the five scored fields from the retrieval keys:
    *   `method_chunks` to `method`
    *   `dataset_chunks` to `dataset`
    *   `task_chunks` to `task`
    *   `findings_chunks` to `main_findings`
    *   `limitations_chunks` to `limitations`

    `paper_type`, `relevance_to_research_question` and `confidence` are not
    scored.
*   **Status mapping (v1 text to status):** a value is `not_found` if, after
    lowercasing and trimming, it is empty, or starts with "not specified", "not
    explicitly specified", "not mentioned" or "not stated", or is "no empirical
    dataset". Otherwise it is `found`. The mapping has its own unit test.
    "No empirical dataset" counts as `not_found`, because the gold holds only
    fields the paper reports.

Extraction runs on the 6 extraction-gold papers whatever the screener decided
about them, so extraction scores do not mix in screening errors.

**Run command.** One command takes an adapter name and the model settings
(environment variables, read through `src/llm/settings.py` as usual), and runs
these steps:

1.  **Precheck.** Every configured Ollama model answers a one-token request.
    If one does not, the command stops with an error that names the model.
2.  **Screening twice.** Screen the screening set twice with the production
    concurrency of 3.
3.  **Retrieval and extraction.** Retrieve and extract the 6 extraction-gold
    papers. Retrieval runs on the in-memory repository, so no Postgres and no
    library rows are touched.
4.  **Post-check.** Run the Ollama health check again. If it fails, or a failed
    paper's error text names a connection error or a timeout, mark the run
    `incomplete` and do not score it.
5.  **Save outputs.** Save all records and per-stage wall-clock timings to
    `outputs/<run_id>/` in the data folder, with a provenance file. The provenance file holds:
    *   models
    *   Ollama model digests
    *   prompt versions
    *   context length
    *   embedding model
    *   `CHUNKER_VERSION`
    *   `RETRIEVAL_TOP_K`
    *   concurrency
    *   gold-set version
    *   snapshot timestamps
    *   adapter name
    *   git commit
6.  **Score** (below) and write `eval/results/<run_id>.json`.

Scoring is also a separate command that reads only `outputs/<run_id>/` in the
data folder and `eval/gold/`. Correcting a gold label re-scores without
re-running a model. The page text for retrieval and the quote check is read
from the data folder; before use, each page-text file's PDF hash is compared
with the one in the gold file.

### Metrics

All metrics are reported as counts with rates next to them, per topic and
pooled.

*   **Screening (screening set, first run):**
    *   **Gold × model table:** gold `include`/`exclude`/`uncertain` against model
        `include`/`exclude`/`uncertain`/`failed`.
    *   **Include recall:** model `include` out of gold `include`. A model
        `uncertain` or a failed call is a miss.
    *   **Exclude recall:** model `exclude` out of gold `exclude`. A failed call
        is a miss.
    *   **Hard errors:** gold include with model exclude, and gold exclude with
        model include.
    *   **Failed calls:** the count of failed calls.
    *   **Gold-`uncertain` papers:** counts of what the model answered, not
        scored.
*   **Run-to-run noise:** papers whose decision differs between the two
    screening runs, in total and among gold includes.
*   **Search precision@10 (search set):** gold includes among the 10, per topic.
*   **Retrieval recall@5 (extraction gold):** for each gold `found` field, it is
    a hit if the normalized quote appears in the field's retrieved chunks.
    Retrieved chunks that are on the same page with consecutive ordinals are
    joined before the check, so a quote crossing a chunk boundary still
    counts. Reported per field and pooled.
*   **Extraction field status:** gold `found` fields that the model reports as
    `found`, per field and pooled.
*   **Structured-output health:** failed calls per stage; retries are not
    visible in v1 and are not reported.
*   **Timings:** wall-clock per stage, and per paper for screening and for
    retrieval plus extraction.

### Truncation check (G7)

Before the baseline, one logged run extracts the largest of the 6
extraction-gold papers (the most retrieved characters). The run records
`usage.prompt_tokens` from the response. For comparison, it counts the same
prompt's tokens with the model family's own tokenizer, loaded through
`transformers` (already installed with sentence-transformers), for example the
Qwen2.5-Coder tokenizer for `qwen2.5-coder:7b`.

*   **The counts match within a small margin:** there is no truncation, and
    the context length in use is recorded.
*   **The reported count is lower and equals a round context size:** Ollama
    truncated the prompt. Every run, including the baseline, then uses a
    derived Ollama model with an explicit `num_ctx`, created from a Modelfile
    that is committed under `eval/`. The run's provenance names it, and the
    truncation becomes a backlog item as a v1 finding.

### Latency budget (author decision: from harness timings)

The budget is built from what the baseline run measures:

```text
budget = search time of the snapshot run
       + 25 × screening time per paper (mean of the two runs)
       + 10 × retrieval-plus-extraction time per paper (mean over the 6 papers)
```

The factors 25 and 10 come from today's search output size and the plan's
`target_included = 10`. The budget leaves out PDF download, Postgres and graph
overhead, because these are not agent time, which is what Phase 2b can improve.
For reporting only, one end-to-end smoke run (topic 1, through the API, with
Postgres) is timed once. Its total time goes into the baseline report next to the
budget, but it does not define the budget.

### Model-selection rule for Phase 2b (G10)

Phase 2b compares a candidate with the baseline on the same frozen inputs and
gold set, paper by paper:

*   **Screening:**
    *   **Wins and losses:** a win is a gold include that the candidate
        includes and the baseline does not; a loss is the reverse.
    *   **Threshold:** the candidate qualifies if wins − losses ≥ N, where N is
        the number of gold includes that flipped between the two baseline
        runs, plus 1, and at least 2.
    *   **Gates:** no more hard errors and no more failed calls than the
        baseline.
*   **Extraction:**
    *   **Wins and losses:** on gold `found` fields, a win is a field the
        candidate reports `found` and the baseline does not; a loss is the
        reverse.
    *   **Threshold:** wins − losses ≥ 2.
    *   **Faithfulness:** the Phase 2b faithfulness judge must not score the
        candidate lower than the baseline by more than the judge's own
        repeat-run difference.
*   **Embedding:**
    *   **Wins and losses:** on gold `found` fields, a win is a quote the
        candidate retrieves and the baseline does not; a loss is the reverse.
    *   **Threshold:** wins − losses ≥ 2. Embeddings are deterministic, so the
        threshold is the minimum.
*   **Gates for every role:**
    *   **Time:** the candidate's stage time keeps the whole run within the
        latency budget.
    *   **Memory:** while it runs, macOS reports no swap use.

If no candidate qualifies, the v1 model stays, and the decision record says why.

## Alternatives Considered

Alternatives from the brainstorm (`concepts_brief.md`, "Alternatives Weighed",
and `docs/eval_notes.md`) and from drafting this document.

### Topics and labels

#### Alternative A: Civil engineering as topic 3

Three options were considered: concrete strength prediction, bridge vibration
monitoring, and recycled aggregate.

*   **Pros**: Option B (bridge vibration monitoring) had many hard boundary
    cases (lab beam versus real bridge, simulation versus field test).
*   **Cons**: The labeler no longer has expert knowledge of the field.
*   **Reason for Rejection**: Rejected by author: they have forgotten most civil
    engineering details, so their blind labels would not be expert labels.

#### Alternative B: Ecology, clinical medicine, or a quasi-experimental economics topic as topic 3

*   **Pros**:
    *   Ecology (neonicotinoids and bees in the field) had a lab-versus-field
        boundary and the highest PDF share.
    *   Clinical trials of intermittent fasting matched how systematic reviews
        are usually done.
    *   Minimum wage studies limited to quasi-experimental designs had real
        borderline cases.
*   **Cons**:
    *   The author is not an expert in ecology or medicine.
    *   The minimum wage topic requires judging whether a study design is
        quasi-experimental.
*   **Reason for Rejection**: Rejected by author: topic 3 comes from economics,
    with criteria a non-expert can check from the abstract (population, region,
    data level, outcome); a design judgment cannot be made reliably.

#### Alternative C: Cash transfers and children's education in Latin America as topic 3

*   **Pros**: Crisp criteria; 44 of the first 50 search results have a PDF link.
*   **Cons**: Its most common borderline case is a country name, which every model
    gets right.
*   **Reason for Rejection**: Rejected by author: it would separate screening
    models less than the mobile money topic, whose boundaries (household versus
    country or firm data, welfare outcome versus adoption) need the abstract to
    be read.

#### Alternative D: Keep the v1 topic 2, or fit it to the 24 v1 papers

*   **Pros**: Reuses the frozen v1 snapshot; no new search.
*   **Cons**: The v1 question (evaluate multi-agent systems "efficiently") and
    criteria (safety only, no performance or cost) contradict each other. The
    24 papers are mostly formal verification of classic multi-agent systems.
*   **Reason for Rejection**: Rejected by author: they can label LLM-based
    multi-agent systems, which they built, but not formal verification. Topic 2
    now covers any kind of evaluation of LLM-based multi-agent systems, with a
    fresh search.

#### Alternative E: Gold labels judged against the full paper

*   **Pros**: Closer to the truth about each paper; fewer `uncertain` labels.
*   **Cons**: The screener sees only title and abstract, so it would be penalized
    for information it never had. Reading full papers costs labeling time.
*   **Reason for Rejection**: Rejected by author: gold labels judge only what the
    title and abstract say, and a paper can be gold `uncertain`.

#### Alternative F: Groq Llama 3.3 70B as the pre-labeling model

*   **Pros**: Free, and needs no second tool.
*   **Cons**: Its free tier limits tokens per minute and per day, which whole
    papers would hit. It would also be the same model as the judge.
*   **Reason for Rejection**: Rejected by author: Claude in Claude Code labels
    once, outside the pipeline. It is a different model family from the judge
    and has no token limit at this size. Groq remains the only outside service
    the system and the harness use.

#### Alternative G: A purely random blind sample, or a stratified sample with double labeling and weighted agreement

*   **Pros**: A random sample gives an unbiased agreement estimate. Double
    labeling finds borderline papers without relying on a single pass.
*   **Cons**: A random sample of about 20 rarely contains the borderline papers
    where the model's labels are most likely wrong. Double labeling and
    weighted agreement add work and detail that v0 does not need.
*   **Reason for Rejection**: Rejected by author: one labeling pass; the blind
    sample includes some borderline cases; agreement is reported as counts;
    one escalation rule. The rest is on the "Later" list.

### Evaluation scope

#### Alternative H: Search model benchmark and search judge in Phase 2a

*   **Pros**: Search would be measured on more than one run, and candidate
    search models could be compared.
*   **Cons**: Needs a calibrated judge in Phase 2a, which adds labeling time and
    Groq quota.
*   **Reason for Rejection**: Rejected by author: search problems are logic
    problems (query construction, no subfield filter) for the Phase 2b agent
    review. Baseline precision@10 is scored from gold labels; the search judge
    moves to Phase 2b.

#### Alternative I: Faithfulness judge and its calibration in Phase 2a

*   **Pros**: A faithfulness number at the end of Phase 2a.
*   **Cons**: Labeling v1 extraction outputs as faithful or unfaithful takes
    2–4 minutes per value, because v1 output has no evidence pointer. That
    breaks the 2-hour budget. Nothing in Phase 2a depends on the number.
*   **Reason for Rejection**: Rejected by author: Phase 2a scores extraction by
    field status and retrieval recall. The baseline extraction outputs are
    saved, and the Phase 2b faithfulness judge scores them after the fact. That
    score is a required Phase 2b task.

#### Alternative J: Model benchmark and decision record in Phase 2a

*   **Pros**: Phase 2b would start with the chosen models in place.
*   **Cons**: Lengthens Phase 2a, and its numbers are not needed until Phase 2b
    changes something.
*   **Reason for Rejection**: Rejected by author: Phase 2a stays minimal (gold set,
    harness, baseline, error analysis). The benchmark is a Phase 2b experiment
    that uses this harness and the paired rule written here.

#### Alternative K: `not_reported` fields in the extraction gold

*   **Pros**: Would measure whether the model invents values for fields a paper
    does not report.
*   **Cons**: Checking an absence claim means reading the whole paper, which does
    not fit the labeling budget.
*   **Reason for Rejection**: Rejected by author: extraction gold keeps only
    `found` fields with script-checked quotes.

### Architecture (decided while drafting)

#### Alternative L: Commit page text, or everything including PDFs, to this repository

*   **Pros**: Every score could be reproduced from a fresh clone of this
    repository alone.
*   **Cons**: This repository is public. Page text and retrieved chunks are a
    paper's full text, and open access does not always permit redistribution.
    PDFs would also stay in git history permanently.
*   **Reason for Rejection**: Rejected by author: only gold files and results are
    committed. Page text, PDFs and raw outputs live in a local data folder that
    is backed up to a private repository. This also removes the need to
    restrict extraction papers by license.

#### Alternative M: Keep all frozen data outside git, with only manifests in git

*   **Pros**: No size or licensing questions at all.
*   **Cons**: The gold labels themselves would exist only on one laptop. This
    contradicts plan section 8 ("datasets are fixed and versioned in
    `eval/`").
*   **Reason for Rejection**: Rejected by author: the gold set and results belong
    in this repository; only material that is full text or bulky stays outside.

#### Alternative N: The harness calls the pipeline functions directly

*   **Pros**: Least code; it measures the real functions.
*   **Cons**: Scoring would depend on v1's return shapes. Phase 2b changes
    extraction output (status, evidence chunk), so the harness and its scoring
    would have to be rewritten during the phase they measure.
*   **Reason for Rejection**: Rejected by author: a contract owned by the
    harness, with one adapter per pipeline version, keeps the scoring code the
    same across versions.

#### Alternative O: The harness runs the real LangGraph graph on frozen inputs

*   **Pros**: Measures exactly what production runs, including the graph's glue.
*   **Cons**: Retrieval results are not in the graph state with page and ordinal.
    An extraction-gold paper that the baseline screener excludes would never be
    extracted, mixing screening errors into extraction scores.
*   **Reason for Rejection**: Rejected by author: the adapter calls the graph's
    node functions where it can (for example `screening_node`), and runs
    extraction on the gold papers whatever the screener decided.

#### Alternative P: A single 20-paper set per topic where the sample mix is only a target, or a topic that grows past 20 papers

*   **Pros**: One set per topic and a simpler gold file (single set), or the mix
    always holds (growing topic).
*   **Cons**:
    *   With a single set, a topic with poor search can end up with few scored
        papers.
    *   A growing topic has uneven sizes and needs extra papers from deeper
        search results.
*   **Reason for Rejection**: Rejected by author: each topic has a search set
    (top-10, always labeled) and a screening set (20 papers that meet the mix),
    and the two overlap where they can.

#### Alternative Q: Latency budget from live end-to-end runs, or set in Phase 2b

*   **Pros**: Live runs include PDF download, Postgres and graph overhead.
    Setting the budget in Phase 2b would define it on the run it limits.
*   **Cons**:
    *   Live runs vary with the search results and are noisy when few papers
        are included.
    *   A budget set by Phase 2b after seeing its own speed limits nothing, and
        the plan requires it in Phase 2a.
*   **Reason for Rejection**: Rejected by author: the budget is built from the
    harness's stage timings, because agent time is what Phase 2b can improve.
    One end-to-end smoke run is timed for reporting only.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Privacy and data flow:**
    *   The harness sends nothing to outside services except OpenAlex (search,
        metadata) and the paper hosts (PDF download).
    *   Claude is used only for the one-time labeling and the extraction
        pre-fill, both run by hand outside the pipeline.
    *   Groq is not used in Phase 2a.
    *   No user data is involved; every input is a public open-access paper.
*   **Copyright:** no full text enters this public repository. Only metadata,
    abstracts (OpenAlex, CC0) and one-sentence quotes are committed.
*   **Runtime:** one baseline run (two screening passes over 60 papers, plus
    retrieval and extraction for 6 papers) should finish in under about 45
    minutes on the MacBook Air M4. This is a target to measure, not a gate.
    Thermal throttling makes later stages slower; the timings record stage
    order.
*   **Rollback:** the only changes to `src/` are additive: two extra fields in
    the search result and one optional setting. Reverting the harness commits
    leaves the pipeline unchanged.

### Additional Resources

*   `docs/plan_v2.md`: sections 8, 10 (Phase 2a and 2b) and 11.
*   `docs/eval_notes.md`: the brainstorm record with every decision and its
    reason.
*   `concepts_brief.md`: the Goldfish review of the brainstorm.
*   `docs/backlog.md`: items #33, #37 and the triaged items #10, #16, #24, #27
    and #29.

### Future Improvements

These come from the "Later" list of the brainstorm and are not in v0:

*   **Double labeling:** label every paper twice in fresh contexts, and treat
    disagreement between the two passes as a borderline signal.
*   **Weighted agreement:** report agreement weighted by each stratum's share
    of all papers.
*   **Lenient precision@10:** report it next to the strict one, with gold
    `uncertain` counted as relevant.
*   **Noting the step size of precision@10:** per topic it moves in 10-point
    steps, which cannot separate close search variants.
*   **Split precision reporting after Phase 2b:** report how many of each
    top-10 were scored from gold labels and how many by the judge.
*   **`not_reported` extraction gold:** a script shows candidate passages, so
    absence claims can be checked without reading the whole paper.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Order of work

Each step is one commit with passing tests (`plan_v2.md`, working rule 5).

1.  **Search capture and the data-folder setting.** `src/pipeline/search/agent.py`,
    `src/llm/settings.py`, `.env.example`, and their tests.
2.  **Harness core, which never imports `src/`.** Record types, topics, text
    helpers, gold loading and validation, and scoring, with unit tests and
    fixtures.
3.  **Phase 1 adapter, run, score, Ollama check, truncation check, sync.**
    Includes the dry-run test on the fake surface, plus the Makefile and CI
    updates.
4.  **Gold-build commands**, with unit tests.
5.  **The three topic configs.**
6.  **Documentation:** `CLAUDE.md`, `eval/README.md`, the backlog triage,
    and the status notes in the plan and the eval notes.

Data steps follow the code. Each one ends with the data-folder sync:

7.  **Build the gold set** (CUJ 1, build steps 2–10). Commit
    `eval/gold/v0/`.
8.  **Truncation check (G7).** If it finds truncation: commit the Modelfile
    and add a backlog item.
9.  **Baseline run.** Commit `eval/results/<run_id>.json`.
10. **End-to-end smoke run.** Write `eval/reports/2a_baseline.md` with the
    numbers, the error analysis, the latency budget and N. Commit it.

### Data formats

All files are JSON with UTF-8 and 2-space indentation unless stated. Field names
are exact.

*   **Topic config** (`eval/topics/<topic_id>.json`):
    *   `topic_id` (`t1_social_media`, `t2_llm_mas_eval` or `t3_mobile_money`)
    *   `research_question`
    *   `min_year`: 2020
    *   `checks`: a list of objects, each with `id` (`c1` …), `question`, `yes`
        (the inclusion statement) and `no` (the exclusion statement)
*   **Search snapshot** (`eval/gold/v0/<topic_id>/search.json`):
    *   `topic_id` and `retrieved_at` (ISO 8601, UTC)
    *   `duration_s`
    *   `search_model` and `search_prompt_version`
    *   `synthetic_abstract` and `fallback_used`
    *   `openalex_params`: `target_output_count`, `min_citations`, `start_year`
    *   `papers`: the list exactly as the search node returns it, in rank order
*   **Pool** (`eval/gold/v0/<topic_id>/pool.json`): a list of papers. Each paper
    has:
    *   `paper_key`, which is the OpenAlex id
    *   the `ResearchPaper` fields: `title`, `abstract`, `year`, `authors`,
        `doi`, `url`, `openalex_id`, `pdf_url`, `venue`
    *   `origin`: `search`, `search_extended` or `link_list`
    *   `search_rank`: an integer or null
    *   `aliases`: the OpenAlex ids of duplicates that were dropped
*   **Link list** (`eval/gold/v0/t1_social_media/link_list.json`): one entry
    per URL of the v1 list (`git show dcc06b0^:Testdatensatz/link.md`). Each
    entry has `url`, `openalex_id` (or null) and `resolution`: `doi`,
    `manual` or `unresolved`.
*   **Screening gold** (`eval/gold/v0/screening.json`): a list of records. Each
    record has:
    *   `topic_id` and `paper_key`
    *   `in_search_set` and `in_screening_set`
    *   `answers`: per check id, an object with `answer` (`yes`, `no` or
        `not_stated`), `source` (`model`, `model_verified` or `human`) and
        `reason`
    *   `decision`: derived, never edited by hand
*   **Extraction gold** (`eval/gold/v0/extraction.json`): a list of records.
    Each record has:
    *   `paper_key`, `topic_id`, `pdf_url` and `pdf_sha256`
    *   `fields`: a list of objects, each with `field` (one of `method`,
        `dataset`, `task`, `main_findings`, `limitations`), `value`, `page`
        (1-based), `quote` (one sentence) and `source`
*   **Gold provenance** (`eval/gold/v0/provenance.json`):
    *   `labeling_model` and `claude_code_version`
    *   `labeling_prompt_sha256` (the prompt text is committed at
        `eval/gold/v0/labeling_prompt.md`) and `prefill_prompt_sha256` (at
        `eval/gold/v0/prefill_prompt.md`)
    *   `selection_seed` and `skipped_papers`
    *   `agreement`: per topic and check, a count of agreements and
        disagreements
    *   `escalation`: per trigger, the topic, the check, the papers in scope,
        the papers reviewed and the answers changed
    *   `dates`
*   **Run outputs** (`<EVAL_DATA_DIR>/outputs/<run_id>/`):
    *   `provenance.json`
    *   `search.json` (the `SearchRecord`, only when the run re-runs search)
    *   `screening_1.json` and `screening_2.json` (lists of `ScreeningRecord`)
    *   `retrieval.json` (per paper, a list of `RetrievedChunk`)
    *   `extraction.json` (per paper, a list of `FieldRecord`, plus the raw
        model output)
    *   `timings.json`

    `run_id` is `<UTC yyyymmddThhmmss>-<adapter>-<short git sha>`.
*   **Results file** (`eval/results/<run_id>.json`):
    *   `run_id` and `status` (`complete` or `incomplete`)
    *   `provenance` (copied)
    *   `screening`: per topic and pooled. It holds the gold × model `table`,
        and `include_recall`, `exclude_recall` and `hard_errors`, each given as
        `{k, n, rate}`. It also holds `failed` and `gold_uncertain_outcomes`.
    *   `noise`: `flips_total` and `flips_gold_include`
    *   `search`: per topic, `precision_at_10` as `{k, n}`
    *   `retrieval`: per field and pooled, `recall_at_5` as `{k, n}`
    *   `extraction`: per field and pooled, `found` as `{k, n}`
    *   `timings`
    *   `latency_budget_s`

### Target Files to Create/Modify

#### 1. `src/pipeline/search/agent.py` (Modify)

*   **Type / Scope**: Python module, the search agent.
*   **Proposed Changes**:
    *   **Fallback flag.** `_generate_academic_search_strategy` adds
        `fallback_used: False` to its result on success and `True` in the
        fallback branch.
    *   **Extra output fields.** `run_precise_retrieval_cycle` returns
        `{"papers": [...], "synthetic_abstract": str, "fallback_used": bool}`.
    *   **Reusable paper formatting.** The per-paper formatting inside
        `run_precise_retrieval_cycle` (title, abstract reconstruction, authors,
        locations, ids) moves unchanged into a module-level function
        `format_openalex_work(work: dict, client: OpenAlexClient) -> dict`. The
        cycle calls it, and so does the gold-build pool step for link-list
        papers and extended results. Labeled abstracts are then exactly the
        strings the screener receives.
    *   **No behaviour change.** `search_node` still reads only `papers`, and
        the golden-transcript test must pass unchanged.

#### 2. `src/llm/settings.py` (Modify)

*   **Type / Scope**: Settings.
*   **Proposed Changes**:
    *   Add `eval_data_dir: Path | None = None`, with a one-line docstring
        comment: the local eval data folder, required only by eval commands.
    *   Eval commands that need it fail with "EVAL_DATA_DIR is not set; point
        it at the local eval data folder (a clone of the private backup
        repository)".

#### 3. `.env.example` (Modify)

*   **Type / Scope**: Configuration documentation.
*   **Proposed Changes**: Add a commented `# EVAL_DATA_DIR=` with the
    explanation: the eval data folder outside this repository, a clone of the
    private backup repository, holding PDFs, page text, raw run outputs and
    labeling work files.

#### 4. `tests/unit/test_search_agent.py` (Create)

*   **Type / Scope**: Unit test.
*   **Proposed Changes**: with the fake LLM and the stubbed OpenAlex client:
    *   The cycle returns `synthetic_abstract` and `fallback_used = False`.
    *   With a fake that raises, `fallback_used = True` and the synthetic
        abstract equals the raw query.
    *   `format_openalex_work` on a fixture work returns the same dict the
        cycle produced before the refactor.

#### 5. `tests/unit/test_settings.py` (Modify)

*   **Type / Scope**: Unit test.
*   **Proposed Changes**: `eval_data_dir` defaults to `None`; when set, it is
    read from `EVAL_DATA_DIR`.

#### 6. `eval/__init__.py`, `eval/harness/__init__.py`, `eval/gold_build/__init__.py` (Create)

*   **Type / Scope**: Package markers.
*   **Proposed Changes**: Empty. This makes `python -m eval.harness.run` and
    the test imports work from the repository root, as `src` does.

#### 7. `eval/harness/records.py` (Create)

*   **Type / Scope**: Pydantic models, the harness contract. No `src` imports.
*   **Proposed Changes**:
    *   **`SearchRecord`**: `papers` (list of dicts), `synthetic_abstract`,
        `fallback_used`.
    *   **`ScreeningRecord`**:
        *   `paper_key`
        *   `decision` (`include`, `exclude`, `uncertain` or `failed`)
        *   `error` (str or None)
        *   `reasoning`
        *   `matched_inclusion` and `matched_exclusion`
    *   **`RetrievedChunk`**: `paper_key`, `field`, `rank`, `page`, `ordinal`,
        `text`.
    *   **`FieldRecord`**: `paper_key`, `field`, `status` (`found` or
        `not_found`), `value`.
    *   **`RunProvenance`**:
        *   models per role and Ollama digests
        *   prompt versions per role
        *   `context_length` (int or `"ollama_default"`)
        *   `embedding_model`, `chunker_version`, `retrieval_top_k`,
            `concurrency`
        *   `gold_version` and `snapshot_retrieved_at` per topic
        *   `adapter`, `git_commit`, `started_at`

#### 8. `eval/harness/topics.py` (Create)

*   **Type / Scope**: Topic configs. No `src` imports.
*   **Proposed Changes**:
    *   `load_topic(topic_id) -> Topic`, which validates the config.
    *   `derive_decision(answers: dict[str, str]) -> str`: the rule in the
        Technical Plan.
    *   `decided_by(answers, check_id) -> bool`: true if changing that check's
        answer could change the decision.
    *   `render_screener_input(topic) -> dict`: `research_question`,
        `inclusion_criteria` (the list of `yes` statements),
        `exclusion_criteria` (the list of `no` statements),
        `additional_info = None`, `min_year`.
    *   `render_labeling_prompt(topic) -> str` and `labeling_json_schema(topic)
        -> dict`. The schema requires one answer per check id, each with
        `answer` in `yes`, `no` or `not_stated`, and a `reason`.

#### 9. `eval/harness/text.py` (Create)

*   **Type / Scope**: Text helpers. No `src` imports.
*   **Proposed Changes**:
    *   `normalize_ws(text)`: collapses all whitespace to single spaces and
        trims.
    *   `normalize_title(title)`: lowercase, then removes everything that is
        not a letter or a digit.
    *   `quote_on_page(quote, page_text) -> bool`: compares the two after
        `normalize_ws`.
    *   `joined_runs(chunks: list[RetrievedChunk]) -> list[str]`: sorts by
        page and ordinal, and joins chunks on the same page with consecutive
        ordinals into one string per run.

#### 10. `eval/harness/gold.py` (Create)

*   **Type / Scope**: Gold loading and validation. No `src` imports.
*   **Proposed Changes**:
    *   `load_screening_gold()` and `load_extraction_gold()`.
    *   `validate(gold_dir, data_dir | None) -> list[str]` returns
        human-readable problems. It checks:
        *   search sets of 10
        *   screening sets of 20 with 8–12 includes and ≤ 4 uncertain
        *   every decision equal to `derive_decision(answers)`
        *   every answer with a source
        *   no two papers in a topic with the same `normalize_title`
        *   extraction fields only from the five scored fields

        When `data_dir` is given, it also checks every quote on its page and
        every page file's `pdf_sha256` against the gold file.

#### 11. `eval/harness/scoring.py` (Create)

*   **Type / Scope**: Metrics. No `src` imports.
*   **Proposed Changes**: `score(outputs_dir, gold_dir) -> dict` builds the
    results structure in "Data formats". It uses the metric definitions in
    the Technical Plan, with only the screening-set papers for screening
    metrics, the search set for precision@10, `joined_runs` plus
    `normalize_ws` substring for recall@5, and `FieldRecord.status` for field
    status. If `provenance.json` marks the run incomplete, it raises an error
    instead of scoring.

#### 12. `eval/harness/data_dir.py` (Create)

*   **Type / Scope**: Paths in the eval data folder.
*   **Proposed Changes**: `data_dir()` reads `get_settings().eval_data_dir` and
    fails with the message in file 2. It also has helpers for the `pdfs/`,
    `pages/`, `outputs/<run_id>/` and `labeling/` paths.

#### 13. `eval/harness/ollama_check.py` (Create)

*   **Type / Scope**: HTTP checks against Ollama's native API. This is not an
    LLM client: it does not generate text.
*   **Proposed Changes**:
    *   The native root is `OLLAMA_BASE_URL` without its trailing `/v1`.
    *   `check_models(models) -> dict[str, str]` calls `GET /api/tags`. It
        fails with "Ollama model '<tag>' is not pulled (ollama pull <tag>)" or
        "Ollama is not reachable at <url>". Otherwise it returns each model's
        digest.
    *   `is_infrastructure_error(error_text) -> bool` matches "connection
        error", "timed out" or "connection refused", case-insensitive.

#### 14. `eval/harness/adapters/__init__.py` and `eval/harness/adapters/phase1.py` (Create)

*   **Type / Scope**: Adapter registry and the Phase 1 adapter. This is the
    only harness module that imports `src`.
*   **Proposed Changes**:
    *   **Registry:** `get_adapter(name)`.
    *   **`search(topic)`:** awaits `src.pipeline.search.new_main.main` with
        the rendered screener input and `target_output_count=25`, and returns
        a `SearchRecord`.
    *   **`screen(papers, topic)`:** builds a `PipelineState` dict with
        `raw_papers`, `research_question`, `inclusion_criteria`,
        `exclusion_criteria` and `additional_info`, and awaits
        `src.graph.nodes.screening_node`. It maps the four buckets to
        `ScreeningRecord`s by `openalex_id`.
    *   **`retrieve(paper_key, pages)`:**
        *   runs `chunk_pages(pages)` and embeds the chunk texts with
            `embed_texts`
        *   creates an `InMemoryRepository`, upserts the paper, and calls
            `replace_chunks` with `get_settings().embedding_model` and
            `CHUNKER_VERSION`
        *   calls `retrieve_field_chunks`
        *   maps each returned text to the first chunk with identical text
            (page, ordinal); the rank is its position in the returned list
        *   maps the field keys to field names as in the Technical Plan
    *   **`extract(paper, chunks, topic)`:** builds the
        `retrieved_chunks_by_field` dict back from the chunks and awaits
        `extract_from_retrieved_chunks`. It maps the five scored fields with
        `v1_status(value)`.
    *   **`v1_status(value) -> str`:** the mapping in the Technical Plan,
        with the phrases as a module constant.
    *   **Provenance:** `provenance()` returns the prompt versions from
        `src/llm/prompts/*`, `CHUNKER_VERSION` and `RETRIEVAL_TOP_K`.

#### 15. `eval/harness/run.py` (Create)

*   **Type / Scope**: CLI, `python -m eval.harness.run --adapter phase1`.
*   **Proposed Changes**:
    1.  Check that `REPOSITORY_BACKEND=memory`; stop with an error otherwise,
        so a run never touches the library.
    2.  Run `check_models`.
    3.  Load the gold set and the frozen pool. Screen the screening-set
        papers of all topics twice, timing each pass.
    4.  For each extraction-gold paper, load the page text from the data
        folder (checking the hash), then retrieve and extract, timing each
        paper.
    5.  Run `check_models` again, and apply `is_infrastructure_error` to
        every failed record. Either one failing sets status `incomplete`.
    6.  Write the outputs and provenance.
    7.  If the run is complete, call `scoring.score` and write
        `eval/results/<run_id>.json`. Print the run id, the status and the
        reminder to run the sync.

    The latency budget is computed in scoring from `timings.json` and the
    snapshot's `duration_s`.

#### 16. `eval/harness/score.py` (Create)

*   **Type / Scope**: CLI, `python -m eval.harness.score <run_id>`.
*   **Proposed Changes**: Re-scores saved outputs against the current gold
    set and overwrites `eval/results/<run_id>.json`. It writes
    `<data_dir>/outputs/<run_id>/errors.md`, which lists every wrong output
    per agent for the error analysis:
    *   screening misses and hard errors with the model's reasoning
    *   non-relevant top-10 papers
    *   recall misses with the pages that were retrieved
    *   gold `found` fields reported `not_found`, with the model's value

#### 17. `eval/harness/truncation_check.py` (Create)

*   **Type / Scope**: CLI, `python -m eval.harness.truncation_check`.
*   **Proposed Changes**:
    *   Picks the extraction-gold paper with the most retrieved characters.
    *   Calls `get_llm("extraction").chat.completions.create_with_completion`
        with the same messages as `extract_from_retrieved_chunks`, and reads
        `completion.usage.prompt_tokens`.
    *   Counts the same messages with
        `transformers.AutoTokenizer.from_pretrained(<HF id>)` and
        `apply_chat_template`. The HF id comes from a `--tokenizer` argument;
        the default is `Qwen/Qwen2.5-Coder-7B-Instruct`.
    *   Prints both counts. It reports truncation if the Ollama count is
        lower than the tokenizer count by more than 5%.

#### 18. `eval/harness/sync.py` (Create)

*   **Type / Scope**: CLI, `python -m eval.harness.sync`.
*   **Proposed Changes**: In `data_dir()`, it runs `git add -A`, then `git
    commit -m "sync <UTC timestamp>"` (skipped when there is nothing to
    commit), then `git push`. A failure prints git's message and exits
    non-zero. Setting up the private repository is a one-time manual step,
    described in `eval/README.md`.

#### 19. `eval/gold_build/__main__.py` and step modules (Create)

*   **Type / Scope**: CLI, `python -m eval.gold_build <step>`. One module per
    step.
*   **Proposed Changes**:
    *   `freeze_search`: runs adapter `search` per topic and writes
        `search.json` with timing and provenance. It refuses to write when
        `fallback_used` is true.
    *   `build_pool`:
        *   resolves the link list: by DOI through the OpenAlex works
            endpoint, by hand for entries listed in
            `link_list_manual.json`; it writes `link_list.json`
        *   fetches link-list works and formats them with
            `format_openalex_work`
        *   applies the year ≥ 2020 and abstract filters outside the search
            set
        *   removes duplicates with `normalize_title`, preferring a record
            with a journal `venue`, and records aliases
        *   writes `pool.json`
        *   with `--extend <topic>`, calls `OpenAlexClient.execute_retrieval`
            with the frozen `synthetic_abstract`, the same filters and
            `limit=50`, and appends the new papers as `search_extended`
    *   `label_prepare`: writes one input file per pool paper (title and
        abstract only) to `<data_dir>/labeling/inputs/<topic_id>/`, plus the
        rendered prompt and JSON schema.
    *   `label_run`: for each input file without an answer, runs `claude -p`
        with the working directory set to that inputs folder, so this
        repository's `CLAUDE.md` is not loaded. The flags are:
        *   `--model <id>`
        *   `--tools ""`
        *   `--system-prompt <labeling prompt>`
        *   `--json-schema <schema>`
        *   `--output-format json`
        *   `--no-session-persistence`

        The paper text is passed on stdin. Each raw JSON answer is saved to
        `<data_dir>/labeling/answers/`. It records `claude --version` and the
        model id.
    *   `label_import`: writes `screening.json` with source `model` and
        derived decisions.
    *   `select_sets`: the screening-set selection in the Technical Plan,
        with `--seed` (default 2026). It records the seed and skipped papers.
        With `--needs-extension` it reports the topics below 8 includes, which
        `build_pool --extend` then fixes.
    *   `blind_sample`: picks the 7 papers per topic (borderline up to 3,
        then random from the search set) with the seed. It writes
        `<data_dir>/labeling/blind_sheet.csv` (topic, paper key, title,
        abstract, one empty column per check) in shuffled order.
    *   `compare`: reads the filled sheet and writes the agreement counts. For
        every trigger it writes `<data_dir>/labeling/escalation_sheet.csv`
        with the papers in scope (from `decided_by`), the check question, and
        an empty answer column. The model's answers are not shown.
    *   `escalation_import`: applies the escalation answers (confirmed gives
        `model_verified`, changed gives `human`), re-derives the decisions,
        and writes the escalation log.
    *   `extraction_prepare`:
        *   downloads each chosen paper's PDF to `<data_dir>/pdfs/`, hashes
            it, and writes `<data_dir>/pages/<key>.json` with
            `extract_pages_from_pdf` and the PyMuPDF version
        *   runs `claude -p` as in `label_run`, with the pre-fill prompt and
            the page text, and saves the raw answer
        *   runs the quote check and lists failures for a re-run
    *   `extraction_verify`: writes `<data_dir>/labeling/extraction_sheet.csv`
        (field, value, page, quote, an empty verdict). On import, rows marked
        `ok` become `model_verified`, and rows marked `wrong` are dropped from
        the gold set.
    *   `validate`: runs `gold.validate` with the data folder and exits
        non-zero on any problem.

#### 20. `eval/gold/v0/labeling_prompt.md` and `eval/gold/v0/prefill_prompt.md` (Create)

*   **Type / Scope**: Prompts, committed so they can be hashed and audited.
*   **Proposed Changes**:
    *   **Labeling prompt:** answer every check from the title and abstract
        only; `not_stated` when the abstract does not say; one-line reason;
        no outside knowledge about the paper.
    *   **Pre-fill prompt:** for each of the five fields that the page text
        reports, give the value, the 1-based page index of the `PAGE n`
        marker, and one sentence copied character for character from that
        page. Leave out fields the text does not report.

#### 21. `eval/topics/t1_social_media.json`, `t2_llm_mas_eval.json`, `t3_mobile_money.json` (Create)

*   **Type / Scope**: Topic configs.
*   **Proposed Changes**: The questions and checks accepted in
    `docs/eval_notes.md`, as follows. Each check's `yes` and `no` statements
    are written from its question and its stated "no" cases.
    *   **Topic 1:** the 5 checks, with the wellbeing boundary in check 3.
    *   **Topic 2:** the 4 checks.
    *   **Topic 3:** the 5 checks.

#### 22. `eval/README.md` (Create)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**:
    *   Setting up the data folder (create the private repository, clone it,
        set `EVAL_DATA_DIR`).
    *   The gold-build steps in order, with the human steps marked.
    *   The truncation check, the baseline run and re-scoring.
    *   The sync after every run.
    *   What is committed where, and why.

#### 23. `eval/reports/2a_baseline.md` (Create, after the baseline run)

*   **Type / Scope**: Report.
*   **Proposed Changes**: written by hand from the results file and
    `errors.md`. It holds:
    *   the baseline numbers with counts, and the flip count with the
        resulting N for the paired rule
    *   the error analysis: groups per agent, each with a cause and at least
        one example, using short excerpts only
    *   the backlog #37 count
    *   the latency budget, and the smoke-run total for reporting
    *   the truncation result
    *   the labeling summary: label sources, agreement counts and the
        escalation log

#### 24. `eval/snapshots/v1/README.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: replaces "inputs for the Phase 2a baseline" with
    "kept for history; not used by the gold set v0 (see
    `docs/designs/eval.md`)".

#### 25. Tests: `tests/unit/eval/` (Create) and `tests/fixtures/eval/` (Create)

*   **Type / Scope**: Unit tests on the fake surface, with no network, no
    model and no data folder except a temporary one.
*   **Proposed Changes**:
    *   **Fixtures:**
        *   a two-check mini topic
        *   a mini gold set: 2 topics, small set sizes passed to the
            validator
        *   page-text files for the 2 fixture PDFs already in
            `tests/fixtures/`
        *   recorded output files for one complete and one incomplete run
    *   **`test_topics.py`:** `derive_decision` on all answer combinations;
        `decided_by` for include, single-`no` exclude, multi-`no` exclude and
        uncertain; the screener rendering.
    *   **`test_text.py`:** whitespace normalization; title normalization;
        `joined_runs` joining a quote across two consecutive chunks and not
        across pages.
    *   **`test_gold.py`:** each validation problem is reported (a wrong
        derived decision, a missing source, a duplicate title, a quote not on
        its page, a hash mismatch).
    *   **`test_scoring.py`:**
        *   the gold × model table
        *   `uncertain` and `failed` counted as include misses
        *   hard errors
        *   flips
        *   precision@10 with a duplicate in the top-10
        *   recall@5 hits and misses
        *   field status
        *   refusal on an incomplete run
    *   **`test_phase1_adapter.py`:**
        *   `screen` maps all four buckets, including a `[FAKE:FAIL]` paper
        *   `retrieve` returns page and ordinal for every chunk
        *   `extract` maps the fields
        *   `v1_status` on every phrase, on "No empirical dataset", and on a
            real value
    *   **`test_ollama_check.py`:** native-root derivation; the error messages
        for a missing model and an unreachable server, with the HTTP mocked;
        `is_infrastructure_error`.
    *   **`test_run_dry.py`:** the full `run` on the fixture gold set with
        `PROFILE=test` and a temporary data folder (I9 from the review). It
        writes outputs and a results file whose screening numbers match a
        hand-computed expectation.
    *   **`test_gold_build.py`:** `select_sets` is deterministic for a seed
        and respects the mix; `build_pool` removes duplicates and keeps the
        journal version; `blind_sample` and `compare` produce the expected
        sheets and escalation scope.

#### 26. `Makefile` (Modify)

*   **Type / Scope**: Build commands.
*   **Proposed Changes**: Add three targets:
    *   `eval-run` (`REPOSITORY_BACKEND=memory python -m eval.harness.run
        --adapter $(ADAPTER)`, default `phase1`)
    *   `eval-score` (`python -m eval.harness.score $(RUN)`)
    *   `eval-sync` (`python -m eval.harness.sync`)

#### 27. `.github/workflows/ci.yml` and `pyproject.toml` (Modify)

*   **Type / Scope**: CI and lint configuration.
*   **Proposed Changes**:
    *   `ruff check` and `ruff format --check` also cover `eval`.
    *   `pytest` already collects `tests/unit/eval/`.
    *   No live eval runs in CI.

#### 28. `CLAUDE.md` (Modify)

*   **Type / Scope**: Agent documentation.
*   **Proposed Changes**:
    *   Add `eval/` to the layout. It is a harness that imports `src`, and only
        `eval/harness/adapters/` may import it.
    *   Add the eval commands, `EVAL_DATA_DIR`, and the search result's new
        fields.
    *   Replace the line describing `eval/snapshots/v1/` as Phase 2a inputs.

#### 29. `docs/backlog.md` (Modify)

*   **Type / Scope**: Backlog.
*   **Proposed Changes**: the triage accepted by the author:
    *   #10: stays deferred.
    *   #16: closed, covered by the frozen search snapshot (`eval.md`).
    *   #24: phase becomes Phase 4.
    *   #27: closed, the golden test is kept unchanged.
    *   #29: rejected for v0, because provenance lives in the results files;
        phase becomes "when needed".
    *   New row #38: the eval "Later" items, listed in `eval.md` "Future
        Improvements".
    *   After step 8, if truncation is found: a new row for it, as a v1
        finding.

#### 30. `docs/eval_notes.md` and `docs/plan_v2.md` (Modify)

*   **Type / Scope**: Status notes.
*   **Proposed Changes**:
    *   **Eval notes:** the banner says the notes are superseded by
        `docs/designs/eval.md`.
    *   **Plan section 8:** the "Provisional" note is replaced by a pointer to
        `docs/designs/eval.md`.
    *   **Plan Phase 2a:** the first checkbox is ticked when this design is
        committed.

### Verification Plan

*   **Build:** none (Python, no build step).
*   **Unit tests:** `make test` passes. That includes `tests/unit/eval/`, the
    new search and settings tests, and the unchanged golden-transcript test.
*   **Static analysis:** `ruff check src tests eval` and
    `ruff format --check src tests eval`.
*   **Coverage:** every function listed in files 8–17 has at least one unit
    test. There is no percentage target, as elsewhere in the repository.
*   **Live checks, at the Phase 2a exit, each with a committed result:**
    *   `python -m eval.gold_build validate` exits 0 (G1, G3).
    *   `provenance.json` holds the agreement counts and the escalation log
        (G2).
    *   The truncation-check output is recorded in the baseline report (G7).
    *   `make eval-run` finishes with status `complete`, and
        `eval/results/<run_id>.json` is committed (G4, G5, G6).
    *   `make eval-score RUN=<run_id>` reproduces the same results file (G4).
    *   `eval/reports/2a_baseline.md` holds the error analysis, the latency
        budget and N (G8, G9, G10).
    *   `make eval-sync` has pushed the data folder after the run.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
