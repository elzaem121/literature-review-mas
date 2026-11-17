# v1 eval input snapshot

Frozen copies of the two gitignored v1 search outputs, kept as inputs for the Phase 2a eval
baseline. Do not edit them.

| Snapshot file | Copied from | Papers | Retrieved |
| --- | --- | --- | --- |
| `screening_search_results.json` | `Screening_Agent/search_results.json` | 24 | 2026-08-05 or earlier (see below) |
| `extract_search_results.json` | `extract_agent/search_results.json` | 10 | between 2026-05-25 and 2026-06-09 (see below) |

Snapshot created: 2026-11-17.

## How the retrieval dates were established

The files carry no timestamp of their own, so the dates are bounded from git history of the
v1 repository, where earlier copies of both files were committed:

- `extract_search_results.json` is byte-identical to the version committed in `dcc06b0`
  (2026-06-09) and differs from the version committed in `e11a2b3` (2026-05-25). It was
  therefore written after 2026-05-25 and no later than 2026-06-09.
- `screening_search_results.json` is byte-identical to the version committed in `c7977e4`
  (2026-08-05), the first commit that contains it. It was therefore retrieved no later than
  2026-08-05. The local file's modification time is 2026-06-28.

If an exact date matters for the Phase 2a report, re-run the search and replace these files.
