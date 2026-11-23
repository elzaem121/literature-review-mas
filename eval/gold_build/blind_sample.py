"""Step `blind_sample`: the papers the human labels without seeing the model's answers."""

import random
from pathlib import Path

from eval.gold_build.files import labeling_dir, load_labels, load_topics, write_csv
from eval.harness.gold import DEFAULT_GOLD_DIR, PoolPaper, ScreeningGold, load_pool
from eval.harness.topics import TOPICS_DIR, decided_by, derive_decision

DEFAULT_SEED = 2026
SAMPLE_PER_TOPIC = 7
MAX_BORDERLINE = 3
BLIND_SHEET = "blind_sheet.csv"
# For these topics a paper is also borderline when its decision hangs on this one check.
DECISIVE_CHECKS = {"t2_llm_mas_eval": "c3"}
SHEET_FIXED_COLUMNS = ["topic_id", "paper_key", "title", "abstract"]


def is_borderline(record: ScreeningGold) -> bool:
    """A `not_stated` answer, or a decision that rests on one check."""
    answers = {check: item.answer for check, item in record.answers.items()}
    if "not_stated" in answers.values():
        return True
    if derive_decision(answers) == "exclude" and list(answers.values()).count("no") == 1:
        return True
    decisive = DECISIVE_CHECKS.get(record.topic_id)
    return decisive is not None and decided_by(answers, decisive)


def sample_topic(topic_id: str, records: list[ScreeningGold], seed: int) -> list[str]:
    """Up to 3 borderline papers, then random search-set papers, 7 in all."""
    rng = random.Random(f"{seed}:{topic_id}:blind")
    eligible = sorted(
        (r for r in records if r.in_search_set or r.in_screening_set), key=lambda r: r.paper_key
    )
    borderline = [r.paper_key for r in eligible if is_borderline(r)]
    chosen = rng.sample(borderline, min(MAX_BORDERLINE, len(borderline)))
    search_set = sorted(
        r.paper_key for r in records if r.in_search_set and r.paper_key not in chosen
    )
    needed = SAMPLE_PER_TOPIC - len(chosen)
    if len(search_set) < needed:
        raise ValueError(
            f"{topic_id}: the search set has {len(search_set)} papers left for the random part, "
            f"{needed} are needed"
        )
    return chosen + rng.sample(search_set, needed)


def blind_sample(
    *,
    data_root: Path,
    seed: int = DEFAULT_SEED,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    topics_dir: Path = TOPICS_DIR,
) -> Path:
    """Write the shuffled blind sheet: paper, title, abstract and an empty column per check."""
    records = load_labels(gold_dir)
    topics = load_topics(topics_dir)
    check_columns = sorted(
        {check.id for topic in topics.values() for check in topic.checks}, key=lambda c: int(c[1:])
    )
    rows: list[dict[str, str]] = []
    for topic_id in topics:
        pool: dict[str, PoolPaper] = {p.paper_key: p for p in load_pool(gold_dir, topic_id)}
        topic_records = [r for r in records if r.topic_id == topic_id]
        for key in sample_topic(topic_id, topic_records, seed):
            rows.append(
                {
                    "topic_id": topic_id,
                    "paper_key": key,
                    "title": pool[key].title,
                    "abstract": pool[key].abstract,
                    **dict.fromkeys(check_columns, ""),
                }
            )
    random.Random(f"{seed}:blind-order").shuffle(rows)
    path = labeling_dir(data_root) / BLIND_SHEET
    write_csv(path, [*SHEET_FIXED_COLUMNS, *check_columns], rows)
    return path
