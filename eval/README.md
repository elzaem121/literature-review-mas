# Evaluation harness

Measures the pipeline against a hand-checked gold set: screening, search precision@10, retrieval recall and extraction
field status. The design, the metrics and the reasons for every choice are in `docs/designs/eval.md`; this file is the
how-to. Commands run from the repository root.

## What is committed where

| What | Where | Why there |
| --- | --- | --- |
| Topic configs (question, min year, yes/no checks) | `eval/topics/*.json` | One source for the labeling prompt and the screener's criteria |
| Frozen search, candidate pools, gold labels, labeling prompts, provenance | `eval/gold/v0/` | They define the gold set; titles and abstracts come from OpenAlex (CC0), extraction gold holds one-sentence quotes only |
| One results file per run | `eval/results/<run_id>.json` | Scores, timings and provenance of a run |
| PDFs, page text, raw run outputs, labeling work files | the **eval data folder** (`EVAL_DATA_DIR`), outside this repository | Full text and bulky files must not enter this public repository |

`eval/snapshots/v1/` holds the old v1 search results; they are kept for history and are not used by gold set v0.

## One-time setup: the eval data folder

1. Create a **private** GitHub repository for the backup (for example `literature-review-eval-data`).
2. Clone it outside this repository, for example `~/eval-data`.
3. Set `EVAL_DATA_DIR=~/eval-data` in `.env` (see `.env.example`). Only eval commands read it.

The folder holds `pdfs/`, `pages/`, `outputs/<run_id>/` and `labeling/`. `make eval-sync` commits everything in it
and pushes. Run it after every build step or run that writes to the folder; the commands print a reminder.

Live commands also need Ollama serving the configured models and `OPENALEX_EMAIL` set. `claude` (Claude Code) must be
on the path for the labeling steps.

## Build the gold set

`python -m eval.gold_build <step>`. Steps run in this order. **Human** marks the steps you do by hand.

| # | Step | What it does |
| --- | --- | --- |
| 1 | (manual) | Finalize `eval/topics/*.json`. The search adds the `yes` statements to its query, so change them before step 2 or not at all |
| 2 | `freeze_search --topic <id>` | Runs the Phase 1 search once and writes `eval/gold/v0/<topic>/search.json`. Refuses when the query expansion fell back to the raw question: run it again. Never overwrites; delete the file to freeze again |
| 3 | `build_pool` | Writes `pool.json` per topic (search output, plus the v1 link list for topic 1, read from git history). Unresolved links are listed: add them by hand to `eval/gold/v0/t1_social_media/link_list_manual.json` (URL to OpenAlex id) and run again after deleting the pool. `build_pool --extend <topic>` appends the next results of the same query |
| 4 | `label_prepare` | Writes one title-and-abstract file per pool paper, and the prompt and schema, into the data folder; writes `eval/gold/v0/labeling_prompt.md` |
| 5 | `label_run --model <id>` | One headless `claude -p` call per paper, from inside the inputs folder. Pass the pinned model id (for example `claude-opus-5-5`); it stops if another model answered. A stopped run continues where it ended |
| 6 | `label_import` | Turns the answers into gold records, source `model`. Only adds papers without a record |
| 7 | `select_sets` | Chooses the 20-paper screening set per topic from a seed (`--seed`, default 2026). `--needs-extension` lists topics under 8 gold includes; fix those with `build_pool --extend <topic>`, then repeat steps 4-6 and 7 |
| 8 | `blind_sample` | **Human:** writes `labeling/blind_sheet.csv` in the data folder: 7 papers per topic, shuffled. Fill each check column with `yes`, `no` or `not_stated` **without looking at the model's answers** |
| 9 | `compare` | Counts agreement per topic and check into `provenance.json`. For each check with 2 or more disagreements in a topic it writes `labeling/escalation_sheet.csv` |
| 10 | `escalation_import` | **Human first:** fill the `answer` column of the escalation sheet (about 20 minutes; empty rows count as not reached). Then run: confirmed answers become `model_verified`, changed ones `human`, decisions are derived again, the log is written |
| 11 | `extraction_prepare --model <id> --paper <key> ...` | Downloads each chosen paper's PDF, stores page text and hash, asks Claude to pre-fill fields with page and quote, and checks every quote is on its page. Failures are listed: run the step again. Choose 3 gold-include papers each from topics 1 and 2 |
| 12 | `extraction_verify` | **Human:** writes `labeling/extraction_sheet.csv`. Mark each row `ok` or `wrong` against its quote and page. Then `extraction_verify --import` writes `extraction.json` (`wrong` rows are dropped) |
| 13 | `validate` | Checks sizes, mix, derived decisions, sources, duplicate studies, quotes and PDF hashes. Exits non-zero on any problem |

Sheets that a human fills are never overwritten: move a sheet away to write it again. Commit `eval/gold/v0/` after
`validate` passes, then run `make eval-sync`.

## Check truncation, then run the baseline

```bash
python -m eval.harness.truncation_check     # compares Ollama's prompt token count with the model family's tokenizer
make eval-run                               # ADAPTER=phase1 by default
make eval-score RUN=<run_id>                # re-score saved outputs; also writes errors.md for the error analysis
make eval-sync
```

`truncation_check` runs the largest extraction-gold paper. If it reports truncation, set an explicit context length
for every run, including the baseline (design, "Truncation check").

`make eval-run` sets `REPOSITORY_BACKEND=memory`, so it never touches the paper library. It checks that every model
answers, screens the screening set twice, retrieves and extracts the extraction-gold papers, saves every output to
`<EVAL_DATA_DIR>/outputs/<run_id>/` and writes `eval/results/<run_id>.json`. A run that loses Ollama partway is marked
`incomplete` and is not scored. Re-scoring after correcting a gold label needs no model call, and gives the same file
for the same outputs and gold set.

## Tests

`make test` covers the scoring, validation and build logic on the fake surface and fixtures in `tests/fixtures/eval/`
(`tests/unit/eval/`). There are no live evals in CI.
