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
