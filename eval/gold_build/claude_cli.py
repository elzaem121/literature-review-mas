"""Headless `claude -p` calls for labeling and pre-filling, with the pinned-model check."""

import json
import subprocess
from pathlib import Path
from typing import Any

CLAUDE_COMMAND = "claude"
CLAUDE_TIMEOUT_S = 600


class ClaudeError(RuntimeError):
    """A headless Claude call failed, or a different model than the pinned one answered."""


def claude_version() -> str:
    """The installed Claude Code version, for the provenance."""
    result = subprocess.run(
        [CLAUDE_COMMAND, "--version"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise ClaudeError(f"`{CLAUDE_COMMAND} --version` failed: {result.stderr.strip()}")
    return result.stdout.strip()


def run_claude(
    *, model: str, system_prompt: str, schema: dict[str, Any], text: str, cwd: Path
) -> dict[str, Any]:
    """One headless call with no tools and no stored session; returns the parsed JSON output.

    It runs in `cwd`, so this repository's CLAUDE.md is not loaded. The call fails unless the
    pinned model, and only that model, answered.
    """
    command = [
        CLAUDE_COMMAND,
        "-p",
        "--model",
        model,
        "--tools",
        "",
        "--system-prompt",
        system_prompt,
        "--json-schema",
        json.dumps(schema),
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    try:
        result = subprocess.run(
            command,
            input=text,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=CLAUDE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClaudeError(f"claude did not answer within {CLAUDE_TIMEOUT_S} s") from exc
    if result.returncode != 0:
        raise ClaudeError(f"claude exited with {result.returncode}: {result.stderr.strip()}")
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeError(f"claude did not print JSON: {result.stdout[:200]!r}") from exc
    if output.get("is_error"):
        raise ClaudeError(f"claude reported an error: {output.get('result')}")
    answered = sorted(output.get("modelUsage", {}))
    if answered != [model]:
        raise ClaudeError(f"models that answered were {answered}, the pinned model is '{model}'")
    if not isinstance(output.get("structured_output"), dict):
        raise ClaudeError("claude returned no structured output")
    return output
