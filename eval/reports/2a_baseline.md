# Phase 2a baseline report

Baseline run `20261127T095143-phase1-4fc1921` (results: `eval/results/20261127T095143-phase1-4fc1921.json`), written
2026-11-27 for the Phase 2b agent review. Design: `docs/designs/eval.md`. The summary of findings with their planned
fix phase is in `docs/findings.md`.

## Summary

The Phase 1 system with the v1 models finds and extracts, but it does not filter.

*   **Screening includes almost everything.** The baseline includes 52 of 60 papers. It finds all 22 gold includes
    (recall 22/22) but excludes only 8 of 36 gold excludes (22%), so 28 of 58 decided papers are hard errors (48%).
*   **Search precision@10 is 12/30 (40%)**: 7/10, 3/10 and 2/10 for the three topics.
*   **Retrieval puts the gold passage in the top 5 chunks for 6 of 29 fields (21%).** Extraction nevertheless reports
    25 of 29 fields as found (86%). Only 5 of those 25 had the gold passage in their context.
*   **One third of the gold includes have no retrievable PDF** (7 of 22), so the pipeline would lose them before
    extraction even with perfect screening.
*   **Extraction dominates the run time**: 98.8 s per paper against 23.7 s for screening. The latency budget is
    1,640 s (27.3 min).

## The run

| | |
| --- | --- |
| Run id | `20261127T095143-phase1-4fc1921`, status `complete` |
| Adapter, commit | `phase1`, `4fc1921` |
| Models (search, screening, extraction) | `qwen2.5-coder:7b-ctx16k`, digest `8db9947d…9a4e` |
| Embedding model, chunker, top-k | `sentence-transformers/all-MiniLM-L6-v2`, `v1` (1,200 characters, no overlap), 5 |
| Prompt versions | search `v1`, screening `v1`, extraction `v1` |
| Concurrency | 3 |
| Gold set | `v0`; frozen searches retrieved 2026-11-24 |

**Context length: the record says `ollama_default`, the real value was 16,384.** The baseline's `provenance.json` and
results file record `context_length: "ollama_default"`. That is wrong. All three roles ran on the derived model
`qwen2.5-coder:7b-ctx16k` (`eval/ollama/Modelfile`, `num_ctx 16384`); the model name in the same record shows it, and
Ollama's `/api/show` confirms `num_ctx 16384` for that model. The field was fixed after the run (commit `30d42ad`: runs
now record the real `num_ctx`). The committed baseline record and its saved outputs are left unedited, and later runs
carry the right value. Re-scoring the saved outputs on 2026-11-27 reproduced the committed results file byte for byte.

## Baseline numbers

### Screening (60 papers, first run)

Gold set: 22 include, 36 exclude, 2 uncertain. Model: 52 include, 8 exclude, 0 uncertain, 0 failed.

Pooled gold × model table:

| gold \ model | include | exclude | uncertain | failed |
| --- | --- | --- | --- | --- |
| include (22) | 22 | 0 | 0 | 0 |
| exclude (36) | 28 | 8 | 0 | 0 |
| uncertain (2) | 2 | 0 | 0 | 0 |

| Topic | Gold include / exclude / uncertain | Include recall | Exclude recall | Hard errors |
| --- | --- | --- | --- | --- |
| t1 social media | 11 / 9 / 0 | 11/11 (100%) | 0/9 (0%) | 9/20 (45%) |
| t2 LLM multi-agent evaluation | 9 / 10 / 1 | 9/9 (100%) | 1/10 (10%) | 9/19 (47%) |
| t3 mobile money | 2 / 17 / 1 | 2/2 (100%) | 7/17 (41%) | 10/19 (53%) |
| **Pooled** | 22 / 36 / 2 | **22/22 (100%)** | **8/36 (22%)** | **28/58 (48%)** |

Hard errors here are gold exclude with model include (28); gold include with model exclude is 0. Both gold
`uncertain` papers were included. Topic 3 has only 2 gold includes, so its include recall carries little weight (the
gold set records this as a mix exception: the frozen search found only 2).

Derived from the table: 22 of the 52 included papers are gold includes (42%).

### Run-to-run noise and N for the paired rule

