"""File helpers shared by the gold-build steps: JSON and CSV, provenance, answers, topics."""

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from eval.harness.gold import ScreeningGold, load_screening_gold
from eval.harness.records import CheckAnswer
from eval.harness.topics import ANSWERS, TOPICS_DIR, Topic, load_topic

PROVENANCE_FILE = "provenance.json"
SCREENING_FILE = "screening.json"
LABELING_DIR = "labeling"


def write_json(path: Path, value: Any) -> None:
    """Write JSON with UTF-8 and 2-space indentation, creating the folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    """Read a JSON file; a missing file raises with its path."""
    return json.loads(path.read_text(encoding="utf-8"))


def dump_models(items: list[BaseModel], item_type: type[BaseModel]) -> list[Any]:
    """The JSON-ready form of a list of models."""
    return TypeAdapter(list[item_type]).dump_python(items, mode="json")


def sha256_bytes(content: bytes) -> str:
    """The hex SHA-256 of some bytes."""
    return hashlib.sha256(content).hexdigest()


def today() -> str:
    """The current UTC date, ISO 8601."""
    return f"{datetime.now(UTC):%Y-%m-%d}"


def update_provenance(gold_dir: Path, updates: dict[str, Any], *, dated: str | None = None) -> None:
    """Merge fields into `provenance.json`; `dated` also stamps today's date for that step."""
    path = gold_dir / PROVENANCE_FILE
    provenance = read_json(path) if path.is_file() else {}
    provenance.update(updates)
    if dated:
        provenance["dates"] = {**provenance.get("dates", {}), dated: today()}
    write_json(path, provenance)


def read_provenance(gold_dir: Path) -> dict[str, Any]:
    """`provenance.json` as a dict; {} when there is none yet."""
    path = gold_dir / PROVENANCE_FILE
    return read_json(path) if path.is_file() else {}


def load_topics(topics_dir: Path = TOPICS_DIR) -> dict[str, Topic]:
    """Every topic config in the folder, by topic id."""
    ids = sorted(path.stem for path in topics_dir.glob("*.json"))
    if not ids:
        raise ValueError(f"no topic configs in {topics_dir}")
    return {topic_id: load_topic(topic_id, topics_dir) for topic_id in ids}


def load_labels(gold_dir: Path) -> list[ScreeningGold]:
    """`screening.json`, or an empty list before the first import."""
    if not (gold_dir / SCREENING_FILE).is_file():
        return []
    return load_screening_gold(gold_dir)


def save_labels(gold_dir: Path, records: list[ScreeningGold]) -> None:
    """Write `screening.json`."""
    write_json(gold_dir / SCREENING_FILE, dump_models(records, ScreeningGold))


def labeling_dir(data_root: Path) -> Path:
    """The labeling work folder inside the data folder."""
    return data_root / LABELING_DIR


def parse_answer(cell: str, where: str) -> CheckAnswer:
    """A human's sheet cell as a check answer; blanks and unknown words fail naming the place."""
    answer = cell.strip().lower().replace(" ", "_").replace("-", "_")
    if answer not in ANSWERS:
        raise ValueError(f"{where}: '{cell}' is not one of {list(ANSWERS)}")
    return answer  # type: ignore[return-value]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    """Write a sheet for a human; refuses to overwrite one, since it may hold their work."""
    if path.exists():
        raise ValueError(f"{path} already exists and may hold answers; move it away to start over")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path, columns: list[str]) -> list[dict[str, str]]:
    """Read a sheet back; it must still have every column it was written with."""
    if not path.is_file():
        raise ValueError(f"{path} does not exist; write the sheet first")
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = [column for column in columns if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path} lacks the columns {missing}")
        return list(reader)
