# Evaluation harness — brainstorm notes

> **Status: draft, no decisions yet, input for Phase 2.**
> Paused EGM brainstorm (2026-11-11). Nothing here has been reviewed by Goldfish reviewers or turned into a design doc.
> When Phase 2 starts, resume the brainstorm from this file, settle the open questions, and only then write `docs/designs/<eval>.md`.

## Scope

Evaluation harness originally planned for Phase 0 (`plan_v2.md` section 8 and the Phase 0 checklist): a small gold dataset for three test topics, and one eval script that measures the baseline and compares candidate local models. It now runs at the start of Phase 2.

## Positions stated during the brainstorm (not final)

These came from the author during the brainstorm. They are recorded as the starting point, not as decisions.

- **Search** is measured live with judge precision@10 and reported separately. It is never used to compare models.
- **Screening and extraction** run on frozen snapshots: saved paper lists with retrieval date, and saved PDFs/chunks kept outside git.
- **End-to-end runs** are only a smoke test plus latency measurement.
- **Extraction gold per field** = status (`found` / `not_reported`) + evidence page + short quote. Value correctness is scored by the judge against the evidence.
- **One labeling effort:** the gold labels are also the judge calibration set (but see weak point 3).
- **No tool calling in the model benchmark.** The router is benchmarked in Phase 3.
- **Topics** (test cases only; the app is domain-agnostic):
  1. Social media and adolescents — `Screening_Agent/testdaten/review_config.json`
  2. Evaluating multi-agent systems — `Screening_Agent/review_config_Evaluation.json`
  3. A civil engineering topic (candidates below)
- **No v1 labels survive.** Labeling starts from zero. Candidate paper sources:
  - topic 1: link list in git history before commit `dcc06b0`
  - topic 2: the 24 papers in `Screening_Agent/search_results.json`
  - topic 3: a fresh search
- **Labeling:** one person, about 2 hours, model-assisted.
  - A strong model (not the model under test) labels all screening papers and pre-fills extraction fields with quote and page.
  - The human blind-labels a random sample of 15–20 screening papers without seeing the model's labels; agreement is measured. The human decides all disagreements.
  - For extraction, the human checks each pre-filled value against its quote and page.
  - Every label records its source: `human`, `model`, or `model_verified`.
- **Size:** 20 screening papers per topic (60 total); extraction gold for 3 papers each in topics 1 and 2 (6 papers); topic 3 is screening only in v0.
- **Benchmark decides:** one model per role (screening, extraction), plus the embedding model.
- **Judge** only where needed: extraction value faithfulness and search precision@10. Screening accuracy and field status are scored deterministically against gold labels. Judge model: Groq llama-3.3-70b if the free tier allows it, otherwise another free 70B-class model; temperature 0; versioned prompt; report human–judge agreement before trusting it.
- **Harness shape:** a thin adapter per pipeline version (e.g. `eval/adapters/v1.py` with `screen()` and `extract()`); a later adapter is added for the new code; the harness itself does not change.
- **Done means:**
  - one command runs the eval for a given model
  - one results file per run in `eval/results/`, plus a LangSmith experiment
  - a short baseline report in markdown
  - a comparison table for the benchmark models
  - a full run for one model finishes in under about 45 min on a MacBook Air M4 with 16 GB RAM
  - the model choice is written down as a short decision record

## Findings from the sources

- **Topic 1 link list** (`git show dcc06b0^:Testdatensatz/link.md`):
  - About 35 links, hand-picked by the v1 team, so almost all are likely includes.
  - Several are ResearchGate or publisher URLs rather than DOIs, so they need mapping to OpenAlex IDs.
  - Some may have no open-access PDF.
  - The same commit also contains `Testdatensatz/PDF_files_for_dataset.zip` (29 MB), probably the v1 PDFs. It could serve as a ready-made frozen extraction snapshot for topic 1.
