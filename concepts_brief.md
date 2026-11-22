# Phase 2a evaluation harness v0

* **Author:** Mohamed Elsayed
* **Date:** 2026-11-22

## Overview

Phase 2a needs baseline numbers for the Phase 1 system (v1 models: `qwen2.5-coder:7b`, `all-MiniLM-L6-v2`) and a fair way to choose local models for screening, extraction and embedding. v0 is the simplest evaluation that gives numbers the author can trust. It is run by one person, with about 2 hours of labeling, free inference, on a MacBook Air M4 with 16 GB.

- **Gold set:** 60 papers, 20 per topic, across three test topics:
  1. social media and adolescents
  2. how LLM-based multi-agent systems are evaluated
  3. mobile money and household welfare in Sub-Saharan Africa
- **Labels:** yes / no / not stated answers to a few checks per topic, judged on title and abstract only. The decision is derived: any "no" gives exclude, all "yes" gives include, otherwise uncertain.
- **Who labels:** Claude labels every paper once, in a fresh Claude Code context per paper, outside the pipeline. The author blind-labels about 20 papers, including some borderline ones. If the author disagrees with Claude on 2 or more papers for the same check, the author reviews all papers decided by that check.
- **Screening score:** include recall, exclude recall and hard include↔exclude errors. A model `uncertain` counts as an include miss, because the pipeline ingests only included papers.
- **Search score:** each topic's baseline top-10 is part of its 20 gold papers and is frozen with its retrieval date, so baseline precision@10 is scored from gold labels without a judge. No search-model benchmark in Phase 2a.
- **Extraction score:** extraction gold for 6 papers (field status, 1-based PDF page index, a one-sentence quote) is labeled from frozen PyMuPDF text and checked by a script. It gives retrieval recall@k per field and judge-scored faithfulness. The judge is Groq Llama 3.3 70B, calibrated on the author's labels of baseline outputs.
- **Model choice:** candidates are compared under a selection rule written before the runs.

The full record of how each decision was reached is in `docs/eval_notes.md`.

## Analysis

A Goldfish review with seven lenses (design, codebase details, zoom-out, comprehension, implementation readiness, structure, inventive catalyst) read the notes, the plan and the code. Every lens kept the core of the design:

- checks judged on the abstract
- `uncertain` counted as an include miss
- precision@10 from gold labels
- frozen inputs

Their objections fall into four groups.

### 1. Four gaps block implementation

- **What the screener receives is not defined.** Gold labels are checks, but the screener takes a prose `ReviewProtocol` (inclusion list, exclusion list, extra instructions; `src/graph/nodes.py:70-84`). Topic 3 has both prose criteria and checks, and they differ; topic 2 has only checks.
  - Search adds the inclusion criteria to its query (`src/pipeline/search/new_main.py:40-42`). So the frozen top-10 depends on how the checks are written as criteria, and the configs must exist before any search is frozen.
  - Whether the baseline keeps "Be conservative when excluding papers" is also open. The notes drop it, yet also say the baseline measures "the system as it is".
  - The topic-1 config in `tests/fixtures/` feeds the golden-transcript test, so it cannot be edited.
- **Extraction gold does not map onto the v1 schema.** `ExtractedPaperInfo` is eight free-text fields with no status.
  - Absence is written as "not specified", "not explicitly specified" or "no empirical dataset", and the last is ambiguous.
  - `paper_type` has no retrieval query.
  - The v1 output cannot tell `missing` from `not_reported`, yet the Phase 2b exit compares against the baseline on exactly that.
- **The model-selection rule is not written.** The plan requires it before any run. The only draft uses "empty-field share", which is defined nowhere. Also missing:
  - the candidate list
  - hard limits (memory, time, failures)
  - the main metric per role
  - the noise estimate
  - whether one model must serve both screening and extraction to fit in 16 GB
- **No data formats.** The gold file must hold:
  - per-check answers with a label source
  - the derived decision
  - duplicate aliases
  - the paper's origin (link list or search)
  - its top-10 rank and retrieval date
  - the labeling model, Claude Code version and prompt
  - the exact abstract labeled

  The extraction gold, the calibration labels and the results file have no format either.

