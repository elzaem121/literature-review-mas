# Evaluation harness — brainstorm notes

> **Status: superseded by `docs/designs/eval.md`, which is the source of truth for the evaluation. This file is kept as the brainstorm record.**
> EGM brainstorm paused 2026-11-11, resumed 2026-11-22. Goldfish review on 2026-11-22 (summary in `docs/reviews/2a_concepts_brief.md`); the author's answers are in "Decisions after the Goldfish review".
> Decisions are marked with their date in each section; earlier positions that were superseded are marked as such. The design doc, not this file, becomes the source of truth once written.

## Scope

Evaluation harness originally planned for Phase 0 (`plan_v2.md` section 8 and the Phase 0 checklist): a small gold dataset for three test topics, and one eval script that measures the baseline and compares candidate local models. It now runs at the start of Phase 2.

## Positions stated during the brainstorm (not final)

These came from the author during the brainstorm. They are recorded as the starting point, not as decisions.

- **Search** is measured live with judge precision@10 and reported separately. It is never used to compare models. *(Superseded 2026-11-22: see "Search precision@10".)*
- **Screening and extraction** run on frozen snapshots: saved paper lists with retrieval date, and saved PDFs/chunks kept outside git.
- **End-to-end runs** are only a smoke test plus latency measurement.
- **Extraction gold per field** = status (`found` / `not_reported`) + evidence page + short quote. Value correctness is scored by the judge against the evidence.
- **One labeling effort:** the gold labels are also the judge calibration set (but see weak point 3).
- **No tool calling in the model benchmark.** The router is benchmarked in Phase 3.
- **Topics** (test cases only; the app is domain-agnostic):
  1. Social media and adolescents — `Screening_Agent/testdaten/review_config.json`
  2. How LLM-based multi-agent systems are evaluated — rewritten as checks on 2026-11-22 (section "Topic 2, rewritten"); replaces `Screening_Agent/review_config_Evaluation.json`
  3. An economics topic whose criteria a non-expert can check from the abstract (candidates below; civil engineering dropped by the author on 2026-11-22)
- **No v1 labels survive.** Labeling starts from zero. Candidate paper sources:
  - topic 1: link list in git history before commit `dcc06b0`
  - topic 2: a fresh search (decided 2026-11-22); the 24 v1 papers in `eval/snapshots/v1/screening_search_results.json` are no longer used for the gold set
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
- **Topic 2's research question and criteria disagree.** (Resolved 2026-11-22: topic 2 rewritten, see "Topic 2, rewritten".)
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

## Topic 3 candidates

The civil engineering candidates from 2026-11-11 (concrete strength prediction, bridge vibration monitoring, recycled aggregate) were dropped by the author on 2026-11-22: topic 3 comes from another field. They remain in git history.

What topic 3 has to add, given the other two:

- Topic 1 is social science and health (social media and adolescents); its sources are nearly all includes.
- Topic 2 is computer science (multi-agent systems); its sources are nearly all excludes, and its question and criteria disagree.
- Topic 3 should therefore come from a third field, have criteria that agree with its question, and have boundary cases that can be decided from title and abstract alone, because screening sees nothing else.

All candidates use `min_year: 2020` and are screening-only in v0.

**Selection rule (author, 2026-11-22).** The author is not a domain expert in any candidate field. Topic 3 must have criteria that a careful non-expert can check from title and abstract alone (population, country or region, data type, outcome measured), and still have real borderline cases. Criteria that ask the labeler to judge study design or quality are out.

**Field: economics (author decision, 2026-11-22).** Rejected candidates:

- Ecology (neonicotinoids and bees in the field) and clinical medicine (intermittent fasting trials): rejected by author; economics chosen as the third field.
- Economics, minimum wage and employment with quasi-experimental designs only: rejected by author, because deciding whether a design is quasi-experimental needs expertise the labeler does not have.

**Open-access check (2026-11-22).** For each candidate, the first 50 OpenAlex results for a keyword search from 2020 on were counted for a PDF link (`best_oa_location.pdf_url`). This is a rough signal of how many included papers could later reach extraction, not a measure of the topic's size.

