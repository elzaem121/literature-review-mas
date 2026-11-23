"""Step `escalation_import`: apply the human's escalation answers and log them."""

from collections import defaultdict
from pathlib import Path
from typing import Any

from eval.gold_build.compare import ESCALATION_COLUMNS, ESCALATION_SHEET
from eval.gold_build.files import (
    labeling_dir,
    load_labels,
    parse_answer,
    read_csv,
    save_labels,
    update_provenance,
)
from eval.harness.gold import DEFAULT_GOLD_DIR
from eval.harness.topics import derive_decision


def import_escalation(
    *, data_root: Path, gold_dir: Path = DEFAULT_GOLD_DIR
) -> list[dict[str, Any]]:
    """Confirm or change the answered checks, re-derive decisions and record the escalation log.

    Rows without an answer were not reached. A check whose source is no longer `model` was
    applied by an earlier import and is left as it is, so importing a sheet again is safe.
    """
    records = load_labels(gold_dir)
    by_key = {(r.topic_id, r.paper_key): r for r in records}
    rows = read_csv(labeling_dir(data_root) / ESCALATION_SHEET, ESCALATION_COLUMNS)
    scope: dict[tuple[str, str], list[str]] = defaultdict(list)
    reviewed: dict[tuple[str, str], list[str]] = defaultdict(list)
    for number, row in enumerate(rows, start=2):
        trigger = (row["topic_id"], row["check"])
        record = by_key.get((row["topic_id"], row["paper_key"]))
        if record is None or row["check"] not in record.answers:
            raise ValueError(
                f"{ESCALATION_SHEET} row {number}: no gold answer for "
                f"{row['paper_key']} {row['check']}"
            )
        scope[trigger].append(row["paper_key"])
        if not row["answer"].strip():
            continue
        reviewed[trigger].append(row["paper_key"])
        human = parse_answer(row["answer"], f"{ESCALATION_SHEET} row {number}")
        gold = record.answers[row["check"]]
        if gold.source != "model":
            continue
        if human == gold.answer:
            gold.source = "model_verified"
        else:
            gold.reason = f"Changed by the human on escalation; the model answered '{gold.answer}'."
            gold.answer, gold.source = human, "human"
        record.decision = derive_decision({c: a.answer for c, a in record.answers.items()})
    save_labels(gold_dir, records)
    log = [
        {
            "topic_id": topic_id,
            "check": check_id,
            "papers_in_scope": keys,
            "papers_reviewed": reviewed[(topic_id, check_id)],
            "answers_changed": [
                key
                for key in reviewed[(topic_id, check_id)]
                if by_key[(topic_id, key)].answers[check_id].source == "human"
            ],
        }
        for (topic_id, check_id), keys in scope.items()
    ]
    update_provenance(gold_dir, {"escalation": log}, dated="escalation")
    return log
