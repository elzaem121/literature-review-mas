# Phase 2b Block A — Setup and judges

Author: Mohamed Elsayed
Date: 2026-11-28

## Overview

Block A prepares everything Phase 2b's experiments depend on, before any experiment runs:

1. **Context length fix (backlog #38).** Ollama silently cuts prompts at about 2,050 tokens. The derived model `qwen2.5-coder:7b-ctx16k` (`eval/ollama/Modelfile`, `num_ctx 16384`) becomes the pipeline default. A startup check reads `num_ctx` through Ollama's `/api/show`. A make target re-creates the derived model after a cluster pod restart. The shared cluster deployment stays as it is. The owner treats this as a fix with a test, not as an experiment.
2. **One decision rule for every Phase 2b experiment.** A change "improves" a metric when wins minus losses is at least 2, counted paper by paper or field by field against the cluster baseline. It makes another metric "worse" when losses minus wins is at least 2. The rule also amends the screening model-selection rule so that it counts gold excludes (backlog #41). The macOS memory gate is dropped. The latency budget is the slowest of 3 cluster baseline runs times 1.2.
3. **Extraction judge** under `eval/`. It scores faithfulness (is the value supported by the chunks the model saw) and correctness (does it match the gold quote) separately. It is calibrated against about 30 owner hand labels and passes at 85% or better agreement, provided it also catches most of the values the owner labels unfaithful. It runs on Groq if the free tier covers the volume, and otherwise on a larger non-qwen model on the cluster's Ollama.
4. **Search judge.** The Phase 2a gold labeler (`eval/gold_build/claude_cli.py`, Claude CLI, `claude-opus-5-5`) is reused for new papers only. Results are cached and token cost is reported per run.
5. **Done when:** the #38 fix and its test are in, the rule and its tests are in, the latency budget is recorded, the faithfulness judge reaches at least 85% agreement, and baseline faithfulness and correctness numbers are reported.

> **Revised after the Goldfish review (owner, 2026-11-28).** Items 2, 3 and 4 above are the hypothesis as reviewed. The owner's answers in "Key Decisions" replace them: a per-metric rule table with a hard include gate; calibration from synthetic negatives plus one normal run; a cluster judge as primary with Groq as fallback; the search judge moved to Block B. The done criterion is now at least 26/30 agreement and at least 7/8 unfaithful values caught.

Seven reviewer lenses ran (design, codebase-details, zoom-out, comprehension, implementation-readiness, structural, inventive-catalyst). This brief merges what they found.

| Reviewer | Status |
| --- | --- |
| `egm-design` | completed |
| `egm-codebase-details` | completed |
| `egm-zoom-out` | completed |
| `egm-comprehension` | completed |
| `egm-implementation-readiness` | completed |
| `egm-structural` | completed |
| `egm-inventive-catalyst` | completed |

## Analysis

The findings are grouped by subject and ranked Blocker, Major or Nit. A finding that several lenses raised is listed once, with every lens that raised it.

### Facts established from the repository

- **The cluster baseline already ran at 16k context.** `eval/results/20261127T160606-phase1-e7f7169.json` records `context_length: 16384` and model `qwen2.5-coder:7b-ctx16k`. The #38 fix therefore moves the pipeline onto the configuration the baseline already measured. The baseline does not need a re-run, and no eval metric is expected to move. (implementation-readiness, codebase-details)
- **Extraction gold.** 6 papers, 29 gold `found` fields (method 6, dataset 6, task 6, main_findings 6, limitations 5). One run produces 6 × 5 = 30 values. In the baseline, 25 of the 29 gold fields came back `found` and 4 `not_found`. For 20 of the 25 `found` values, the gold passage was not in the model's context.
- **Prompt size.** The largest extraction prompt is 8,860 tokens (paper `W4405090304`). A prompt holds up to 25 chunks of 1,200 characters.
- **Screening gold.** The screening set has 60 papers: 22 include, 36 exclude, 2 uncertain. Every label came from Claude. The only human check is a 21-paper blind sample, where 94 of 98 check answers agreed.
- **Search.** 3 topics × top-10 = 30 slots, and precision@10 is 12/30. Every baseline top-10 paper already has a gold label.
- **The harness never re-runs search.** `eval/harness/run.py:209-284` has no search step, and precision is scored from frozen snapshots (`scoring.py:188-212`).
- **The `/api/show` reader already exists.** It is `configured_context_length` in `eval/harness/ollama_check.py:56-69`, with tests. `native_root` derives the native URL by stripping `/v1` from `OLLAMA_BASE_URL`.
- **Token usage is discarded.** `extract_from_retrieved_chunks` calls `.create()`, so `usage.prompt_tokens` is not kept (`src/pipeline/extraction/node.py:14-29`).
- **`run_claude` has no cache of its own.** `label_run` skips a paper when its answer file exists, keyed by topic and paper only. `modelUsage` and cost are saved but never read.

### Blockers

**B1. The decision rule cannot be turned into code as written.** (all 7 lenses)

- **Units differ by metric.**
  - Screening counts papers.
  - Retrieval, extraction status and correctness count gold fields.
  - Faithfulness counts only `found` values, so its denominator moves with the candidate: a candidate that abstains more often looks more faithful.
  - Search precision@10 cannot be paired, because a changed search returns different papers.
  - Latency, failed calls and hard errors are gates, not win/loss counts.
- **"Another metric" is not enumerated**, so the rule can be read after the fact.
- **The rule conflicts with the existing text:**
  - The plan says "no other metric gets worse" (`plan_v2.md:244`, `experiments_2b.md:4-5`, `AGENTS.md`), while "losses − wins ≥ 2" tolerates a net loss of 1.
  - The eval design's gates allow no more hard errors or failed calls than the baseline (`eval.md:635-636`).
  - The eval design sets the threshold as N = flips + 1, at least 2, which the new rule replaces with a fixed 2.
  - The eval design's faithfulness gate is tied to the judge's own repeat-run difference (`eval.md:642-644`), which the new rule does not mention.
- **The #41 amendment, pooled, trades includes for excludes.** A candidate that gains 5 excludes and loses 3 of the 22 gold includes nets +2 and "improves". Backlog #41 itself asks for a gate against new missed includes. For a literature review, a lost include costs more than a kept exclude.
- **The reference is unclear.** If every experiment is compared with the frozen baseline, earlier kept changes are mixed into later experiments, and tolerated −1 losses add up unseen.

Recommendation: write one committed metric table. Each row gives the unit, the population, the win, the loss, and whether the metric is a target or a gate. Lens proposals for its contents:

- **Screening:** include and exclude counted as two separate metrics. Gold-uncertain papers are excluded. A model `uncertain` on a gold exclude is "not excluded". A hard gate of 0 new gold-include misses (the owner chooses 0 or 1).
- **Search:** the per-topic difference in relevant slots, marked as unpaired.
- **Faithfulness:** counted only on fields that both runs report `found`, with the `found` count kept as a separate guard. The alternative is one ordered outcome per field: correct-and-faithful > faithful-but-wrong > `not_found` > unfaithful. That alternative turns three metrics into one and ranks a made-up value below abstaining.
- **Latency, failed calls, hard errors:** gates.

Each experiment names its target metric before it runs. A comparison tool (`eval/harness/compare.py` plus `make eval-compare BASE= CAND=`) prints wins, losses and the verdict, and its output goes into the `experiments_2b.md` row. That way two people get the same answer.

**B2. The calibration run with "default 2,050-token context" probably does not produce what it is meant to.** (design, codebase-details, zoom-out, comprehension, implementation-readiness, structural, inventive-catalyst)

- **Truncation removes the instructions.** Ollama keeps the end of the prompt, so the system prompt, the JSON instructions and most chunks are lost. The likely result is Instructor failures or obviously broken values, not the subtle unfaithfulness seen in the baseline.
- **"Chunks the model saw" is undefined.** `retrieval.json` stores all retrieved chunks, but the model saw only the tail. A judge given every chunk would mark values faithful that the model never had support for.
- **The 2,050 figure may not hold on the cluster.** It was measured on the laptop with Ollama 0.34.4. The cluster runs the unpinned `ollama/ollama:latest` image (`deploy/NOTES.md:12`), and newer releases may size the default context by GPU memory.
- **The labels would come from a different population** than the baseline the judge is later reported on.

Recommendation, if the owner keeps the extra run:

- Pin its config explicitly, for example `Modelfile.ctx2k` with `num_ctx 2048`.
- Confirm with `truncation_check` on the cluster first that it truncates and still returns valid JSON.
- Rebuild the exact text the model saw with the Qwen tokenizer from `truncation_check.py`.
- Define faithfulness as "supported by the text actually in the prompt".

Three cheaper ways to get unfaithful examples (inventive-catalyst):

- Judge paper A's values against paper B's chunks.
- Remove the chunk that holds the support (leave one out).
- Perturb a number or negate a finding.

All three are built from saved outputs, with no extra model run and no extra owner time.

**B3. The search judge is circular and has nothing to do in Block A.** (all 7 lenses)

- **Calibrating it against the Phase 2a gold labels is circular.** Those labels were made by `claude-opus-5-5` with the same prompt, so the check measures repeatability, close to 100%, not accuracy.
- **It has nothing to score in Block A.** The baseline top-10 is fully gold-labelled and the harness does not re-run search, so the judge would make 0 calls.

Recommendation:

- Rename it a "gold-set extension" that uses the same prompt, schema, pinned model and `format_openalex_work`.
- Cite the existing 94/98 human blind sample as its calibration.
- Store its labels outside `eval/gold/v0`, with source `model` or `judge`, and report gold-scored and judge-scored slots separately (backlog #39).
- Move it to Block B, where the live search re-run is built. Block A only records the procedure.
- Update `plan_v2.md:257-258` to match.

**B4. Groq's free tier probably cannot carry the extraction judge.** (design, implementation-readiness, zoom-out, codebase-details, inventive-catalyst)

- The reviewers recalled the free-tier limits for `llama-3.3-70b-versatile` as about 12k tokens per minute and 100k per day. None of them could check this live.
- A per-paper judge call is about 9-11k tokens, right at the per-minute limit. A per-value pass is about 270k tokens, more than a day's quota.
- The Block C full-paper experiment (about 40k tokens per paper) cannot be judged on that tier at all.
- Groq retires model IDs, and a pinned ID has no weights digest behind it.

Recommendation:

- Check the limits live before choosing, and record the date and the arithmetic in `decisions.md`.
- Lens alternatives: make the cluster Ollama judge the primary (design, zoom-out), or reuse the Claude CLI judge (inventive-catalyst, zoom-out). The Claude CLI is a different family, has no size problem, and already has pinning and a JSON schema. Its caveats:
  - Correctness judging would be mildly circular, because Claude pre-filled the extraction gold.
  - Paper text would go to Anthropic.
  - It uses the owner's subscription, not a free tier.

**B5. Judge layering contradicts current docs.** (structural)

- Plan section 7 lists `judge` as a `get_llm` role, and `get_llm` is "the only place that builds LLM clients".
- `architecture.md:33-36` forbids eval modules other than the adapter from importing pipeline code, and `scoring.py` "never calls a model".

Recommendation:

- Make the judge eval-only and a separate step: `python -m eval.harness.judge <run_id>` writes `outputs/<run_id>/judgments/*.json`.
- `score()` only reads those files. Re-scoring then still gives the same file byte for byte.
- Amend plan section 7 and `architecture.md`.
- Do not add `judge` to `WIRED_ROLES`.

### Majors

**M1. The #38 startup check: where it lives, what it checks, how it fails.** (all lenses)

- **Location.** Move `native_root` and `configured_context_length` into `src/llm/ollama.py`, and have `eval` import them from there. `src` may not import `eval`.
- **What it checks.** Every role model has `num_ctx` at or above a setting (for example `min_context_length = 16384`). Do not compare the tag string, because Block D candidates will need their own derived tags.
- **Test profile.** Skip the check entirely when `profile == "test"`. CI sets `OLLAMA_BASE_URL` with no server behind it. Add a unit test proving that no HTTP call is made.
- **When it runs.** Lenses split here:
  - At API lifespan (`src/api/main.py:24-28`).
  - At pipeline-run start and in the eval precheck, so that an unreachable Ollama does not crash-loop the API under compose.
  - Recommendation: run it at run start and in the eval precheck. At API startup, at most a warning.
- **Failure messages.** Three distinct ones:
  - Ollama is unreachable at the given root.
  - The model is not found; run `make <target>`.
  - `num_ctx` is unset or too low; run `make <target>`.
- **Known false failure.** A server-wide `OLLAMA_CONTEXT_LENGTH` is invisible to `/api/show`, so the check would fail even though the context is fine. Document this.

**M2. A startup check does not catch truncation during a run.** (design, codebase-details, inventive-catalyst, comprehension) Any prompt over 16k is still cut silently, for example by the full-paper experiment or the 59-page paper. Add a per-call guard: use `create_with_completion`, keep `usage.prompt_tokens`, and flag or raise when it reaches `num_ctx` minus a margin. Record `num_ctx` per role, the Ollama version and the base host in both provenance records. This is the test that actually proves #38 closed for every prompt size.

**M3. The base model can drift after a pod restart.** (implementation-readiness, design, structural) The README procedure pulls `qwen2.5-coder:7b` by tag, and the derived digest changes every time the model is re-created. The make target should check that the base digest is `dae161e27b0e` and refuse otherwise. Provenance should pin the base digest plus the Modelfile SHA, and the target should do nothing harmful if the model already exists. Lenses also suggested:

- Find the pod by label instead of copying its name by hand.
- Parameterize the target as `BASE=`, `CTX=`, `TARGET=local|cluster`.
- Consider moving the Modelfile to `deploy/ollama/`, since it becomes a deployment artifact.

**M4. Calibration statistics on about 30 labels.** (design, zoom-out, comprehension, inventive-catalyst, implementation-readiness)

- 26 of 30 has a 95% interval of about 70-95%, so the test cannot tell an 85% judge from a 70% one.
- If 26 or more labels are "faithful", a judge that always answers "faithful" passes.
- "Catches most" with 3-5 unfaithful labels is 2 or 3 events.

Recommendation:

- Pre-register the pass as counts: agreement of at least 26/30, and unfaithful recall of at least k of n with n of at least 8.
- Report the full 2x2 table.
- Freeze the judge prompt (record its SHA) before measuring agreement, and allow at most one revision.
- The owner labels blind: shuffled across runs, without seeing the judge's output.
- Run the judge twice to measure its repeat-run difference.

**M5. Correctness is reported but never calibrated.** (design, zoom-out, comprehension, implementation-readiness) Plan section 8 says a judge is calibrated before its results are trusted. The owner should label both faithful and correct on the same values. This adds little time, because the gold quote sits next to the value. Otherwise, mark correctness "uncalibrated, report-only". Never use a Claude model as the correctness judge, because of the gold pre-fill.

**M6. The owner's labeling unit and scale are undefined.** (comprehension, inventive-catalyst, zoom-out)

- Proposed unit and scale: one label per (paper, field) value reported `found`. Faithfulness is supported / partial / unsupported, with partial counting as unfaithful.
- Proposed handling of hard values: generic values such as "empirical study", or a task that restates the review question, are faithful but flagged "uninformative". The title and the research question do not count as support.
- `not_found` values are not labelled for faithfulness.
- The sheet lives under `labeling/` in the data folder. Only counts are committed.
- The judge quotes its support span, and a script checks that the span is in the chunks (reuse `quote_on_page`).
- Labeling time: 2-4 minutes per value, so about 1-2 hours.

**M7. The latency budget is partly a laptop number.** (design, codebase-details, comprehension, implementation-readiness, zoom-out, inventive-catalyst, structural)

- **The search part is a constant.** 27.9 s of the 145.4 s is the mean `duration_s` of the frozen laptop snapshots (`scoring.py:278-288`). All 3 cluster runs will repeat it unchanged.
- **The margin is applied twice.** Taking the slowest of 3 runs and then multiplying by 1.2 counts the margin twice.
- **The Block C check measures something else.** Plan section 11 says "one new_topic run", which measures wall-clock time, not the harness formula.

Recommendation:

- Define the budget as the existing run plus 2 new runs at the same commit and digest, then max(`latency_budget_s`) × 1.2.
- State that search is fixed.
- Use the same formula for the Block C check, with a retry rule.
- Spread the runs over different times or run them back to back after a warm-up, and state which.
- Use the 3 runs to measure cluster noise as well: screening flips and extraction status flips. They can confirm or replace the fixed threshold of 2, which matters because GPU inference at temperature 0 with concurrency 3 may not be deterministic.

**M8. A cluster fallback judge has its own setup costs.** (design, implementation-readiness, codebase-details)

- It is reached through `/v1`, so it needs its own derived Modelfile with `num_ctx`. Otherwise it repeats #38.
- `OLLAMA_MAX_LOADED_MODELS=1` means it evicts qwen, so the next timed run pays the model reload.
- A 70B q4 model is about 43 GB, and the A100's memory size is not recorded.
- It is lost on every pod restart and must be pulled again.

Recommendation: pick a judge in the 20-30B class. Name it and pin it by base digest. Add it to the make target and to the `num_ctx` check. Never run it alongside timed runs.

**M9. "Never the generating model" is too weak and not enforced.** (comprehension, structural, codebase-details, inventive-catalyst) A Llama judge would grade a Llama candidate in Block D. Change the rule to "a different family from every generating model and every Block D candidate". The judge step reads the run's provenance and refuses to run on a clash, with a test.

**M10. The judge needs a fixed output store and cache.** (design, implementation-readiness, inventive-catalyst, zoom-out)

- Cache verdicts by (judge model ID or digest, prompt SHA, input hash).
- Store them beside `outputs/<run_id>/`, so that re-scoring makes no calls and a retired model cannot change past scores.
- If the judge changes, re-calibrate on the stored owner labels and re-score the baseline.
- Judge the cluster run `20261127T160606-phase1-e7f7169`, not the laptop run, and check that its outputs folder is synced to the data repository.

**M11. Docs, tests and data flow to update.** (structural, implementation-readiness, codebase-details)

Changing the default model breaks these tests:

- `tests/unit/test_settings.py:15-17`
- `tests/unit/test_run_status.py:87-89`
- `tests/integration/test_restart.py:107`

It also touches `.env.example:14`, `README.md`, `AGENTS.md`, `deploy/NOTES.md` and `plan_v2.md:166`.

Other text that needs amending:

- `plan_v2.md:85` and `:342` ("Groq is used only by the eval judge").
- `eval.md:859-862` ("Claude only for one-time labeling") must be amended if the Claude CLI is used per run.

Single source of truth:

- Put the rule and the latency budget once, in `docs/designs/phase2b.md` under a "Shared rules (all blocks)" heading.
- Mark `eval.md:624-655` as superseded, and replace the three paraphrased copies with links.
- Add one `decisions.md` row each for:
  - the rule;
  - #41;
  - the margin;
  - dropping the memory gate;
  - the judge provider;
  - #38 as a fix rather than an experiment.

**M12. "Free budget only" and the Claude CLI.** (implementation-readiness, structural, codebase-details) Claude CLI usage comes from the owner's subscription, not a free API tier. Record that it is reported but not paid per token. Read the cost from the saved `modelUsage` / `total_cost_usd`; no new metering code is needed.

**M13. Block A has no exit if calibration fails.** (zoom-out, implementation-readiness) Pre-state the path: one prompt revision, then the fallback model. If both fail, the design records why, which the plan allows. Then the owner's labels supply the baseline faithfulness number, so Block B is not blocked.

### Nits

- Use one label count: "about 20-30" (plan, STATUS) or "about 30" (hypothesis).
- Record that flips were 0 at temperature 0, so N stays at the floor of 2. Do not drop the formula silently.
- Dropping the macOS gate leaves no check that a candidate runs fully on the GPU. Consider an `ollama ps` 100%-GPU check for Block D.
- Sending paper chunks to Groq sends full text to an outside service. State that this is acceptable.
- Do not build a string-overlap faithfulness check. It fails on paraphrased fields.
- The #38 fix gets either a "fix, no metric" row in `experiments_2b.md` or an explicit exemption note.
- Mark `eval.md:4` status to show which parts are superseded.

## Goals vs. Non-Goals

**Goals**

- The pipeline cannot run with a truncated context without an error. That needs the derived model as default, the `num_ctx` check, and a per-call guard if adopted.
- The derived model can be re-created after a pod restart with one command, with a check on the base digest.
- One written, tested decision rule that two people apply with the same result. It defines units per metric, lists the target and guard metrics, sets the include gate, and names the reference run. It amends #41.
- A recorded latency budget from 3 cluster runs, with the search constant stated. The same runs also measure noise.
- A faithfulness judge calibrated before use: at least 26/30 agreement and at least 7/8 unfaithful values caught. Correctness is reported without calibration and marked as such.
- Baseline faithfulness and correctness numbers on the cluster reference run.

**Non-Goals**

- Changing the shared cluster Ollama deployment, including any server-wide `OLLAMA_CONTEXT_LENGTH`.
- Treating #38 as an experiment, or expecting a metric change from it.
- Any paid API.
- The search judge, live search re-runs and scoring new search papers in Block A. Both belong in Block B, where the first search experiment needs them.
- A string-overlap faithfulness checker, or evidence pointers per field. The latter is a Block C candidate.
- Derived `num_ctx` models for Block D candidates, which are Block D work.
- Any extraction, screening or search improvement. Those are Blocks B to D.

## Alternatives Weighed

**Context length (#38)**

- **Server-wide `OLLAMA_CONTEXT_LENGTH=16384` on the cluster deployment.** It would remove the derived model and the make target. Rejected by author: the shared cluster deployment is not changed.
- **Per-request `num_ctx` through the `/v1` endpoint.** Not available: the OpenAI-compatible endpoint takes no per-request `num_ctx`. Passing it through `extra_body` is unproven and should not be relied on without a probe (reviewer-raised).
- **Native `/api/chat` with `options.num_ctx`.** It would bypass Instructor's OpenAI path in `src/llm/client.py` (reviewer-raised, not recommended).
- **Running #38 as a measured experiment.** Rejected by author: it is a fix with a test, not an experiment. The reviewers agree, because the baseline already ran at 16k.
- **Per-call truncation guard on `usage.prompt_tokens`, added to the startup check.** Reviewer-raised, and recommended.
- **Startup check at API lifespan vs at run start.** Reviewer-raised. The lenses split; most favour run start plus the eval precheck.

**Decision rule**

- **Keep the macOS memory gate.** Rejected by author: dropped, because all Phase 2b runs are on the cluster. A replacement GPU-residency check was raised by a reviewer for Block D.
- **Pooled include and exclude screening counts (#41 as drafted).** Rejected by author: a table per metric (unit, win, loss, target or gate), with a hard gate that no gold include is newly missed.
- **Compare each experiment against the frozen baseline.** Rejected by author: each experiment is compared with the last accepted state; the phase end is reported against the frozen baseline.
- **Paired comparison for search precision@10.** Rejected by author: a changed search returns different papers, so precision@10 is compared as counts.
- **N recomputed from the noise in the 3 cluster runs.** Reviewer-raised. Not taken: the owner set the threshold to 2 (wins − losses ≥ 2 to improve, losses − wins ≥ 2 to be worse).
- **One ordered outcome per field**, combining status, faithfulness and correctness. Reviewer-raised.

**Faithfulness calibration**

- **The owner labels the 30 saved baseline values directly.** Rejected by author: calibration values must not be the values the judge is reported on.
- **A degraded calibration run at a 2,050-token or `num_ctx 2048` context.** Rejected by author after the review: truncation removes the instructions and gives broken output, not subtle unfaithfulness. Chosen instead: synthetic negatives built from saved outputs (supporting chunk removed, chunks swapped between papers) plus one normal run with another config.
- **A string or quote-overlap check** instead of an LLM judge. Reviewer-raised and rejected by the reviewers themselves: it fails on paraphrased fields.

**Judge provider**

- **A paid API judge.** Rejected by author: free budget only.
- **Using the generating model (qwen) as judge.** Rejected by author: the judge must never be the generating model. Reviewers would widen this to the same family as any candidate.
- **Groq primary, cluster fallback** (the hypothesis as reviewed). Rejected by author after the review: the free tier probably cannot carry the call volume. Chosen instead: a non-qwen model pulled on the cluster Ollama is primary (try two, keep the first that passes calibration); Groq is the fallback. Every judge output is cached.
- **Claude CLI as the faithfulness judge** (reviewer-raised): strong and a different family. It is subscription-based, sends text to Anthropic, and has a correctness circularity.
- **One judge call per paper (5 values)** vs **one per value.** Reviewer-raised: per-paper calls are about 5 times cheaper.

**Search judge**

- **Calibrating it against the Phase 2a gold labels in Block A** (plan wording). Rejected by author: it is circular, and in Block A it would make 0 calls. The search judge moves to Block B.

## Key Decisions & Staging for Next Steps

### Owner decisions (2026-11-28)

1. **Decision rule, for every Phase 2b experiment.**
   - One table per metric, with its unit, what counts as a win and as a loss, and whether it is a target or a gate.
   - Improves: wins − losses ≥ 2. Worse: losses − wins ≥ 2 on another metric in the table.
   - Hard gate: no gold include is newly missed.
   - Search precision@10 is compared as counts, not paired.
   - Each experiment is compared with the last accepted state. The phase end is reported against the frozen baseline.
   - The memory gate is dropped. Latency budget = slowest of 3 cluster baseline runs × 1.2.
2. **Calibration data.**
   - About 30 values, at least 8 of them unfaithful.
   - Built from saved outputs, with the supporting chunk removed or chunks swapped between papers, plus one normal run with another config.
   - Not the baseline values.
3. **Calibration pass.**
   - At least 26/30 agreement overall, and at least 7/8 unfaithful values caught.
   - Correctness is reported without calibration and marked as such.
4. **Judge provider.**
   - Primary: a non-qwen model pulled on the cluster Ollama. Try two and keep the first that passes.
   - Fallback: Groq, with a pinned model ID.
   - Every judge output is cached.
5. **Search judge.** Moved to Block B. Block A's plan checklist is amended to match.
6. **#38.** A fix with a test, as decided before the review.

**Still open, to settle in the design section:**
- the other config for the normal calibration run;
- where the startup check sits (run start plus eval precheck is the reviewers' majority), and whether to add the per-call truncation guard;
- whether the family rule is widened to "not the same family as any candidate";
- what happens if neither cluster model nor Groq passes calibration.

### Call volume and token cost estimates

These are approximate. The Groq limits are assumed from the reviewers' memory, not checked.

| Item | Calls | Tokens |
| --- | --- | --- |
| Faithfulness judge, per paper (5 values per call), one pass | 6 | ~9-11k in + ~1k out per call, ~55-65k per pass |
| Faithfulness judge, per value (full context), one pass | 30 | ~270-285k per pass |
| Block A judge passes (calibration, repeat for noise, baseline, baseline repeat) | 4 passes | ~220-260k per paper; ~1.1M per value |
| Phase 2b extraction side (about 8-12 Block C plus 3-4 Block D experiments, judged twice) | about 25-30 passes | ~1-1.5M per paper, before the full-paper experiment |
| Full-paper experiment (Block C) | 6 per pass | ~40k per call; exceeds the assumed Groq per-minute limit |
| Search gold extension, per search experiment | up to 30 (new top-10 papers only) | ~2-3k per paper, up to ~90k |
| Search gold extension, Block B (about 4 candidates) | up to 120 | up to ~360k, less with caching |
| Search labeler on the Block A baseline | 0 | 0, because every top-10 paper is already gold |
| Extra cluster baseline runs (latency) | 2 runs | about 4-5 minutes of GPU each |

With the assumed limits of about 12k tokens per minute and 100k per day, Groq allows about one per-paper judge pass per day. Block A alone would take 2-3 days of quota, and per-value judging does not fit. Search labeler cost is read from the CLI's `modelUsage` / `total_cost_usd` and reported per run. It counts against the owner's Claude subscription, not a free tier.

### Ordered task list for Block A

1. **Design section.** Write `docs/designs/phase2b.md` with "Shared rules (all blocks)": the decision-rule table, the latency budget and the judge contract. Then the Block A section with items A1-A5 that match the plan checklist. Record the owner decisions above in `decisions.md`, mark the superseded parts of `eval.md`, and update `plan_v2.md` section 10 Block A and section 7.
2. **#38 fix.**
   - Move the `/api/show` helpers into `src/llm/ollama.py`.
   - Add the `min_context_length` setting and the default `qwen2.5-coder:7b-ctx16k`.
   - Add the check at run start and in the eval precheck, skipped on the `test` profile.
   - Optionally add the per-call truncation guard and `num_ctx` in provenance.
   - Add the make target with the base digest check.
   - Update the tests and docs that name the old tag.
   - Acceptance: unit tests (pass, unset, too low, 404, test profile makes no call) and `truncation_check` on the cluster reports no truncation.
3. **Decision rule code.** Write `eval/harness/compare.py` and `make eval-compare`, reading two outputs folders. Fixture tests cover:
   - each metric's wins and losses;
   - the #41 exclude counting;
   - the include gate;
   - the edge at exactly 2;
   - a self-comparison that returns "no change";
   - mismatched base digests.
4. **Two more cluster baseline runs.** Record the latency budget (max × 1.2, search constant stated) and the noise: screening flips and extraction status flips.
5. **Judge selection.** Pull two non-qwen models on the cluster, pinned by digest; Groq is the fallback. Run them outside timed runs, and note the GPU memory they take next to qwen.
6. **Calibration.**
   - Build about 30 values with at least 8 unfaithful: synthetic negatives from saved outputs (supporting chunk removed, chunks swapped between papers) plus one normal run with another config.
   - The owner labels them blind, faithfulness only.
   - Build the judge as a separate eval step with every output cached. Freeze its prompt.
   - Try the first cluster model. Keep it if it reaches at least 26/30 overall and at least 7/8 unfaithful caught; otherwise try the second, then Groq.
   - Run the kept judge twice for the repeat difference.
7. **Baseline judging.** Score the cluster reference run `20261127T160606-phase1-e7f7169` for faithfulness (calibrated) and correctness (reported without calibration, marked as such).
8. **Search judge.** Not in Block A. Add it to the Block B list as a gold-set extension (new papers only, cached, token cost reported per run).
9. **Close the block.** Drift check, explanation notes, `STATUS.md`, backlog items for out-of-block ideas (owner spot-check of model-labelled search papers, a token-count latency proxy, a GPU-residency check for Block D).