| Candidate | Top 50 with a PDF link |
| --- | --- |
| E1. Mobile money and household welfare in Sub-Saharan Africa | 32 |
| E2. Cash transfers and children's education in Latin America and the Caribbean | 44 |

Both questions say "relationship", not "effect", so that the question and the criteria agree: neither asks the labeler to judge whether a study shows a causal effect. This avoids the topic 2 problem.

### E1. Mobile money and household welfare in Sub-Saharan Africa

*"What is the relationship between mobile money use and household or individual welfare in Sub-Saharan Africa?"*

- **Include (all must hold):**
  - mobile money: phone-based payment and transfer services such as M-Pesa
  - data from at least one Sub-Saharan African country
  - household- or individual-level data (survey, panel, or field experiment)
  - at least one outcome from this closed list: consumption, savings, income, poverty, food security, health spending or use, schooling, coping with shocks
- **Exclude:**
  - country-level data only (for example a panel of countries' financial development)
  - firm-level data only
  - the only outcome is mobile money adoption or its determinants
  - an outcome not on the list (for example energy poverty, entrepreneurship)
  - data from other regions only
  - reviews, meta-analyses, conceptual papers
- **Borderline cases seen in the first 25 search results:** an adoption experiment ("Adopting Mobile Money: Evidence from an Experiment in Rural Africa"), firm-level data ("Mobile money, traditional financial services and firm productivity in Africa"), country-level data ("Mobile Money is Driving Financial Development in Africa"), an outcome off the list ("Analysis of Mobile Money Innovations and Energy Poverty in Africa"), and a review.
- **Trade-off:** the main boundaries (household versus country or firm data; welfare outcome versus adoption) need the abstract to be read, not a country name spotted. The weak point: some abstracts do not say what level the data is at ("using data from Kenya"), so these papers can only be labeled `uncertain`, or the labeler has to open the paper.

### E2. Cash transfers and children's education in Latin America and the Caribbean

*"What is the relationship between cash transfer programmes and children's education in Latin America and the Caribbean?"*

- **Include (all must hold):**
  - a government or NGO cash transfer programme, conditional or unconditional
  - data from at least one country in Latin America and the Caribbean
  - at least one education outcome for children or adolescents: enrolment, attendance, dropout, grade progression, test scores, years of schooling
  - empirical data (survey, administrative records, or trial)
- **Exclude:**
  - in-kind transfers only (food, vouchers)
  - data from other regions only
  - no education outcome (only health, labour supply, child labour, poverty, or the politics of the programme)
  - reviews, comparative policy essays, theoretical models
- **Borderline cases seen in the first 25 search results:** programmes in other regions (Indonesia, the Philippines, Pakistan), a Latin America and Africa comparison, a child labour trial that may also report attendance, higher-education attainment of former beneficiaries who are now adults, and papers on public opinion about the programmes.
- **Trade-off:** the boundaries are crisp. Conditional versus unconditional is deliberately not a criterion: a non-expert cannot tell from a programme's name (Bolsa Familia, Progresa) whether it is conditional. The weak point is that the most common borderline case is a country name, which any model gets right, so E2 may separate screening models less than E1.

**Decided (author, 2026-11-22): E1.** E2 rejected by author: its most common borderline case is a country name, which may not separate screening models.

## Duplicate versions of one study (rule accepted by author, 2026-11-22)

Working-paper and journal versions of one study can appear as two OpenAlex works with different DOIs. The search results above show it (the same title appears once from a journal and once from a repository), and topic 2's snapshot already has one such pair. The paper upsert merges only by OpenAlex id or normalized DOI, so it keeps both.

Effect on the eval:

- **Screening:** screening runs on the frozen snapshot, which the gold set controls. If both copies stay in, one study counts twice in a 20-paper sample, and if the two abstracts differ, the two labels can legitimately differ.
- **Extraction:** not affected in v0; topic 3 is screening-only, and the extraction papers are picked by hand.
- **Search precision@10:** a duplicate in the top 10 would count as two relevant hits.

Rule:

1. When freezing a snapshot, treat records whose titles are equal after lowercasing and removing punctuation and whitespace as one study.
2. Keep one record: the journal version if there is one, otherwise the first one seen. Record the dropped record's OpenAlex id in the gold file as an alias of the kept one.
3. For search precision@10, count a second copy of a study as not relevant.
4. Report the number of duplicates found per topic. This is the measurement that backlog #19 (external-ID mapping table) waits for.

Merging duplicates in the pipeline itself is not part of Phase 2a.

## How the gold set treats `uncertain` (accepted by author, 2026-11-22)

### What the code does today

- The screening prompt (`src/llm/prompts/screening.py`, `v1`) says: use `uncertain` "if the metadata is insufficient, the abstract is missing, or the paper may be relevant but cannot be judged safely", and "uncertain is better than wrongly excluding a potentially useful paper".
- Ingestion and extraction read only `included_papers` (`src/pipeline/ingestion/node.py`, `src/pipeline/extraction/node.py`). An `uncertain` paper is never downloaded or extracted, so downstream it is lost, the same as an excluded one.
- So the prompt's "be conservative" advice loses papers. This is a finding for the baseline error analysis and the Phase 2b agent review, recorded as backlog #37. Phase 2a does not change it, because the baseline measures the system as it is.
- The model also returns `matched_inclusion_criteria` and `matched_exclusion_criteria` as free text. These are not scored in v0, but the error analysis can compare them with the gold checks below.

### Decision

1. **A gold label states what the title and abstract support, not what the full paper says.** The screener sees only title and abstract, so scoring it against full-text truth would penalize it for information it never had. The labeler does not open the PDF for screening labels. This also saves labeling time.
2. **Labels are recorded as checks, and the decision is derived from them.** Each criterion becomes a yes / no / not stated question about the abstract. For E1:
   - Is the subject mobile money (phone-based payments or transfers)?
   - Does the data come from at least one Sub-Saharan African country?
   - Is the data at household or individual level?
   - Is at least one outcome on the list (consumption, savings, income, poverty, food security, health spending or use, schooling, coping with shocks)?
   - Is it a primary empirical study (not a review, meta-analysis or conceptual paper)?

   Rule: any "no" gives `exclude`; all "yes" gives `include`; otherwise `uncertain`. A non-expert can answer each check, a disagreement points to the exact check, and the error analysis can group screening errors by check.
3. **Sample mix per topic:** 20 papers, 8–12 gold `include`, at most 4 gold `uncertain`. Gold-`uncertain` papers do not count toward the includes. If a topic has more, replace the extra ones with other search results, and report how many were replaced.
4. **Scoring per topic, from a 3×3 table (gold × model):**
   - **Include recall:** share of gold `include` the model labels `include`. A model `uncertain`, `exclude`, or a failed call (`failed_papers`) counts as a miss, because the pipeline passes only `included_papers` on.
   - **Exclude recall:** share of gold `exclude` the model labels `exclude`.
   - **Hard errors:** count of include↔exclude swaps.
   - **Gold-`uncertain` papers:** reported as a count of what the model answered, not scored. With at most 4 per topic, a rate would be noise, and there is no single right answer for them.

   A model that always answers `uncertain` gets include recall 0; one that always answers `include` gets exclude recall 0. Neither can score well by hedging.

### Weak points in this proposal

- **Replacing gold-`uncertain` papers biases the sample toward clear abstracts**, so measured screening quality will be higher than on real search results. Reporting the number of replaced papers shows the size of this bias but does not remove it.
- **The prompt's `uncertain` is broader than the gold rule.** "May be relevant but cannot be judged safely" lets the model answer `uncertain` where the abstract does decide. Under this scoring that is a miss on include recall. This is intended: it measures the cost of the prompt's hedging advice.
- **Topics 1 and 2 have criteria written as prose** in their review configs, not as checks. Using the check format for them means rewriting their criteria as checks for labeling, and for topic 2 that forces open question 3 (question and criteria disagree) to be settled first.

## Topic 2, rewritten (author decision, 2026-11-22)

The v1 question asked how to evaluate multi-agent systems "in an efficient way", while the v1 criteria required safety evaluation and excluded performance and cost. The author resolved this by widening the topic to any kind of evaluation of LLM-based multi-agent systems. The author built an LLM-based multi-agent system and can label this field; formal verification of classic multi-agent systems, which makes up most of the 24 v1 papers, they cannot. So the v1 snapshot is not used for the gold set, and topic 2 gets a fresh search. The snapshot file stays unchanged in `eval/snapshots/v1/`.

*"How are LLM-based multi-agent systems evaluated, and which benchmarks, metrics and methods are used?"*

`min_year: 2020`. Kept from v1 on purpose: papers from 2020–2022 on classic multi-agent systems give near-misses for the "built on LLMs" check.

**Checks** (yes / no / not stated; same rule as E1: any "no" gives `exclude`, all "yes" gives `include`, otherwise `uncertain`):

1. Does the paper study a multi-agent system, with two or more interacting agents? (A single agent, or a standalone LLM, is "no".)
2. Are the agents built on large language models? (Classic agent systems and multi-agent reinforcement learning without LLMs are "no".)
3. Is evaluating such systems the main contribution? "Yes" means a benchmark, dataset, evaluation framework, metric, an empirical study that compares systems, or a failure analysis. Any kind of evaluation counts: performance, safety, reliability, cost. A paper that proposes a new system or method and evaluates it only to show that it works is "no".
4. Is it a primary study (not a survey, review or position paper)?

**Dropped from the v1 config:**

- The exclusion of non-peer-reviewed literature. Most work in this field is on arXiv (17 of the top 50 results below), and the screener sees only title and abstract, not the venue's review status. arXiv also gives reliable PDF links for the extraction gold.
- The robotics hardware exclusion: check 2 covers it.
- `additional_instructions: "Be conservative when excluding papers."` It pushes the model toward `uncertain`, which loses papers downstream (backlog #37), and it would make topic 2 the only topic with extra instructions.

**Search check (2026-11-22):** the first 50 OpenAlex results for "evaluation benchmark LLM-based multi-agent systems" from 2023 on: 39 have a PDF link; 20 are preprints and 23 conference papers. Borderline cases among the first 30:

- Check 1 (single agent): Mobile-Bench, AgentBench, CTFusion, "Evaluating Memory in LLM Agents".
- Check 3 (method with its own experiments, not an evaluation contribution): MAS-GPT, Optima, "Cut the Crap", Dr. MAS. This is the main hard boundary of the topic.
- Check 3 (evaluation study, so "yes" although it proposes no benchmark): "Single-Agent LLMs Outperform Multi-Agent Systems on Multi-Hop Reasoning Under Equal Thinking Token Budgets".
- Check 4: several surveys.
- Duplicates: "Seeing the Whole Elephant" appears twice, so the duplicate rule applies.

**Weak point:** check 3 is a judgment on what the paper mainly contributes, not a fact like a country name. The author can judge it in this field, but the strong labeling model may draw the line differently, so expect most disagreements on check 3. The cross-model disagreement review (section "Proposed changes to the plan") should look there first.

## Topic 1 as checks (accepted by author, 2026-11-22)

v1 config (`tests/fixtures/review_config.json`, same content as `Screening_Agent/testdaten/review_config.json`):

- Question: "How does social media shape adolescents' lifeworlds and everyday experiences?"
- Include: adolescents, teenagers, youth or young people; social media use; everyday life, identity, wellbeing, peer relations or social interaction.
- Exclude: adults only; purely technical recommender systems; marketing performance studies; severe psychiatric treatment studies.
- Extra instruction: "Be conservative when excluding papers."

**Problems a non-expert labeler would hit:**

- "Youth or young people" has no age limit. Many studies use university students aged 18–24.
- "Wellbeing" is open. The social-media-and-depression literature is very large; if depressive symptoms count, includes from a search will be mostly mental-health surveys, and if they do not, a labeler cannot tell where wellbeing ends.
- "Severe" psychiatric treatment needs a clinical judgment.
- The question ("lifeworlds and everyday experiences") is narrower than the criteria (which include wellbeing). This is a milder form of the topic 2 problem.

**Proposed question:** *"How is social media use related to adolescents' everyday life, identity, wellbeing and peer relations?"*

**Proposed checks** (same rule as the other topics):

1. Does the study population include people under 18, or is it described as adolescents or teenagers? (Only university students or adults is "no"; a mixed-age sample that includes under-18s is "yes".)
2. Is social media use studied (named platforms such as Instagram, TikTok, Snapchat, YouTube, or social media in general)? (General screen time, gaming, or internet use without social media is "no".)
3. Is at least one outcome on the list: everyday life, identity, wellbeing, peer relations, social interaction? Depressive and anxiety symptoms in general-population adolescents count as wellbeing (author decision: telling them apart needs clinical expertise the labeler does not have).
4. Is the population a general one, not a clinical sample or a treatment study?
5. Is it a primary study (not a review or meta-analysis)?

Dropped: the recommender-systems and marketing exclusions (checks 1 and 3 cover them), "severe" (check 4 replaces it with a fact), and the extra instruction (backlog #37).

**Consequence of the wellbeing boundary:** a fresh search will return many mental-health surveys, which all pass check 3. If includes are drawn from the search alone, topic 1's includes become one kind of paper. Draw includes from both the v1 link list (mostly qualitative everyday-life studies) and the search, and record each paper's source in the gold file.

**Paper sources:** the v1 link list is nearly all includes. Negatives should come from a fresh search with the new question, so that topics 1 and 2 are built the same way. The v1 extraction snapshot (`eval/snapshots/v1/extract_search_results.json`, 10 papers) shows how off-topic v1's search was for this topic (music streaming, Indigenous health, early marriage): a finding for the baseline search error analysis.

## Labeling model (author decision, 2026-11-22)

Pre-labeling is done by Claude in a Claude Code session, as a one-time task outside the pipeline. Reasons (author): a different model family from the Llama judge, no second free-tier account, and no Groq token limits for whole papers. The gold file records the exact model and the labeling prompt. Groq remains the only outside service the system and the eval harness use, and only for the judge.

### Weak points and mitigations (all six accepted by author, 2026-11-22)

1. **A Claude Code session is not a fixed API call.** The session's own system prompt, the auto-loaded `CLAUDE.md`, earlier conversation, and context compaction all shape the output, and none of it is captured by "model + labeling prompt". Over 60 papers, labels from early and late in a long session may follow different readings of the checks.
   - *Mitigation:* label each paper in a fresh context (one headless call or subagent per paper) that receives only the labeling prompt and that paper's input, and save the raw output per paper. Record the Claude Code version as well as the model id.
2. **Leaking labels between the labeler and the human.** A session inside this repository can read whatever is in it. If the human's blind labels are in the repository when the model labels, the model can see them and the agreement number becomes meaningless. The same applies the other way round: the human must not see the model's labels before finishing the blind sample (already a rule).
   - *Mitigation:* the model labels from a folder that holds only the inputs, and the human's blind labels are kept outside the repository until both sets are done.
3. **The same model family wrote the checks.** The checks and the borderline examples in these notes were drafted with Claude. A Claude labeler will tend to read the checks the way they were written, so model-only labels measure agreement with that reading. The human blind sample is the only independent check, so it carries more weight than before. Check 3 of topic 2 is the most exposed.
4. **Quotes and pages must match what the pipeline sees.** Retrieval recall@k checks whether the gold quote appears in the retrieved chunks. Chunks hold PyMuPDF text, and `page` is the 1-based PDF page index (`src/pipeline/ingestion/chunking.py`), not the printed journal page. If Claude reads the PDF with its own tools, its quotes can differ from the PyMuPDF text (hyphenation, ligatures, line breaks), and its page numbers can be printed page numbers, so recall@k reports misses that are not real.
   - *Mitigation:* give the labeler the frozen PyMuPDF text per page (the extracted-text snapshot) instead of the PDF, ask for the 1-based page index, and check every quote by script: it must appear in that page's text after whitespace normalization. A quote that fails the check goes back to the labeler.
5. **Related, not caused by the labeler: quotes can be split across chunks.** Chunks are 1200-character windows without overlap, so a quote that crosses a window boundary is in no single chunk. Keep gold quotes to one sentence, and count a quote as found if it is in the concatenation of retrieved chunks that are adjacent on the same page.
6. **Gold provenance outside the system's data flow.** The papers sent to Claude are public open-access papers, so this is not user data. But `docs/designs/eval.md` should state that model labels came from Anthropic's model, so "Groq is the only outside service" is read as a statement about the system and the harness, not about how the gold set was made.

## Blind sample and escalation (author decision, 2026-11-22)

v0 is the simplest eval that gives baseline numbers the author can trust. Refinements go to "Later" below.

- **One labeling pass.** Claude labels every paper once (per-paper fresh context, as in "Labeling model").
- **Blind sample of about 20 papers that includes some borderline cases.** *(Refined in `docs/designs/eval.md`, 2026-11-23: 7 papers per topic. Borderline means a "not stated" answer, an exclude with exactly one "no", or, for topic 2, a decision that changes if check 3 changes. The random part is drawn from every topic's search set, not only topic 2's.)* The human labels in shuffled order without seeing model labels.
- **Agreement** is reported as counts per check (for example "check 3: 2 of 5 disagree"), not as weighted percentages.
- **Escalation rule:** if the human disagrees with the model on 2 or more papers for the same check within one topic, the human re-answers that check on every paper of the topic whose decision depends on it. A confirmed answer becomes `model_verified`, a changed one `human`. The time limit is about 20 minutes; papers not reached keep source `model`. *(Refined in `docs/designs/eval.md`, 2026-11-23.)*

## Search precision@10 (author decision, 2026-11-22)

- Phase 2a reports **baseline** search precision@10 only, scored from gold labels, with no judge. Each topic's baseline top-10 is part of its 20 gold papers.
- "Top 10" is the first 10 papers of the search node's output (OpenAlex relevance order after the local filters in `src/pipeline/search/agent.py`).
- Top-10 papers are never replaced. The include target and the cap of 4 gold `uncertain` are met through the other 10 papers.
- The top-10 is frozen with its retrieval date, together with the screening snapshot.
- **No search model benchmark in Phase 2a.** Search problems are logic problems (keyword query, no subfield filter) for the Phase 2b agent review. The search judge and its calibration move to Phase 2b. This replaces the earlier position "search is measured live with judge precision@10".
- Only the extraction faithfulness judge is calibrated in Phase 2a.

## Later (not in v0)

- Label every paper twice in fresh contexts and treat disagreement as a borderline signal.
- Agreement weighted by each stratum's share of all papers.
- Strict and lenient precision@10 (whether gold `uncertain` counts as relevant).
- Noting that precision@10 per topic moves in 10-point steps and cannot separate close search variants.
- After Phase 2b, reporting how many of each top-10 were scored from gold labels and how many by the judge.
- Search judge calibration on human-labeled top-10 papers (Phase 2b).

## Decisions after the Goldfish review (author, 2026-11-23)

The review's full findings and its list of points still to settle are in `docs/reviews/2a_concepts_brief.md`.

1. **One config per topic** generates both the screener's criteria and the labeling prompt, so labeler and screener read the same checks. The screening prompt (`src/llm/prompts/screening.py`, `v1`) stays as is for the baseline.
2. **Prompt truncation:** one logged run checks whether Ollama cuts extraction prompts short. If it does, the context length is set explicitly for all runs, including the baseline, and the truncation goes into `docs/backlog.md` as a v1 finding.
3. **The faithfulness judge moves to Phase 2b**, with the search judge.
   - In Phase 2a, extraction is scored by field status and retrieval recall only.
   - Extraction gold keeps only `found` fields with script-verified quotes.
   - The baseline extraction outputs are saved, so the Phase 2b judge can score baseline faithfulness afterwards and there is still a before/after number. This score is a required Phase 2b task, because hallucination matters to the author (`plan_v2.md` Phase 2b checklist).
   - This supersedes the earlier positions on judge calibration in Phase 2a (open question 5, weak point 3, the Phase 2a part of "Labeling model" point 4).
4. **Paired model-selection rule.** On the same papers, count the gold includes the candidate gets right and the baseline misses (wins), and the reverse (losses). A candidate replaces the baseline only if:
   - wins − losses ≥ N
   - it has no more hard errors and no more failed calls
   - it fits the time and memory limits

   N is set before the benchmark from the number of decisions that flip between two baseline screening runs. The exact gates and the rule for extraction and embedding are settled in `docs/designs/eval.md`.

5. **Phase 2a is minimal** (2026-11-23): gold set, harness, baseline, error analysis, so that Phase 2b starts soon.
   - The candidate-model benchmark and the decision record move to Phase 2b as one of its experiments, measured with the same harness and under the paired rule in point 4. The two baseline screening runs that set N stay in Phase 2a, as the baseline's run-to-run noise.
   - The latency budget is still recorded in Phase 2a, from the baseline run.
   - This supersedes the Phase 2a parts of "Benchmark decides" and "Done means" in "Positions stated during the brainstorm": the comparison table, the decision record and the 45-minute run per candidate model now belong to Phase 2b.
   - No second Goldfish review for this design; the author reviews the draft of `docs/designs/eval.md`.

## Open questions

1. **Answered (2026-11-22):** topic 3 is E1, mobile money and household welfare in Sub-Saharan Africa. Duplicate rule accepted.
1a. **Answered (2026-11-22):** `uncertain` in the gold set as described above: labels judge title and abstract only, decisions are derived from checks, at most 4 gold `uncertain` per topic, and include recall counts `uncertain` as a miss. Topic 2 is rewritten as checks. Topic 1 checks accepted (section "Topic 1 as checks").
2. **Answered (2026-11-22):** Claude in Claude Code, one-time, outside the pipeline (section "Labeling model"); mitigations still to accept. *Original question:* **Labeling model:** which strong model pre-labels? If it is the same model as the judge, is the circularity acceptable, or should the labeler be a different model?
3. **Answered (2026-11-22):** topic 2 rewritten as checks, with a fresh search (section "Topic 2, rewritten"). *Original question:* **Topic 2 mismatch:** change the research question to match the criteria (safety evaluation of LLM-based multi-agent systems), or keep it and accept the noise?
4. **Answered (2026-11-22):** 8–12 gold includes and at most 4 gold `uncertain` per topic; include recall, exclude recall and hard errors instead of plain accuracy (section "How the gold set treats `uncertain`"). *Original question:* **Balancing:** accept a target of 8–12 includes per topic, adding search negatives to topic 1 and positives to topic 2, and report include and exclude recall instead of plain accuracy?
5. **Answered (2026-11-22):** the remaining labeling time goes to escalation and to labeling baseline extraction outputs for the faithfulness judge; baseline search precision@10 comes from gold labels, and the search judge moves to Phase 2b (section "Search precision@10"). *Original question:* **Judge calibration on baseline outputs:** spend part of the 2-hour budget labeling baseline extraction outputs as faithful or unfaithful, and report search precision@10 as uncalibrated in v0?
6. **Answered by `plan_v2.md` (2026-11-13, decision D2):** the baseline is the Phase 1 system with the v1 models (`qwen2.5-coder:7b`, `all-MiniLM-L6-v2`), measured at the start of Phase 2a; only the new adapter is needed. *Original question:* **New with the move to Phase 2:** what is the baseline now? By Phase 2 the code has moved to `src/` (Phase 1). Is the baseline the v1 code on the `v0.1` tag (needs the v1 adapter) or the Phase 1 code with provisional models before any Phase 2 change (needs only the new adapter)?
7. **Answered by `plan_v2.md` (2026-11-13, Phase 2a checklist):** Phase 1 keeps the v1 models, so candidates are compared against them. If the benchmark picks a new embedding model, a Phase 2a task migrates the vector column, re-embeds stored chunks and checks that all chunks share one `embedding_model`. *Original question:* **New with the move to Phase 2:** the benchmark candidates are compared against the provisional Phase 1 defaults (`qwen3:8b`, `nomic-embed-text`). If the embedding model changes, existing chunks need re-embedding and the pgvector column dimension changes (a migration).