The two screening passes gave the same decision for all 60 papers: **0 flips** in total and 0 among gold includes. The
reasoning text was identical too (60 of 60), because the screening call uses `temperature=0`
(`src/pipeline/screening/screening_agent.py:180`). The flip count therefore measures that this configuration is
deterministic, not how much a model varies. By the rule in `docs/designs/eval.md`, N = max(0 + 1, 2) = **2**.

**The paired screening rule cannot be met as written.** A win is a gold include that the candidate includes and the
baseline does not. The baseline already includes all 22 gold includes, so wins are 0 for every candidate and
wins − losses ≥ 2 is impossible. The rule has to change before the Phase 2b screening benchmark, for example by
counting gold excludes that the candidate excludes and the baseline does not. This is a decision for the author; the
design document is unchanged.

### Search precision@10

| Topic | Gold includes in the top 10 |
| --- | --- |
| t1 social media | 7/10 |
| t2 LLM multi-agent evaluation | 3/10 |
| t3 mobile money | 2/10 |
| **Pooled** | **12/30 (40%)** |

A second copy of the same study counts as not relevant: that happened once in t1 and once in t3. Per topic, the value
moves in steps of 10 points. The frozen searches returned 19, 25 and 15 papers although 25 were requested.

### Retrieval recall@5 and extraction field status (6 papers, 29 gold `found` fields)

| Field | Gold quote in the retrieved chunks | Baseline reports `found` |
| --- | --- | --- |
| method | 2/6 | 6/6 |
| dataset | 2/6 | 4/6 |
| task | 0/6 | 6/6 |
| main_findings | 0/6 | 5/6 |
| limitations | 2/5 | 4/5 |
| **Pooled** | **6/29 (21%)** | **25/29 (86%)** |

Fields the baseline reports `found` against the retrieval outcome:

| | Gold passage retrieved | Gold passage not retrieved |
| --- | --- | --- |
| Model reports `found` (25) | 5 | 20 |
| Model reports `not_found` (4) | 1 | 3 |

This cross-table was computed from the saved outputs for this report; the results file holds only the two columns
above.

### Timings

| Stage | Time |
| --- | --- |
| Search (frozen snapshot runs) | 42.8 s, 17.9 s, 22.9 s (mean 27.9 s) |
| Screening, one pass of 60 papers | 1,476 s and 1,364 s (mean 23.7 s per paper) |
| Retrieval | 3.2 s per paper (12.3 s for the first paper, probably the embedder loading) |
| Extraction | 98.8 s per paper (29 s to 126 s) |
| Retrieval plus extraction | 102.1 s per paper |

## Latency budget

```text
budget = 27.9 s search + 25 × 23.7 s screening + 10 × 102.1 s retrieval and extraction = 1,640.5 s (27.3 min)
```

The budget leaves out PDF download, Postgres and graph overhead (design, "Latency budget"). Phase 2b must keep one run
with `target_included` = 10 within it. Extraction is 62% of the budget (1,021 of 1,641 s). The
end-to-end smoke run below took 3,093 s (51.5 min), about 1.9 times the budget figure, but with different paper
counts; see that section.

## Cluster run (the reference for Phase 2b)

The same eval was run again on the university cluster's Ollama (one NVIDIA A100 GPU), run
`20261127T160606-phase1-e7f7169` (results: `eval/results/20261127T160606-phase1-e7f7169.json`), with the same gold
set, topics, prompts, models (same base model, `dae161e27b0e`) and the 16k context.

*   **The scores are identical.** Every number in the results file is the same as in the laptop baseline: screening,
    search precision, retrieval recall and extraction field status. Only the run id, commit, start time, model
    digest, context length and timings differ.
*   **Phase 2b uses the cluster run as its reference** for scores and timings. The laptop run above stays as the first
    baseline and is kept for history.
*   **The digest differs** because the 16k model was created again on the cluster; the base model is the same. The
    cluster record also shows the real context length (16,384), where the laptop record shows `ollama_default` (explained
    under "The run").

| Stage | Laptop | Cluster |
| --- | --- | --- |
| Screening, one pass of 60 papers | 1,476 s and 1,364 s (23.7 s per paper) | 106 s and 102 s (1.7 s per paper) |
| Retrieval | 3.2 s per paper | 2.1 s per paper |
| Extraction | 98.8 s per paper | 5.3 s per paper |
| Retrieval plus extraction | 102.1 s per paper | 7.4 s per paper |
| Latency budget (formula above) | 1,640.5 s (27.3 min) | 145.4 s (2.4 min) |

