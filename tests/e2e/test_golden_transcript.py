"""Characterization test: the fake end-to-end run must keep producing the captured v1 state.

Differences are allowed only under a JSON-path prefix listed in ALLOWED_PREFIXES (one list per
behaviour-change register entry that is visible in graph state). The list is empty: V6 predates
the capture, V4 is API-layer state, and V1-V3/V5 are baked into the file as regenerated in Batch 2b
(only the retrieved chunks changed: page-aware boundaries, one PDF and chunk set per paper).
Regenerate deliberately with `UPDATE_GOLDEN=1 pytest tests/e2e/test_golden_transcript.py`.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "golden_run.json"
VOLATILE_KEYS = {"pdf_path": "<PDF_PATH>"}
ALLOWED_PREFIXES: tuple[str, ...] = ()


def scrub(value: Any) -> Any:
    """Replace volatile values (filesystem paths) with fixed placeholders."""
    if isinstance(value, dict):
        return {k: VOLATILE_KEYS.get(k, scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def flatten(value: Any, path: str = "") -> Dict[str, Any]:
    """Map every leaf of a JSON-like value to its dotted path."""
    if isinstance(value, dict) and value:
        children = value.items()
    elif isinstance(value, list) and value:
        children = enumerate(value)
    else:
        return {path: value}
    leaves: Dict[str, Any] = {}
    for key, child in children:
        leaves.update(flatten(child, f"{path}.{key}" if path else str(key)))
    return leaves


def changed_paths(golden: Any, actual: Any) -> List[str]:
    """Return the sorted paths at which two JSON-like values differ."""
    before, after = flatten(golden), flatten(actual)
    return sorted(
        p for p in before.keys() | after.keys() if before.get(p, _MISSING) != after.get(p, _MISSING)
    )


_MISSING = object()


def unexpected_changes(
    golden: Any, actual: Any, allowed_prefixes: tuple[str, ...] = ALLOWED_PREFIXES
) -> List[str]:
    """Return the changed paths that no register entry allows."""
    return [p for p in changed_paths(golden, actual) if not p.startswith(allowed_prefixes)]


def test_fake_run_matches_the_golden_transcript(final_state):
    actual = scrub(final_state)
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN_PATH.write_text(
            json.dumps(actual, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    assert unexpected_changes(golden, actual) == []


def test_scrub_replaces_paths_at_any_depth():
    state = {"a": [{"pdf_path": "/tmp/x.pdf", "keep": 1}], "pdf_path": "/tmp/y.pdf"}

    assert scrub(state) == {"a": [{"pdf_path": "<PDF_PATH>", "keep": 1}], "pdf_path": "<PDF_PATH>"}


def test_changed_paths_lists_added_removed_and_edited_leaves():
    golden = {"a": 1, "b": [1, 2], "c": {"d": "x"}}
    actual = {"a": 2, "b": [1], "c": {"d": "x", "e": True}}

    assert changed_paths(golden, actual) == ["a", "b.1", "c.e"]


def test_differences_under_an_allowed_prefix_are_not_reported():
    golden = {"screening_results": {"status": "a"}, "raw_papers": {"title": "a"}}
    actual = {"screening_results": {"status": "b"}, "raw_papers": {"title": "b"}}

    assert unexpected_changes(golden, actual, ("screening_results",)) == ["raw_papers.title"]
    assert unexpected_changes(golden, actual, ()) == [
        "raw_papers.title",
        "screening_results.status",
    ]