- **Topic 2 papers** (`Screening_Agent/search_results.json`):
  - 24 papers. The file is gitignored, so it exists only on one machine, and the only record of when it was retrieved is the file timestamp (June 28).
  - Most papers are about formal verification and model checking of multi-agent systems, so most will be excludes under the safety-focused criteria.
  - Three papers are from 2019. v1's year prefilter (min 2020) removes them before the LLM sees them.
  - One paper appears twice ("An Abstraction-based Method to Check Multi-Agent Deep Reinforcement-Learning Behaviors").
- **Topic 2's research question and criteria disagree.**
  - The question asks how to evaluate multi-agent systems "in an efficient way".
  - The criteria require safety evaluation and exclude "purely performance-based metrics or cost optimization".
  - A labeler following the criteria and one following the question will disagree. That is gold-set noise, not an error by the model under test.
- **v1 extraction schema** (`extract_agent/extraction_schemas.py`):
  - Fields: `paper_type`, `method`, `dataset`, `task`, `main_findings`, `limitations`, `relevance_to_research_question`, `confidence`.
  - There is no field status. A status has to be inferred from strings like "not specified" and "not explicitly specified".
- **v1 quality numbers** in `README.md` (precision@10 > 0.85, 95%, 90%) have no data, script or labels behind them. They cannot serve as a baseline.

## Weak points in the stated positions

1. **Class imbalance makes accuracy meaningless.**
   - Topic 1 sources are nearly all includes; topic 2 sources are nearly all excludes.
   - A model that says "include" for topic 1 and "exclude" for topic 2 scores well without screening anything.
   - Each topic's 20 papers needs a target mix, for example 8–12 includes.
   - Report include recall and exclude recall separately, not plain accuracy.
   - Papers removed by the year prefilter belong in no bucket, or in a separate deterministic check.
2. **Most screening labels would measure agreement with the labeling model, not correctness.**
   - About 40 of the 60 labels would be `model`-only.
   - Scoring a 7–8B model against them measures agreement with a 70B model. The report must say so.
   - If the labeling model and the judge are the same model, judge calibration becomes partly circular. Only `human` and `model_verified` labels count as calibration data.
3. **The extraction calibration set has no wrong answers.**
   - If every gold value is verified correct, there is no way to measure whether the judge catches unfaithful values.
   - The faithfulness judge has to be calibrated on system outputs that contain errors, for example baseline extractions on the 6 papers, each labeled faithful or unfaithful by the human.
4. **The sample is too small to separate close models.**
   - About 6 papers × 5–6 fields ≈ 36 judged values per model. A difference of 3–4 values is within run-to-run noise.
   - n = 60 screening papers gives a 95% interval of roughly ±8–10 points on accuracy.
   - Write down the decision rule before running, for example: "smallest model within 5 points of the best on screening include-recall, and no worse than the best on empty-field share".
5. **The labeling budget is tight.**
   - 20 blind screening labels ≈ 40 min.
   - Checking about 36 extraction fields ≈ 45 min.
   - Labeling baseline extraction outputs for judge calibration ≈ 30 min.
   - That fills the 2 hours. Search judge calibration does not fit, so search precision@10 would be reported as uncalibrated in v0.

## Proposed changes to the plan

- **Score retrieval separately using the gold quotes.**
  - Measure whether the retrieved context for a field contains the gold quote (recall@k per field). No judge is needed.
  - This is the metric for choosing the embedding model, which otherwise has nothing to be measured on.
  - It also splits extraction failures into "retrieval never surfaced it" and "the LLM missed it".
- **Freeze two snapshot levels:**
  - extracted text, as input to the embedding and retrieval benchmark
  - retrieved context per field, as input to the extraction-model benchmark, so only the model changes
- **Use cross-model disagreement to pick what gets reviewed again.**
  - After benchmark runs, look again at gold labels where every candidate model disagrees with the gold.
  - This cheaply catches errors in model-made labels. It misses cases where the gold and all models are wrong together; the report must say so.
- **Keep the local results file as the source of truth; the LangSmith upload is optional.**
  - The harness then works offline and when free-tier limits are hit.
  - CI does not depend on LangSmith being available.
- **The embedding dimension decision is less locked-in than it looks.**
  - The plan already stores `embedding_model` per chunk, and re-embedding a small library is cheap.
  - Choose on retrieval recall@k, but do not let this decision block schema work.
