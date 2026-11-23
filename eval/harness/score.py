"""Re-score saved outputs: `python -m eval.harness.score <run_id>`."""

import argparse
from pathlib import Path

from eval.harness.data_dir import data_dir, outputs_dir
from eval.harness.error_report import render_errors
from eval.harness.gold import DEFAULT_GOLD_DIR, SEARCH_SET_SIZE
from eval.harness.scoring import RESULTS_DIR, score, write_results


def score_run(
    run_dir: Path,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    results_dir: Path = RESULTS_DIR,
    *,
    search_size: int = SEARCH_SET_SIZE,
) -> Path:
    """Score a run's saved outputs and write its results file and `errors.md`; return the path."""
    results = score(run_dir, gold_dir, search_size=search_size)
    path = write_results(results, results_dir)
    errors = render_errors(run_dir, gold_dir, search_size=search_size)
    (run_dir / "errors.md").write_text(errors, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """Command line entry point; prints the results path."""
    parser = argparse.ArgumentParser(description="Re-score the saved outputs of one eval run.")
    parser.add_argument("run_id")
    args = parser.parse_args(argv)
    try:
        path = score_run(outputs_dir(data_dir(), args.run_id))
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
