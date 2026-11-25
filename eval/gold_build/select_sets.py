"""Step `select_sets`: the seeded choice of the screening set, 20 papers per topic."""

import random
from dataclasses import replace
from pathlib import Path

from eval.gold_build.files import load_labels, load_topics, save_labels, update_provenance
from eval.harness.gold import (
    DEFAULT_GOLD_DIR,
    SEARCH_SET_SIZE,
    GoldLimits,
    ScreeningGold,
    load_mix_exceptions,
    load_pool,
    load_search_snapshot,
    resolve_search_set,
)
from eval.harness.topics import TOPICS_DIR

DEFAULT_SEED = 2026
SKIP_REASON = "gold-uncertain cap reached"


def topics_below_min_includes(
    gold_dir: Path, topics_dir: Path, limits: GoldLimits = GoldLimits()
) -> list[str]:
    """The topics whose labeled pool has fewer gold includes than the screening set needs."""
    records = load_labels(gold_dir)
    return [
        topic_id
        for topic_id in load_topics(topics_dir)
        if sum(r.decision == "include" for r in records if r.topic_id == topic_id)
        < limits.min_includes
    ]


def select_topic(
    topic_id: str,
    records: list[ScreeningGold],
    search_order: list[str | None],
    seed: int,
    limits: GoldLimits,
) -> tuple[set[str], list[str]]:
    """Choose one topic's screening set; returns the chosen keys and the skipped search papers."""
    rng = random.Random(f"{seed}:{topic_id}")
    by_key = {record.paper_key: record for record in records}
    chosen: list[str] = []
    skipped: list[str] = []
    uncertain = 0
    for key in dict.fromkeys(key for key in search_order if key is not None):
        if by_key[key].decision == "uncertain" and uncertain >= limits.max_uncertain:
            skipped.append(key)
            continue
        uncertain += by_key[key].decision == "uncertain"
        chosen.append(key)
    rest = sorted(key for key in by_key if key not in chosen and key not in skipped)
    rest_includes = [key for key in rest if by_key[key].decision == "include"]
    rest_others = [key for key in rest if by_key[key].decision != "include"]
    rng.shuffle(rest_includes)
    rng.shuffle(rest_others)
    have = sum(by_key[key].decision == "include" for key in chosen)
    room = limits.screening_size - len(chosen)
    low = max(limits.min_includes, have)
    high = min(limits.max_includes, have + len(rest_includes), have + room)
    if low > high:
        raise ValueError(
            f"{topic_id}: cannot reach {limits.min_includes} gold includes in a set of "
            f"{limits.screening_size} papers (labeled pool: {len(by_key)} papers, "
            f"{have + len(rest_includes)} candidate includes); extend the pool"
        )
    chosen += rest_includes[: rng.randint(low, high) - have]
    for key in rest_others:
        if len(chosen) == limits.screening_size:
            break
        if by_key[key].decision == "uncertain":
            if uncertain >= limits.max_uncertain:
                continue
            uncertain += 1
        chosen.append(key)
    if len(chosen) < limits.screening_size:
        raise ValueError(
            f"{topic_id}: the pool has only {len(chosen)} papers that fit a set of "
            f"{limits.screening_size}; extend the pool"
        )
    return set(chosen), skipped


def select_sets(
    *,
    seed: int = DEFAULT_SEED,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    topics_dir: Path = TOPICS_DIR,
    limits: GoldLimits = GoldLimits(),
) -> dict[str, set[str]]:
    """Mark the screening set in `screening.json` and record the seed and skipped papers.

    A topic with a recorded mix exception is not held to the minimum of gold includes.
    """
    records = load_labels(gold_dir)
    exceptions = load_mix_exceptions(gold_dir)
    selected: dict[str, set[str]] = {}
    skipped: list[dict[str, str]] = []
    for topic_id in load_topics(topics_dir):
        topic_records = [r for r in records if r.topic_id == topic_id]
        pool = load_pool(gold_dir, topic_id)
        unlabeled = {p.paper_key for p in pool} - {r.paper_key for r in topic_records}
        if unlabeled:
            raise ValueError(f"{topic_id}: no labels for {sorted(unlabeled)}; run label_import")
        order = resolve_search_set(load_search_snapshot(gold_dir, topic_id), pool, SEARCH_SET_SIZE)
        selected[topic_id], skipped_keys = select_topic(
            topic_id,
            topic_records,
            order,
            seed,
            replace(limits, min_includes=0) if topic_id in exceptions else limits,
        )
        skipped += [
            {"topic_id": topic_id, "paper_key": key, "reason": SKIP_REASON} for key in skipped_keys
        ]
    for record in records:
        if record.topic_id in selected:
            record.in_screening_set = record.paper_key in selected[record.topic_id]
    save_labels(gold_dir, records)
    update_provenance(
        gold_dir, {"selection_seed": seed, "skipped_papers": skipped}, dated="selection"
    )
    return selected
