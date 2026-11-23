"""Step `compare`: agreement between the model and the human's blind labels, and the escalation."""

from pathlib import Path

from eval.gold_build.blind_sample import BLIND_SHEET, SHEET_FIXED_COLUMNS
from eval.gold_build.files import (
    labeling_dir,
    load_labels,
    load_topics,
    parse_answer,
    read_csv,
    update_provenance,
    write_csv,
)
from eval.harness.gold import DEFAULT_GOLD_DIR, PoolPaper, ScreeningGold, load_pool
from eval.harness.topics import TOPICS_DIR, Topic, decided_by

ESCALATION_TRIGGER = 2
ESCALATION_SHEET = "escalation_sheet.csv"
ESCALATION_COLUMNS = ["topic_id", "paper_key", "check", "question", "title", "abstract", "answer"]


def count_agreement(
    rows: list[dict[str, str]],
    records: dict[tuple[str, str], ScreeningGold],
    topics: dict[str, Topic],
) -> dict[str, dict[str, dict[str, int]]]:
    """Per topic and check, how often the human's blind answer equals the model's."""
    counts: dict[str, dict[str, dict[str, int]]] = {
        topic_id: {check.id: {"agree": 0, "disagree": 0} for check in topic.checks}
        for topic_id, topic in topics.items()
    }
    for number, row in enumerate(rows, start=2):
        topic_id, key = row["topic_id"], row["paper_key"]
        record = records.get((topic_id, key))
        if record is None:
            raise ValueError(f"{BLIND_SHEET} row {number}: no gold labels for {topic_id} {key}")
        for check in topics[topic_id].checks:
            human = parse_answer(row[check.id], f"{BLIND_SHEET} row {number} {check.id}")
            outcome = "agree" if human == record.answers[check.id].answer else "disagree"
            counts[topic_id][check.id][outcome] += 1
    return counts


def papers_in_scope(records: list[ScreeningGold], topic_id: str, check_id: str) -> list[str]:
    """Papers of the topic, in either set, whose decision would change if this check changed."""
    return sorted(
        record.paper_key
        for record in records
        if record.topic_id == topic_id
        and (record.in_search_set or record.in_screening_set)
        and decided_by({c: a.answer for c, a in record.answers.items()}, check_id)
    )


def compare(
    *, data_root: Path, gold_dir: Path = DEFAULT_GOLD_DIR, topics_dir: Path = TOPICS_DIR
) -> list[tuple[str, str]]:
    """Record the agreement counts and write the escalation sheet; return the triggers."""
    topics = load_topics(topics_dir)
    records = load_labels(gold_dir)
    by_key = {(r.topic_id, r.paper_key): r for r in records}
    check_columns = sorted(
        {c.id for t in topics.values() for c in t.checks}, key=lambda c: int(c[1:])
    )
    rows = read_csv(labeling_dir(data_root) / BLIND_SHEET, [*SHEET_FIXED_COLUMNS, *check_columns])
    agreement = count_agreement(rows, by_key, topics)
    triggers = [
        (topic_id, check_id)
        for topic_id, checks in agreement.items()
        for check_id, counts in checks.items()
        if counts["disagree"] >= ESCALATION_TRIGGER
    ]
    sheet_rows: list[dict[str, str]] = []
    for topic_id, check_id in triggers:
        pool: dict[str, PoolPaper] = {p.paper_key: p for p in load_pool(gold_dir, topic_id)}
        question = next(c.question for c in topics[topic_id].checks if c.id == check_id)
        for key in papers_in_scope(records, topic_id, check_id):
            sheet_rows.append(
                {
                    "topic_id": topic_id,
                    "paper_key": key,
                    "check": check_id,
                    "question": question,
                    "title": pool[key].title,
                    "abstract": pool[key].abstract,
                    "answer": "",
                }
            )
    if sheet_rows:
        write_csv(labeling_dir(data_root) / ESCALATION_SHEET, ESCALATION_COLUMNS, sheet_rows)
    update_provenance(gold_dir, {"agreement": agreement}, dated="comparison")
    return triggers