The cluster GPU is shared with other users and the deployment has no storage volume, so timings can vary and the model
must be pulled and created again after a pod restart (`eval/README.md`). The budget on the laptop and the one on the
cluster are both from the harness timings, one run each.

## Truncation (G7)

With Ollama's default context, extraction prompts are cut silently. On 2026-11-27 the check ran on the largest
extraction-gold paper (`W4405090304`, 27,701 retrieved characters): the prompt needs 8,860 tokens, Ollama reported
2,050, so about 77% of the prompt was lost. Every eval run, including this baseline, therefore uses the derived
16k-context model, for which the check reports 8,860 tokens and no truncation. Two consequences:

*   The baseline extraction numbers describe the pipeline *with* a 16k context. The pipeline itself still runs with the
    default context (backlog #38), so it extracts worse than the baseline shows.
*   The check was run on one paper; the other roles' prompts are short and were not measured.

## Error analysis

Sources: `errors.md` (generated by `make eval-score`), the saved outputs, and the gold files. Examples are short
excerpts. The groups state what was observed; causes marked "hypothesis" were not tested.

### Search

18 of the 30 top-10 slots are not gold includes. Counted by the gold check that fails (3 papers fail two checks, so the counts add to 21):

| Group | Slots | Topics | Example |
| --- | --- | --- | --- |
| Not a primary study: review, survey, editorial | 5 | t1 2, t2 3 | t1 rank 9, "Advancing Our Understanding of the Associations Between Social Media Use and Well-Being": an editorial introducing a special issue |
| Single agent where the criteria ask for interacting agents | 3 | t2 | t2 rank 1, "Agent-SafetyBench": evaluates single tool-using agents |
| Country-level or firm-level data where household or individual data is required | 4 | t3 | t3 rank 3, "E-Payment System Adoption…": country-year data, mobile subscriptions rather than mobile money |
| Outcome is not a welfare outcome (for example financial inclusion only) | 3 | t3 | t3 rank 8, mobile money in Mogadishu: the only outcome is financial inclusion |
| Subject is not mobile money, or outside Sub-Saharan Africa | 3 | t3 | t3 rank 6, "Microfinance Institutions… Indonesian Context" |
| Second copy of a study already in the top 10 | 2 | t1, t3 | t1 rank 2, t3 rank 2 |
| Gold `uncertain` | 1 | t2 | t2 rank 8: the abstract does not say that the agents are built on LLMs |

Other observations:

*   The failed checks are mostly about study type, data level and outcome. These are conditions that a semantic query
    built from a "synthetic abstract" cannot enforce, and the keyword filter is bypassed (`CLAUDE.md`, search stage).
    Hypothesis: that is why precision is lowest for t3, whose criteria are mostly such conditions.
*   29 of the 30 top-10 papers come from preprint or repository servers (arXiv, Research Square, PsyArXiv, Qeios,
    medRxiv, Preprints.org, HAL, RePEc); one has no venue. The search keeps only works with a PDF link, which is
    consistent with this, but the cause was not tested.
*   The search returned fewer papers than requested (19, 25, 15 of 25). A later smoke run returned 17 for topic 1, so
    the result also varies between runs.

### Screening

All 28 hard errors are gold excludes that the model included. The model is topical, not criterion-by-criterion: of its
8 exclusions, 7 are t3 papers whose subject is not mobile money and 1 is a survey. It excluded none for study type,
population, data level or outcome in t1 and t2. None of the 52 included papers has any `matched_exclusion`.

Counted by the gold check that fails (4 of the 28 papers fail two checks, so the counts add to 32):

| Group | Papers | Topics | Example (model reasoning) |
| --- | --- | --- | --- |
| Review, survey, editorial or position paper included although the criteria require a primary study | 12 | t1 8, t2 4 | "The paper is a systematic review that includes studies on… which aligns with the inclusion criteria." |
| Single agent included although the criteria require two or more interacting agents | 4 | t2 | ReliabilityBench: "…meets all the inclusion criteria." |
| Outcome is not a welfare outcome | 6 | t3 | "The outcomes include financial inclusion, which aligns with the inclusion criteria." |
| Country-level data included although household or individual data is required | 3 | t3 | Somalia time series 2010–2022: "…making it a primary empirical study" |
| Contribution is a new system, not an evaluation | 3 | t2 | "Adversary-Resistant Multi-Agent LLM System": "introduces a multi-agent system using LLMs and evaluates its performance" |
| Subject is a neighbouring service, not mobile money | 3 | t3 | Mobile broadband in Tanzania: "…which is related to mobile money use" |
| Not social media (smartphone use) | 1 | t1 | "…It examines social media use and wellbeing" for a paper on smartphone use |

The reasoning of included papers cites inclusion criteria only and often says "meets all inclusion criteria". The
screening prompt (`v1`) says "Use include only if the paper clearly matches", yet 52 of 60 were included. Hypothesis: the
model judges topical fit and does not test each criterion; a per-criterion answer in the output schema would show
this directly.

**Backlog #37 (`uncertain` papers are lost downstream):** 0 of 22 gold includes were marked `uncertain`. The model
never used `uncertain` (0 of 60), so #37 did not cost any paper in the baseline. The 2 gold `uncertain` papers were both
included. #37 stays open for the agent review but has no measured effect here.

### Ingestion (backlog #40)

For the 22 gold includes of the screening set, the pipeline's own PDF code (`download_pdf`, then the OpenAlex DOI
lookup from `get_openalex_pdf_url`) was tried once on 2026-11-27:

