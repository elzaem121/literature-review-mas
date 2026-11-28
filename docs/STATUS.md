# Status

> Where the project is now. Update it in the same commit as every task (`AGENTS.md`, "Definition of Done").
> Last updated: 2026-11-28 · state as of commit `75b104c` (a commit cannot name its own hash)

## Phase and block

- **Phase:** 2b — Pipeline (`v0.4`), `docs/plan_v2.md` section 10. Phase 2a is closed (tag `v0.3`).
- **Block:** A — Setup and judges. Goal: the full baseline is measured.
- **Reference run:** cluster baseline `eval/results/20261127T160606-phase1-e7f7169.json`.

## Last finished step

- Phase 2b plan split into four blocks, A to D (`75b104c`).
- Doc system for all agents: `AGENTS.md`, this file, `docs/decisions.md`, `docs/experiments_2b.md`, the status check.

## Next step

- Block A brainstorm (agent review): read the Block A code against `eval/reports/2a_baseline.md`, confirm the causes,
  compare the options, choose and order the candidates. Then write the Block A section of `docs/designs/phase2b.md`
  (the file does not exist yet).

## Open decisions

- Latency margin on top of the 145.4 s budget (plan section 11): set in the Block A brainstorm.
- Amendment of the paired model-selection rule to count gold excludes (backlog #41).
- Judge model for faithfulness and search (provisional: Groq `llama-3.3-70b`); check free-tier limits.

## Blockers

- None. The faithfulness judge needs owner calibration labels (about 20–30 values) before its scores are trusted.
