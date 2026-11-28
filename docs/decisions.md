# Decisions

One row per owner decision, newest last. The plan section linked in each row holds the decision in full; when a
decision changes, add a new row and leave the old one.

| Date | Decision | Why | Link |
| --- | --- | --- | --- |
| 2026-11-27 | Phase 2b runs in four blocks, in order: A setup and judges, B paper selection, C paper reading, D models and close | Fewer, larger steps cost less process; the blocks are grouped by pipeline area (paper selection vs paper reading) | [plan, Phase 2b](plan_v2.md#phase-2b--pipeline--v04) |
| 2026-11-27 | One EGM cycle per block; its brainstorm is the agent review of the block's code against the Phase 2a error analysis, run just before the block | The agent review is part 2: the Phase 2a error analysis is part 1. Reviewing the code just before fixing it uses fresh results from the previous block | [plan, Phase 2b](plan_v2.md#phase-2b--pipeline--v04) |
| 2026-11-27 | Fixed rules vs candidates: the Phase 2b rules are fixed; each block's checklist lists candidates, which the block's brainstorm chooses and orders | The rules keep the measurement honest; the solution is chosen in the brainstorm, after reading the code | [plan, Phase 2b](plan_v2.md#phase-2b--pipeline--v04) |
| 2026-11-27 | The pipeline-as-subgraph task moves to Phase 3; the `screenings` and `extractions` tables stay in Phase 2b | Only the Phase 3 router needs the subgraph. The tables stay in Phase 2b because Loop 1 reads `screenings` and evidence must be stored | [plan, Phase 3](plan_v2.md#phase-3--chat--v05), [5.3](plan_v2.md#53-pipeline-loops) |
| 2026-11-27 | A small held-out topic is measured and reported in Block D | The gold set is small (60 papers, 29 fields), so tuning on it can overfit | [plan, Block D](plan_v2.md#block-d--models-and-close) |
| 2026-11-28 | The university cluster's Ollama is the target hardware for all Phase 2b runs; the latency budget is recomputed with the same formula from the cluster baseline: 145.4 s | The system is deployed on Kubernetes (Phase 4), and runs there are about 18x faster than on the laptop | [plan, section 11](plan_v2.md#11-constraints) |
| 2026-11-27 | Structured JSON logging (backlog #17) moves to Phase 4 | Logging is operations, not agent quality | [plan, Phase 4](plan_v2.md#phase-4--deployment--v06), [backlog](backlog.md) |
| 2026-11-28 | One doc system for all agents: shared instructions in `AGENTS.md` (`CLAUDE.md` imports it), the current state in `docs/STATUS.md`, kept current by a commit-msg hook and CI | One handoff (`docs/STATUS.md`) for Claude Code and Antigravity; docs change in the same commit as the work | [AGENTS.md](../AGENTS.md), [STATUS](STATUS.md) |