- **v1 status inference needs its own test.** The v1 adapter maps "not specified"-style strings to `not_reported`. That mapping is a source of error and needs a small unit test.
- **Leave fields without evidence out of the extraction gold.** `relevance_to_research_question` and `confidence` have no evidence page.

## Topic 3 candidates (civil engineering)

All use `min_year: 2020` and are screening-only in v0.

### A. Machine-learning prediction of concrete compressive strength

*"How accurately do machine-learning models predict the compressive strength of concrete, and which input features matter most?"*

- **Include:**
  - ML or deep-learning models predicting concrete compressive strength
  - reports a quantitative accuracy metric
  - uses experimental mix-design data
- **Exclude:**
  - only physical lab testing, with no predictive model
  - other materials (asphalt, steel, soil)
  - only durability properties
- **Trade-off:** a large, uniform literature, so screening is easy. Clear `method` and `dataset` fields make it useful for extraction later.

### B. Vibration-based structural health monitoring of bridges

*"How effective are vibration-based deep-learning methods for damage detection in bridges under real operating conditions?"*

- **Include:**
  - bridge structures
  - vibration or acceleration data
  - data-driven or deep-learning damage detection
  - validated on a real structure or a full-scale test
- **Exclude:**
  - only numerical or FE simulation, with no real data
  - buildings, wind turbines or pipelines
  - only non-vibration methods (visual inspection, crack images)
- **Trade-off:** many borderline cases (lab beam vs. real bridge, simulation plus a small field test). It is the hardest screening test, which is what separates screening models.

### C. Recycled concrete aggregate in structural concrete

*"How does replacing natural aggregate with recycled concrete aggregate affect the mechanical and durability properties of structural concrete?"*

- **Include:**
  - recycled concrete aggregate (coarse or fine)
  - measures mechanical or durability properties
  - experimental study
- **Exclude:**
  - non-structural uses (road base, fill)
  - only other recycled materials (glass, plastic, rubber)
  - only life-cycle or cost analysis, with no material testing
- **Trade-off:** medium difficulty. The "other recycled materials" boundary gives useful near-misses.

**Brainstorm leaning:** B, because topics 1 and 2 already cover an easy topic and one with mismatched criteria, and B adds hard boundary cases. Not decided.

## Open questions

1. **Topic 3:** A, B or C, or a variant with different criteria?
2. **Labeling model:** which strong model pre-labels? If it is the same model as the judge, is the circularity acceptable, or should the labeler be a different model?
3. **Topic 2 mismatch:** change the research question to match the criteria (safety evaluation of LLM-based multi-agent systems), or keep it and accept the noise?
4. **Balancing:** accept a target of 8–12 includes per topic, adding search negatives to topic 1 and positives to topic 2, and report include and exclude recall instead of plain accuracy?
5. **Judge calibration on baseline outputs:** spend part of the 2-hour budget labeling baseline extraction outputs as faithful or unfaithful, and report search precision@10 as uncalibrated in v0?
6. **Answered by `plan_v2.md` (2026-11-13, decision D2):** the baseline is the Phase 1 system with the v1 models (`qwen2.5-coder:7b`, `all-MiniLM-L6-v2`), measured at the start of Phase 2a; only the new adapter is needed. *Original question:* **New with the move to Phase 2:** what is the baseline now? By Phase 2 the code has moved to `src/` (Phase 1). Is the baseline the v1 code on the `v0.1` tag (needs the v1 adapter) or the Phase 1 code with provisional models before any Phase 2 change (needs only the new adapter)?
7. **Answered by `plan_v2.md` (2026-11-13, Phase 2a checklist):** Phase 1 keeps the v1 models, so candidates are compared against them. If the benchmark picks a new embedding model, a Phase 2a task migrates the vector column, re-embeds stored chunks and checks that all chunks share one `embedding_model`. *Original question:* **New with the move to Phase 2:** the benchmark candidates are compared against the provisional Phase 1 defaults (`qwen3:8b`, `nomic-embed-text`). If the embedding model changes, existing chunks need re-embedding and the pgvector column dimension changes (a migration).