| Topic | Retrieved | Not retrieved |
| --- | --- | --- |
| t1 social media | 5 of 11 | 6 |
| t2 LLM multi-agent evaluation | 9 of 9 | 0 |
| t3 mobile money | 1 of 2 | 1 |
| **Pooled** | **15 of 22 (68%)** | **7 (32%)** |

Of the 7 failures, 3 returned HTTP 403 (MDPI, ScienceDirect, Preprints.org), 3 returned an HTML page instead of a PDF
(two Springer URLs and one HAL URL), and 1 has no `pdf_url` (its DOI lookup found nothing either). The DOI lookup
rescued none of them. These papers would be flagged `pdf_unavailable` and get no extraction. This was a single attempt
from one machine; a repeat may differ. The check was a script run for this report and is not part of the harness.

### Retrieval

23 of the 29 gold fields were missed (the gold quote is not in the 5 chunks per field). Exclusive groups:

| Group | Misses | Example |
| --- | --- | --- |
| Quote is on page 1 or 2 (abstract, introduction) | 8 | `W4416729275` method, task and main_findings: all on page 2; retrieved pages 3 to 13 |
| Paper is long and the retrieved chunks come from the back | 5 | `W4414975314` (59 pages): all five fields missed, retrieved pages 6 to 58 |
| Quote is on another body page that was not retrieved | 7 | `W7162423762` limitations: page 12; retrieved pages 2, 3, 6, 14, 15 |
| The right page was retrieved but the quote is not in the retrieved chunks | 3 | `W4405090304` dataset: page 10 retrieved as `p10#38`, quote not inside it |

