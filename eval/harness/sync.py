"""Back up the eval data folder: `python -m eval.harness.sync` commits everything and pushes it."""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from eval.harness.data_dir import data_dir


def _git(root: Path, *args: str) -> str:
    """Run git in the data folder and return its output; a failure raises with git's message."""
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout


def sync(root: Path) -> bool:
    """Commit all changes in the folder (if any) and push; return whether a commit was made."""
    _git(root, "add", "-A")
    changed = bool(_git(root, "status", "--porcelain").strip())
    if changed:
        _git(root, "commit", "-m", f"sync {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}")
    _git(root, "push")
    return changed


def main() -> int:
    """Command line entry point."""
    try:
        committed = sync(data_dir())
    except RuntimeError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print("synced a new commit" if committed else "nothing new to commit; pushed anyway")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
