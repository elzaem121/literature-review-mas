@AGENTS.md

# Claude Code notes

Everything shared with other agents is in `AGENTS.md` (imported above). Only Claude Code specifics go here.

- `.claude/settings.json` runs `ruff format` and `ruff check --fix` on every `.py` file after Edit or Write, and turns off
  co-author trailers (`includeCoAuthoredBy: false`).
- EGM reviews (Goldfish reviewers, drift checks) use the `egm:*` subagents; their reports go to `docs/reviews/`.
- `eval/gold_build/claude_cli.py` runs the `claude` CLI as a pinned labeler outside the repository, so this file is not
  loaded there; do not move labeling instructions here.
