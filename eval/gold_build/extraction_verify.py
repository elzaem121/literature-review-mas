"""Step `extraction_verify`: the human checks each pre-filled field; the import writes the gold."""

from pathlib import Path

from eval.gold_build.extraction_prepare import EXTRACTION_ANSWERS, quote_problems
from eval.gold_build.files import (
    dump_models,
    labeling_dir,
    load_labels,
    read_csv,
    read_json,
    update_provenance,
    write_csv,
    write_json,
)
from eval.harness.gold import (
    DEFAULT_GOLD_DIR,
    ExtractionFieldGold,
    ExtractionGold,
    load_page_text,
)
from eval.harness.records import SCORED_FIELDS

EXTRACTION_SHEET = "extraction_sheet.csv"
EXTRACTION_COLUMNS = ["paper_key", "field", "value", "page", "quote", "verdict"]
VERDICTS = ("ok", "wrong")


def write_verification_sheet(*, data_root: Path) -> Path:
    """Write the sheet of every pre-filled field with an empty verdict column."""
    paths = sorted((labeling_dir(data_root) / EXTRACTION_ANSWERS).glob("*.json"))
    if not paths:
        raise ValueError("no pre-filled extraction answers; run extraction_prepare first")
    rows: list[dict[str, str]] = []
    for path in paths:
        fields = read_json(path)["structured_output"]["fields"]
        pages = load_page_text(data_root, path.stem).pages
        problems = quote_problems(fields, pages)
        if problems:
            raise ValueError(f"{path.stem}: {'; '.join(problems)}; run extraction_prepare again")
        for item in sorted(fields, key=lambda f: SCORED_FIELDS.index(f["field"])):
            rows.append(
                {
                    "paper_key": path.stem,
                    "field": item["field"],
                    "value": item["value"],
                    "page": str(item["page"]),
                    "quote": item["quote"],
                    "verdict": "",
                }
            )
    sheet = labeling_dir(data_root) / EXTRACTION_SHEET
    write_csv(sheet, EXTRACTION_COLUMNS, rows)
    return sheet


def import_verification(*, data_root: Path, gold_dir: Path = DEFAULT_GOLD_DIR) -> int:
    """Write `extraction.json` from the filled sheet: `ok` rows are kept, `wrong` rows dropped."""
    rows = read_csv(labeling_dir(data_root) / EXTRACTION_SHEET, EXTRACTION_COLUMNS)
    topics = {r.paper_key: r.topic_id for r in load_labels(gold_dir)}
    fields_by_paper: dict[str, list[ExtractionFieldGold]] = {}
    for number, row in enumerate(rows, start=2):
        verdict = row["verdict"].strip().lower()
        if verdict not in VERDICTS:
            raise ValueError(
                f"{EXTRACTION_SHEET} row {number}: verdict '{row['verdict']}' is not one of "
                f"{list(VERDICTS)}"
            )
        fields = fields_by_paper.setdefault(row["paper_key"], [])
        if verdict == "ok":
            fields.append(
                ExtractionFieldGold(
                    field=row["field"],
                    value=row["value"],
                    page=int(row["page"]),
                    quote=row["quote"],
                    source="model_verified",
                )
            )
    papers = []
    for key, fields in sorted(fields_by_paper.items()):
        page_text = load_page_text(data_root, key)
        papers.append(
            ExtractionGold(
                paper_key=key,
                topic_id=topics[key],
                pdf_url=page_text.pdf_url,
                pdf_sha256=page_text.pdf_sha256,
                fields=fields,
            )
        )
    write_json(gold_dir / "extraction.json", dump_models(papers, ExtractionGold))
    update_provenance(gold_dir, {}, dated="extraction_verification")
    return len(papers)