### 2. Risks that would quietly make the numbers wrong

- **Ollama may cut extraction prompts short without warning.** An extraction call can reach about 30,000 characters of context (5 fields × 5 chunks × 1,200 characters). `get_llm` sets no context length (`src/llm/client.py:27-31`). If Ollama's default context is smaller, the input is cut without an error, and every extraction number measures the cut, differently per model. This has not been tested on the machine.
  - Check: log prompt token counts and pin one context length for all candidates.
- **Infrastructure failures count as model misses.** Any exception lands in `failed_papers`: Ollama down, a model not pulled, a timeout, or bad JSON. A missing model would look like a terrible one. Thinking models (for example `qwen3`) can break JSON mode.
  - Fix: check that every model is reachable before a run. Report structured-output failures separately.
- **The sample can only show large differences.** About 30 gold includes in total means one paper moves include recall by about 3 points, so "within 5 points of the best" is one or two papers. Extraction faithfulness and embedder recall each rest on about 30 values.
  - Fix: report counts next to rates, and state in the decision record that only large gaps can be seen.
- **Run-to-run noise is not measured.** The plan demands a delta larger than noise. v0 runs each model once, with 3 screening calls in parallel.
  - Fix: run baseline screening twice and count how many decisions flip.
- **The labeling budget does not fit.** The notes' own estimates already use about 115 of the 120 minutes before escalation. The reviewers put the real total at about 150–240 minutes. Not counted:
  - Calibrating the faithfulness judge without evidence pointers takes 2–4 minutes per value.
  - Checking a `not_reported` claim means scanning the whole paper.
  - Escalation has no upper limit.
  - Mapping the topic-1 link list to OpenAlex and redoing quotes that fail the script check are not budgeted.
- **The 45-minute run limit holds only under unstated conditions.** It holds for 7–8B models with thinking turned off. Thinking models, Instructor retries, a throttling fanless laptop, Groq calls inside the timed window, or 12–14B models spilling out of memory break it. "Full run per model" is not defined.
- **The embedding benchmark collides with the schema.** The vector column and the fake embedder are fixed at 384 dimensions, so a 768-dimension candidate fails on insert. Running a candidate on Postgres replaces the library's chunks. `get_embedder` loads only sentence-transformers models; `nomic-embed-text` needs query and document prefixes that `embed_texts` cannot add. MiniLM also cuts 1,200-character chunks short (backlog #33), so a candidate with a longer input limit wins partly for that reason.
- **The frozen top-10 can be captured wrong.** Runs store only a count of raw papers. If query expansion fails, search falls back to the raw query and only prints a message.
  - Fix: freeze the synthetic abstract, a fallback flag, the OpenAlex parameters and the raw response with the top-10.

### 3. Rules that conflict or are unclear

- **Escalation** ("2 disagreements on the same check") leaves several things undefined:
  - whether it applies per topic (check 3 means a different thing in topic 1 and topic 2)
  - whether "disagree" means the check answer or the final decision
  - what "decided by a check" means for an include, which every check decides
  - which label source a changed answer gets

  With about 20 blind papers spread over about 14 topic-check pairs, it will rarely fire.
- **Borderline sample.** "Borderline" is defined as a "not stated" answer. Those papers become gold uncertain, which is not scored, so most of the borderline effort goes to unscored papers. The scored labels most likely to be wrong are those that rest on a single check.
- **Sample-building rules can be impossible to satisfy together.** If the top-10 alone breaks the cap of 4 uncertain papers or the 8–12 include target, no rule says what wins. A duplicate pair inside the top-10 leaves 19 unique papers.
- **Smaller items:**
  - precision@10 has no rule on whether gold `uncertain` counts as relevant
  - the blind sample's topic-2-only top-10 draw does not give Phase 2b enough human-labeled top-10 papers
  - the plan says datasets are versioned in `eval/`, while the notes keep PDFs outside git
  - the judge role does not exist in `get_llm`
  - the year cut happens only in search (`pre_excluded=[]` in the screening node), so link-list papers from before 2020 can reach screening
  - Claude Code is not free, which `plan_v2.md` section 11 does not allow for

### 4. Simplifications and transforms the reviewers proposed