Task and main_findings are never retrieved (0 of 12). Overall 11 of the 23 misses (the first group plus 3 of the long
paper's fields) are quotes on pages 1 and 2. The field queries are keyword lists, for example "research objective aim
purpose research question analytical focus task contribution" (`src/pipeline/ingestion/retrieval.py`); each field gets
5 chunks. Hypotheses, not tested: keyword-list queries do not match the sentences that state a task or a finding;
1,200-character chunks (about 300 tokens) exceed MiniLM's input window (backlog #33), which could explain the 3
right-page misses.

### Extraction

The baseline reports `found` for 25 of 29 gold fields, but this is the model writing a value instead of "not
specified"; it is not correctness. Groups:

| Group | Fields | Example |
| --- | --- | --- |
| `found`, and the gold passage was not in the model's context | 20 | `W4414975314` dataset: "BAD-ACTS dataset"; gold passage on page 6, dataset chunks came from pages 19, 23, 33, 55 and 58 |
| Uninformative value: the method is just "empirical study" (the paper type) | 2 | `W4414975314`, `W7127576860` |
| Task restates the review question instead of the paper's own aim | 3 of 3 in t2 | "evaluation of LLM-based multi-agent systems" |
| `not_found` and the gold passage was not in the context (consistent with a retrieval miss) | 3 | `W7162423762` limitations: "not explicitly specified"; gold passage on page 12, not retrieved |
| `not_found` although the passage was retrieved | 1 | `W4393202030` dataset: "no empirical dataset"; the paper is a protocol, the gold has the planned sample |

The first group is the main risk and cannot be judged without the Phase 2b faithfulness judge: a value may be right
because another passage states it, or invented. The 6 saved extraction outputs (`extraction.json`, with the raw model
output) are the input for that judge. All 6 papers got `paper_type` "empirical study", including the protocol.

## Labeling summary

| | |
| --- | --- |
| Labeling model | `claude-opus-5-5`, Claude Code 2.1.322, labels written 2026-11-24 |
| Screening answers | 440 check answers on 93 papers, all with source `model` |
| Human blind sample | 21 papers (7 per topic), 94 of 98 check answers agreed |
| Disagreements | t1 c5: 1; t2 c1: 1, c3: 1; t3 c4: 1 |
| Escalation | none triggered (the rule needs 2 or more disagreements on one check in one topic) |
| Extraction gold | 29 fields on 6 papers, all `model_verified`; every quote found on its page by the validation script |
| Gold build | `python -m eval.gold_build validate` passed before the baseline run (commit `6c52ec2`) |

How far the numbers can be trusted:

*   The gold screening labels are model labels with a 21-paper human check. Four disagreements in the sample are too few
    to bound the label error, but the main result does not depend on them: 28 wrongly included papers would stay
    far above any plausible number of label errors.
*   Gold excludes in t1 are 8 reviews out of 9; the t1 result is mostly "the screener ignores the primary-study
    criterion". t3 has 2 gold includes. Extraction rates rest on 29 fields from 6 papers, and recall@5 for a field on 5 or
    6 fields.
*   All gold labels judge the title and abstract only, as designed.
*   The baseline input differs from v1's in wording and in the dropped "Be conservative" additional instruction
    (design, "Topic configs"). The v1 screening result on its own configuration was never measured.

## Smoke run (end to end, reporting only)

One run of topic 1 through the API with Postgres, on 2026-11-27 (`POST /start_pipeline`, polled until `completed`). It
used a scratch database on the compose Postgres (so the paper library was not touched), the same derived 16k-context
model for all roles as the baseline, the topic's rendered criteria, `min_year` 2020 and `target_output_count` 25. The
total is for reporting only and does not define the budget.

| Stage | Time | What happened |
| --- | --- | --- |
| Search | 46 s | 17 papers (the frozen snapshot of this topic has 19) |
| Screening | 476 s (28 s per paper) | 16 included, 1 excluded, 0 uncertain, 0 failed |
| Document processing | 50 s | 3 of the 16 included papers had no downloadable PDF (`Download Failed`) |
| Extraction | 2,519 s (194 s per paper) | 13 papers extracted |
| **Total** | **3,093 s (51.5 min)** | status `completed` |

*   **Against the budget.** The budget formula (design) with this run's counts (17 screened, 13 extracted) gives
    46 + 17 × 23.7 + 13 × 102.1 = 1,775 s. The run took 3,093 s. Screening was 18% slower per paper than in the
    baseline (28 s against 23.7 s) and extraction 96% slower (194 s against 98.8 s per paper). The cause was not investigated; this was one run, and machine load and thermal state were not
    controlled. The budget in this report comes from the harness timings, as designed, and the smoke run suggests it is
    optimistic for a real run on this laptop.
*   **Screening again includes almost everything.** 16 of 17 papers were included. This run has no gold labels, so it
    is not scored, but it shows the same pattern as the baseline on a second search of the same topic.
*   **PDF loss in the live pipeline.** 3 of 16 included papers (19%) were lost to download failures, in line with
    finding F4 in `docs/findings.md`.
*   **The API stalled while the pipeline ran.** The status endpoint did not answer within 30 s during extraction,
    which stopped the polling script used for this run (the run itself finished). The Streamlit frontend polls the same
    endpoint. This was seen once and not investigated.
*   The run used the 16k model, so it does not show the production default context (see "Truncation").
