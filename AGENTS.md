# AGENTS.md

Instructions for every coding agent working in this repository (Claude Code, Google Antigravity, and others).
Agent-specific notes live in that agent's own file (`CLAUDE.md` for Claude Code); everything shared is here.

## Start of session

1. Read `docs/STATUS.md`: where the project is and what the next step is.
2. Read the current block in `docs/plan_v2.md` (section 10), and its section in `docs/designs/phase2b.md` if it exists.
3. Read what those name: the design doc, the `docs/backlog.md` items assigned to the block, and the relevant code.

## What this is

A multi-agent system (MAS) that automates a literature review: it searches OpenAlex for papers, screens
them against inclusion/exclusion criteria, downloads and RAG-processes the accepted PDFs, and extracts
structured findings from each paper — all orchestrated as a LangGraph pipeline behind a FastAPI backend
and a Streamlit frontend. All LLM calls go to a **local (or port-forwarded Kubernetes) Ollama endpoint**
via the `instructor` library patched onto the OpenAI SDK client — there is no cloud LLM provider involved.

This is the v2 rewrite. The roadmap is `docs/plan_v2.md`; how the code is built is `docs/architecture.md`; the
current phase and step are in `docs/STATUS.md`.

## Doc map

| Doc | Role |
| --- | --- |
| `docs/STATUS.md` | Where we are: phase, block, last and next step, open decisions, blockers |
| `docs/plan_v2.md` | Roadmap: goal, phases, checklists, exit criteria, constraints |
| `docs/designs/` | How: one design doc per phase or subject (`phase1_foundation.md`, `eval.md`, `phase2b.md`) |
| `docs/architecture.md` | The code as it is: layout, pipeline shape, data contracts, LLM access, configuration |
| `docs/decisions.md` | Owner decisions, one row each, with the reason and a link to the plan |
| `docs/findings.md` | What the evaluation found about the system, with evidence and the planned fix |
| `docs/experiments_2b.md` | One row per Phase 2b experiment: change, metric, before/after, decision |
| `docs/backlog.md` | Ideas and issues for later, each with a status and an owning phase |
| `docs/notes/` | Explanations of what was built in each phase, for the owner |
| `docs/reviews/` | EGM outputs: brainstorm notes, concepts briefs, Goldfish reviews, drift checks |
| `docs/archive/` | v1 leftovers kept for history; not current |
| `eval/README.md` | Eval setup, the gold-build steps, the cluster eval setup |
| `eval/reports/` | One written report per eval phase |

## EGM outputs

EGM artifact directory: docs/reviews/

- EGM outputs (brainstorm notes, concepts briefs, Goldfish reports, drift checks) go to `docs/reviews/`, with the phase
  and block in the file name, for example `docs/reviews/2b_block_a_concepts_brief.md`.
- Designs go to `docs/designs/`.
- Never overwrite an existing doc. Write a new file, or edit the existing one on purpose.
- EGM tools may write to the repository root (for example `concepts_brief.md`). Move such outputs to their place
  before committing.

## Git

- Work on branch `v2`. Agents commit locally only when the owner asks.
- Agents never push and never touch the remote `origin` (no fetch, pull, push or remote changes). The owner pushes to
  the `github` remote.
- No AI co-author trailers (`Co-Authored-By` or similar) in commit messages.
- One-time setup: `make hooks` installs the commit-msg hook (`scripts/check_status_updated.sh`). Every commit must change
  `docs/STATUS.md`, unless its message contains `[no-status]`. CI runs the same check on every commit in a push.

## Definition of Done

Every commit updates `docs/STATUS.md`, unless its message contains `[no-status]` (checked by the commit-msg hook and
CI; see "Git"). Use `[no-status]` only for commits that do not change where the project is, such as a typo fix.

A task is done when, in the same commit:

- the plan checkbox in `docs/plan_v2.md` is ticked;
- `docs/STATUS.md` is updated (last finished step, next step, open decisions, blockers, date and commit; the commit is
  the last commit before this update, since a commit can't name its own hash);
- each experiment has a row in `docs/experiments_2b.md`, and each decision a row in `docs/decisions.md`;
- `docs/findings.md`, `docs/backlog.md` or `docs/designs/` are updated when the task changes them;
- tests and lint pass (below).

## Phase 2b rules

From `docs/plan_v2.md`, Phase 2b; the plan wins if the two differ.

- Four blocks, A to D, in this order. Each block has a goal with metrics; it is done when the goal is met, or when the
  design records why it is not.
- One change per experiment, measured on the cluster against the cluster baseline
  (`eval/results/20261127T160606-phase1-e7f7169.json`). A change is kept only if its metric improves and no other metric
  gets worse. Each experiment gets one row in `docs/experiments_2b.md`.
- The university cluster's Ollama is the target hardware; all Phase 2b runs, including the latency check, run there.
- New code comes with tests; CI is green.
- The project owner makes the judge calibration labels by hand.
- One EGM cycle per block. Its brainstorm is the agent review: read the block's code against the error analysis in
  `eval/reports/2a_baseline.md`, confirm the causes, and compare the options. It runs just before the block. Design
  sections go in `docs/designs/phase2b.md`. Each block ends with a drift check and explanation notes.
- A block's list holds candidates, not decisions; the block's brainstorm chooses and orders them.
- Ideas outside the current block go to `docs/backlog.md`, not into code.

## Setup & running

```bash
# venv already exists at .venv/ in this repo
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # OPENALEX_EMAIL is required; the app refuses to start without it
```

An Ollama-compatible model must be reachable at `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`)
before running the real pipeline (directly, via `ollama serve` + `ollama pull qwen2.5-coder:7b`, or via
`kubectl port-forward` to a cluster-hosted model — see `README.md` and `deploy/NOTES.md`).

All commands run from the repo root; `src` is a plain package (no editable install).

```bash
# Terminal 1 — backend
uvicorn src.api.main:app --reload

# Terminal 2 — frontend (polls the FastAPI backend)
streamlit run src/ui/app.py

# Postgres (pgvector) must be up (REPOSITORY_BACKEND=postgres, the default), with DATABASE_URL set
# and the schema migrated
docker compose up -d db
make migrate   # alembic upgrade head; the API never migrates by itself

# Or the whole stack in containers: a one-shot `migrate` service runs `alembic upgrade head`
# before the backend starts, so a fresh clone needs no manual migration
make up        # docker compose up -d --build
```

### Tests and lint

```bash
make test                      # pytest from the repo root; unit + fake end-to-end, no network, no model
pytest tests/unit/test_screening.py -q
ruff check src tests eval
ruff format --check src tests eval
```

`make test` runs with the `test` profile's fake surface (fake LLM, fake embedder, stubbed OpenAlex,
fixture PDFs from `tests/fixtures/`) and `REPOSITORY_BACKEND=memory` (an in-memory repository, no database). Tests marked `integration` are excluded by default and need the
compose Postgres (`make integration`; they use their own `literature_review_test` database on that
server, recreated each session). Unit tests need no database. The golden-transcript test
(`tests/e2e/test_golden_transcript.py`) diffs the fake end-to-end run against
`tests/fixtures/golden_run.json`; regenerate that file only as a deliberate, reviewed step.

### Evaluation harness

Design: `docs/designs/eval.md`; setup and the gold-build steps: `eval/README.md`. Live eval commands need Ollama and
`EVAL_DATA_DIR` (a local clone of a private backup repository for PDFs, page text and raw run outputs); CI runs only
the unit tests of the scoring and build logic.

```bash
python -m eval.gold_build <step>          # build the gold set, one step at a time (steps in eval/README.md)
python -m eval.harness.truncation_check   # does Ollama truncate extraction prompts? (G7)
make eval-run                             # the baseline run: REPOSITORY_BACKEND=memory, ADAPTER=phase1
make eval-score RUN=<run_id>              # re-score saved outputs against the current gold set
make eval-sync                            # commit and push the data folder to its backup
```

## Coding standards

- Follow the design; do not add abstractions, layers or options it does not ask for (YAGNI).
- Small functions with one responsibility and clear names; type hints on all public functions; one-line docstrings on public functions.
- Layers: api -> graph/pipeline -> llm/db. Lower layers never import upper ones. Details: `docs/architecture.md`.
- LLM clients only via `get_llm()`, database only via the repository, configuration only via settings.
- No hardcoded values, no dead or commented-out code, no bare `except`; fail with clear error messages.
- Keep each change inside the current task; no unrelated refactors.
- Code must pass `ruff check` and `ruff format`; new behaviour gets a test.
