"""Step `label_import`: turn the raw model answers into gold records with source `model`."""

from pathlib import Path
from typing import Any

from eval.gold_build.files import load_labels, load_topics, read_json, save_labels
from eval.gold_build.label_run import answer_path
from eval.harness.gold import (
    DEFAULT_GOLD_DIR,
    SEARCH_SET_SIZE,
    AnswerGold,
    ScreeningGold,
    load_pool,
    load_search_snapshot,
    resolve_search_set,
)
from eval.harness.topics import TOPICS_DIR, Topic, derive_decision


def answers_from_output(output: dict[str, Any], topic: Topic, where: str) -> dict[str, AnswerGold]:
    """The model's answers as gold answers; they must cover exactly the topic's checks."""
    answers = {
        item["check"]: AnswerGold(answer=item["answer"], source="model", reason=item["reason"])
        for item in output["structured_output"]["answers"]
    }
    expected = sorted(check.id for check in topic.checks)
    if sorted(answers) != expected:
        raise ValueError(f"{where}: answers cover {sorted(answers)}, the checks are {expected}")
    return answers


def import_labels(
    *, data_root: Path, gold_dir: Path = DEFAULT_GOLD_DIR, topics_dir: Path = TOPICS_DIR
) -> int:
    """Add a record for every pool paper that has none; existing records are never touched."""
    records = load_labels(gold_dir)
    labeled = {(record.topic_id, record.paper_key) for record in records}
    added = 0
    for topic_id, topic in load_topics(topics_dir).items():
        pool = load_pool(gold_dir, topic_id)
        search_set = set(
            resolve_search_set(load_search_snapshot(gold_dir, topic_id), pool, SEARCH_SET_SIZE)
        )
        for paper in pool:
            if (topic_id, paper.paper_key) in labeled:
                continue
            path = answer_path(data_root, topic_id, paper.paper_key)
            if not path.is_file():
                raise ValueError(
                    f"no labeling answer for {paper.paper_key} ({path}); run label_run"
                )
            answers = answers_from_output(read_json(path), topic, f"{topic_id} {paper.paper_key}")
            records.append(
                ScreeningGold(
                    topic_id=topic_id,
                    paper_key=paper.paper_key,
                    in_search_set=paper.paper_key in search_set,
                    in_screening_set=False,
                    answers=answers,
                    decision=derive_decision({c: a.answer for c, a in answers.items()}),
                )
            )
            added += 1
    save_labels(gold_dir, records)
    return added