- **Take the judge out of the v0 decision path.** The Phase 2b exit uses field status, not faithfulness. Three variants:
  - (a) move the judge to Phase 2b, where extraction cites one evidence chunk and labeling a value takes seconds
  - (b) use the author's faithful/unfaithful labels as the baseline faithfulness score, and the judge only for candidates
  - (c) report the judge's score without using it to choose models

  Each removes most of the Groq quota risk and up to an hour of labeling.
- **Extraction gold holds only `found` fields with a quote the script has verified.** This removes the costly absence checks. Both the Phase 2b exit and recall@k need only `found` fields.
- **Paired selection rule.** On the same papers, count the gold includes the candidate gets right and the baseline misses (wins), and the reverse (losses). Switch only if wins − losses ≥ N, with no more hard errors or failures, within the time and memory limits. Set N from the flip count. This fits the small sample better than comparing percentages.
- **One source per topic.** Store each topic's checks once and generate both the labeling prompt and the screener's criteria from it. Labeler and screener then read the same thing. The cost is that the baseline input differs from v1, which the report must state.
- **Run on the in-memory repository**, one process per candidate, and benchmark each role on frozen inputs instead of a full pipeline run. Keep one end-to-end run for latency.
- **Cache every model call** by model, digest, prompt version and input hash. Fixing a gold label or escalating then means re-scoring, not re-running, and a Groq run that hits its quota can resume.
- **Dry run on the fakes:** `PROFILE=test` exercises the scoring, the status mapping, the quote checker and the duplicate rule before any 45-minute live run.
- **Make Claude's bias visible:** report every screening metric on all 60 papers and on the human-checked subset. Put topic-1 link-list papers that Claude excludes into the blind sample.

