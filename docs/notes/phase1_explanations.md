# Phase 1 — explanations

Plain-language notes after each core task.

## Batch 0 — Safety net

Before moving any code, Batch 0 makes sure we can tell when something breaks. The three failing
screening tests were not real bugs: one test looked for a config file in the wrong folder, and one
imported the same class under two different names, so Python treated them as two different classes.
Now the tests load the config from where it really is, import with the full package name, and read
their paper data from a small committed fixture (`tests/fixtures/`) instead of a gitignored file that
would not exist on GitHub. `pyproject.toml` tells pytest to start from the repo root and skip
database tests by default, and holds the ruff settings. We ran `ruff format` once over every file in
its own commit, so later diffs show only real changes. The CI workflow, the Makefile and the frozen
v1 search results in `eval/snapshots/v1/` are the remaining pieces; the Phase 2a baseline needs those
search results to stay unchanged.

## Commit 1a — Seam (LLM layer and settings)

Before 1a, three different files each built their own connection to the model, with the model name and
your email typed directly into the code. Now there is one place for that: `src/llm/settings.py` reads
every setting from the environment (and `.env`) and stops the app at startup if the OpenAlex email is
missing. `src/llm/client.py` has `get_llm(role)` and `get_embedder()`, the only functions that create
model clients; swapping a model for one role later means changing one setting. The prompts moved out of
the agents into `src/llm/prompts/` unchanged (checked byte for byte), each with a version label, so a
stored result can later say which prompt produced it. The `test` profile swaps in fakes at the same
seams: a fake model that answers from a small table, a fake embedder, a fake OpenAlex and two tiny
fixture PDFs. That is what lets the whole pipeline run in a test with no network and no model. The
"golden transcript" is that run's final output saved to a file; any later commit that changes the
output by accident now fails a test. Also in 1a: search became `async`, and the screening agent's own
retry loop is gone (the OpenAI client retries 3 times and Instructor 2 times, and nothing else).
