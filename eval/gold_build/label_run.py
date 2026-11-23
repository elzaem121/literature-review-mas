"""Step `label_run`: label every prepared paper with one headless Claude call each."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from eval.gold_build import claude_cli
from eval.gold_build.files import (
    labeling_dir,
    load_topics,
    read_json,
    read_provenance,
    sha256_bytes,
    update_provenance,
    write_json,
)
from eval.gold_build.label_prepare import (
    LABELING_PROMPT_FILE,
    PROMPT_FILE,
    SCHEMA_FILE,
    inputs_dir,
)
from eval.harness.gold import DEFAULT_GOLD_DIR
from eval.harness.topics import TOPICS_DIR

ANSWERS = "answers"
Runner = Callable[..., dict[str, Any]]


def answer_path(data_root: Path, topic_id: str, paper_key: str) -> Path:
    """Where the raw answer for one paper is saved."""
    return labeling_dir(data_root) / ANSWERS / topic_id / f"{paper_key}.json"


def run_labeling(
    model: str,
    *,
    data_root: Path,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    topics_dir: Path = TOPICS_DIR,
    runner: Runner = claude_cli.run_claude,
) -> int:
    """Label every input that has no answer yet with the pinned model; return the calls made."""
    prompt_file = gold_dir / LABELING_PROMPT_FILE
    if not prompt_file.is_file():
        raise ValueError(f"{prompt_file} does not exist; run label_prepare first")
    recorded = read_provenance(gold_dir).get("labeling_model")
    if recorded not in (None, model):
        raise ValueError(
            f"labels so far were made with '{recorded}'; keep that model, not '{model}'"
        )
    update_provenance(
        gold_dir,
        {
            "labeling_model": model,
            "claude_code_version": claude_cli.claude_version(),
            "labeling_prompt_sha256": sha256_bytes(prompt_file.read_bytes()),
        },
        dated="labeling",
    )
    calls = 0
    for topic_id in load_topics(topics_dir):
        folder = inputs_dir(data_root, topic_id)
        if not folder.is_dir():
            raise ValueError(f"{folder} does not exist; run label_prepare first")
        prompt = (folder / PROMPT_FILE).read_text(encoding="utf-8")
        schema = read_json(folder / SCHEMA_FILE)
        for path in sorted(folder.glob("*.txt")):
            target = answer_path(data_root, topic_id, path.stem)
            if target.exists():
                continue
            output = runner(
                model=model,
                system_prompt=prompt,
                schema=schema,
                text=path.read_text(encoding="utf-8"),
                cwd=folder,
            )
            write_json(target, output)
            calls += 1
    return calls