**Ideal Final Result.** The gold set and the metrics come from things the eval produces anyway: the Claude pass, the baseline run, candidate runs and the author's labels. The author spends time only where these disagree. Two limits remain whatever the design: the blind sample is the only independent signal, and 60 papers can only show large differences.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Baseline numbers for the Phase 1 system with the v1 models: screening (include recall, exclude recall, hard errors), search precision@10 from gold labels, retrieval recall@k per field, extraction field status, and extraction faithfulness if kept in v0.
  * A gold set of 60 papers over three topics, labeled with abstract-only checks, with a recorded label source per answer.
  * A benchmark of candidate local models for screening and extraction, and possibly embedding, under a selection rule written before the runs.
  * A results file per run in `eval/results/`, a short baseline report, a decision record for the model per role, and a latency budget.
  * Input for the Phase 2a error analysis and the Phase 2b agent review (for example backlog #37: `uncertain` papers are never ingested).
* **Out-of-Scope Non-Goals:**
  * A search-model benchmark and the search judge (moved to Phase 2b).
  * Router evaluation (Phase 3).
  * Changing pipeline behavior during Phase 2a. The baseline measures the system as it is.
  * Merging working-paper and journal duplicates in the pipeline.
  * Double labeling, weighted agreement, strict and lenient precision, and the other items on the "Later" list in `docs/eval_notes.md`.
  * A LangSmith experiment as a required output. The local results file is the record.

## Alternatives Weighed

* **Civil engineering as topic 3** (concrete strength prediction, bridge vibration monitoring, recycled aggregate): rejected by the author. They have forgotten most civil engineering details, so their labels would not be expert labels.
* **Ecology (neonicotinoids and bees) and clinical medicine (intermittent fasting trials) as topic 3:** rejected by the author; economics chosen.
* **Minimum wage and employment, quasi-experimental studies only:** rejected by the author. Judging whether a design is quasi-experimental needs expertise the labeler does not have.
* **Cash transfers and children's education in Latin America:** rejected by the author. Its most common borderline case is a country name, which may not separate screening models.
* **Keeping the v1 topic-2 question and criteria, or rewriting them to fit the 24 v1 papers:** rejected by the author. The question and criteria disagreed, and the v1 papers are mostly formal verification of classic multi-agent systems, which the author cannot label. Topic 2 now covers any kind of evaluation of LLM-based multi-agent systems, with a fresh search.
* **Gold labels judged against the full paper:** rejected by the author. The screener sees only title and abstract, so full-text labels would penalize it for information it never had.
* **Groq Llama as the pre-labeling model:** rejected by the author. It would be the same model as the judge, and the free tier's token limits are too tight for whole papers. Claude in Claude Code was chosen instead.
* **Labeling extraction gold from the PDF:** rejected by the author. The quotes and page numbers would not match the PyMuPDF text the chunks hold.
* **A purely random blind sample:** rejected by the author. The blind sample is the only independent check, so it must include borderline cases.
* **Double labeling, weighted agreement, strict and lenient precision in v0:** rejected by the author as too much detail for v0; moved to the "Later" list.
* **A search-model benchmark and a search judge in Phase 2a:** rejected by the author. Search problems are logic problems for the Phase 2b agent review, and the judge moves to Phase 2b.
* **Reporting search precision@10 as uncalibrated:** rejected by the author. Search precision matters to them, so baseline precision@10 is scored from gold labels on the frozen top-10.

## Key Decisions & Staging for Next Steps

**Decided (2026-11-22, author):**

1. Topic 3 is mobile money and household welfare in Sub-Saharan Africa, with five checks.
2. Topic 2 is how LLM-based multi-agent systems are evaluated, with four checks and a fresh search. `min_year: 2020` is kept, so that classic multi-agent papers serve as near-misses.
3. Topic 1 has five checks. Depressive and anxiety symptoms in general-population adolescents count as wellbeing. Includes come from both the v1 link list and a fresh search.
4. Gold labels judge title and abstract only, and the decision is derived from the checks. Each topic has 8–12 includes and at most 4 gold `uncertain`.
5. Duplicate rule: one study per normalized title. Keep the journal version and record the dropped id as an alias.
6. Screening is scored with include recall (model `uncertain` and failures count as misses), exclude recall and hard errors.
7. Claude pre-labels in one pass, in a fresh context per paper, from an inputs-only folder, using frozen PyMuPDF text and 1-based page indexes. A script checks every quote.
8. The blind sample has about 20 papers, including some borderline ones. Escalation: 2 or more disagreements on the same check means the author reviews all papers decided by that check.
9. Baseline search precision@10 is scored from gold labels. Top-10 papers are never replaced and are frozen with their retrieval date. There is no search benchmark in Phase 2a; the search judge moves to Phase 2b. `plan_v2.md` is updated to match.
10. Backlog #37 records that papers screened `uncertain` are never ingested.

**To settle before or during `/egm-draft`** (from the Goldfish review):

1. What the screener receives: configs generated from the checks, or the v1 configs? Is "Be conservative" kept? Where do the three configs live?
2. The model-selection rule: candidate list, hard limits, the main metric per role, a paired or absolute margin, the noise estimate, and the memory pairing.
3. Whether the faithfulness judge is in v0, and if so: what it sees, the calibration size, the pass threshold, and what happens if calibration fails.
4. Which fields the extraction gold holds (only `found`?), how `paper_type` and "no empirical dataset" are treated, and how the 6 papers are chosen.
5. The exact wording of the escalation rule and of the borderline definition, including a time cap.
6. Which rule wins when the frozen top-10 breaks the sample mix. Whether precision@10 counts gold `uncertain` as relevant.
7. What a "full run" inside 45 minutes is: thinking off, a pinned context length, the judge outside the timed window.
8. Whether the embedding benchmark stays in Phase 2a, given the 384-dimension column and the dependence of extraction context on the embedder.
9. Where snapshots live (in `eval/`, or outside git with hashes), and whether Claude Code and OpenAlex are named as exceptions to "free only" and "Groq is the only outside service".
10. Whether the "Later" list moves into `docs/backlog.md`, and the decisions on the backlog items tagged for Phase 2a: #10, #16, #24, #27 and #29.

**Suggested shape for `docs/designs/eval.md`:** goals and non-goals, decision register, topics and checks, gold-set construction steps, labeling protocol, data formats, snapshots, metrics (including how failed papers are scored), judge, harness contract, model-selection rule, error analysis, budget (labeling minutes and compute), alternatives, risks, and a definition of done matched item by item to the Phase 2a exit in `plan_v2.md`. After that, `docs/eval_notes.md` becomes history.
