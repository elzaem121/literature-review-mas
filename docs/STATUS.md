# Status

> Where the project is now. Every commit updates it, unless its message contains `[no-status]` (`AGENTS.md`, "Definition of Done").
> Last updated: 2026-11-28 · state as of commit `870856d` (a commit cannot name its own hash)

## Phase and block

- **Phase:** 2b — Pipeline (`v0.4`), `docs/plan_v2.md` section 10. Phase 2a is closed (tag `v0.3`).
- **Block:** A — Setup and judges. Goal: the full baseline is measured.
- **Reference run:** cluster baseline `eval/results/20261127T160606-phase1-e7f7169.json`.

## Last finished step

- Block A brainstorm (agent review with seven Goldfish lenses) and the owner's decisions on it:
  `docs/reviews/2b_block_a_concepts_brief.md`; decisions in `docs/decisions.md` (2026-11-28 rows). The search judge
  moved to Block B.
- EGM outputs now go to `docs/reviews/`; the Phase 2a brief moved to `docs/reviews/2a_concepts_brief.md`.
- The status check now applies to every commit, not only commits that change `src/` or `eval/`.

## Next step

- Write the Block A section of `docs/designs/phase2b.md` (the file does not exist yet) from the brief:
  `/egm:egm-draft docs/reviews/2b_block_a_concepts_brief.md`. It holds the shared decision-rule table for all blocks.

## Open decisions

- The other config for the normal calibration run of the faithfulness judge.
- Which two non-qwen models to try as the cluster judge, and what happens if neither they nor Groq pass calibration.
- Whether the judge-family rule widens to "not the same family as any candidate model".
- Where the `num_ctx` startup check sits (run start plus eval precheck is the reviewers' majority), and whether a
  per-call truncation guard is added.

## Blockers

- None. The faithfulness judge needs about 30 owner calibration labels (at least 8 unfaithful) before its scores are
  trusted.
