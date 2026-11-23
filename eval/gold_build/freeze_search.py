"""Step `freeze_search`: run the baseline search once for a topic and store the snapshot."""

import time
from datetime import UTC, datetime
from pathlib import Path

from eval.gold_build.files import write_json
from eval.harness.adapters.phase1 import (
    SEARCH_MIN_CITATIONS,
    SEARCH_TARGET_OUTPUT_COUNT,
    Phase1Adapter,
)
from eval.harness.gold import DEFAULT_GOLD_DIR, SearchSnapshot
from eval.harness.topics import TOPICS_DIR, load_topic

DURATION_DECIMALS = 1


async def freeze_search(
    topic_id: str, *, gold_dir: Path = DEFAULT_GOLD_DIR, topics_dir: Path = TOPICS_DIR
) -> Path:
    """Write the topic's `search.json`; a fallback run or an existing snapshot is refused."""
    path = gold_dir / topic_id / "search.json"
    if path.exists():
        raise ValueError(
            f"{path} already exists; a frozen search is never overwritten (delete it on purpose)"
        )
    topic = load_topic(topic_id, topics_dir)
    adapter = Phase1Adapter()
    started = time.perf_counter()
    record = await adapter.search(topic)
    duration = time.perf_counter() - started
    if record.fallback_used:
        raise ValueError(
            f"query expansion failed for {topic_id} and fell back to the raw question, which is "
            "not the baseline search; nothing was written, run the step again"
        )
    system = adapter.provenance()
    snapshot = SearchSnapshot(
        topic_id=topic_id,
        retrieved_at=f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}",
        duration_s=round(duration, DURATION_DECIMALS),
        search_model=system["models"]["search"],
        search_prompt_version=system["prompt_versions"]["search"],
        synthetic_abstract=record.synthetic_abstract,
        fallback_used=False,
        openalex_params={
            "target_output_count": SEARCH_TARGET_OUTPUT_COUNT,
            "min_citations": SEARCH_MIN_CITATIONS,
            "start_year": topic.min_year,
        },
        papers=record.papers,
    )
    write_json(path, snapshot.model_dump(mode="json"))
    return path
