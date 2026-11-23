import csv
import hashlib
import shutil
from importlib.metadata import version
from pathlib import Path
from typing import Any

import fitz
import pytest

from eval.gold_build.extraction_prepare import (
    answer_path,
    format_pages,
    freeze_paper,
    prefill_schema,
    prepare_extraction,
    quote_problems,
)
from eval.gold_build.extraction_verify import import_verification, write_verification_sheet
from eval.harness.gold import (
    PageText,
    load_extraction_gold,
    load_page_text,
    load_screening_gold,
    validate,
)
from eval.harness.records import SCORED_FIELDS
from eval.harness.text import normalize_ws
from src.pipeline.ingestion.pdf import extract_pages_from_pdf
from tests.unit.eval.conftest import AddTopic, read, read_sheet, write

MODEL = "claude-opus-5-5"
REPO = Path(__file__).resolve().parents[3]
FIXTURE_PDF = REPO / "tests" / "fixtures" / "paper_small_1.pdf"
PREFILL_PROMPT = REPO / "eval" / "gold" / "v0" / "prefill_prompt.md"
PAGES = extract_pages_from_pdf(FIXTURE_PDF)
SNIPPETS = {
    "method": normalize_ws(PAGES[0])[:40],
    "dataset": normalize_ws(PAGES[0])[40:90],
    "limitations": normalize_ws(PAGES[0])[90:140],
}


def good_fields() -> list[dict[str, Any]]:
    return [
        {"field": name, "value": f"{name} value", "page": 1, "quote": quote}
        for name, quote in SNIPPETS.items()
    ]


def claude_answer(fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {"structured_output": {"fields": fields}, "modelUsage": {MODEL: {}}}


class Downloads:
    """A stand-in for `download_pdf` that copies the fixture PDF and counts its calls."""

    def __init__(self, succeed: bool = True):
        self.succeed = succeed
        self.calls: list[tuple[str, Path]] = []

    def __call__(self, url: str, path: Path) -> bool:
        self.calls.append((url, path))
        if self.succeed:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(FIXTURE_PDF, path)
        return self.succeed


class Claude:
    """A stand-in runner that answers from a list and records its calls."""

    def __init__(self, *answers: list[dict[str, Any]]):
        self.answers = list(answers)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return claude_answer(self.answers.pop(0))


@pytest.fixture
def world(add_topic: AddTopic, gold_dir: Path) -> None:
    """ta_mini with WA1 a gold include in the screening set; the prefill prompt in place."""
    add_topic("ta_mini", ["include"] * 12, prefix="WA")
    labels = read(gold_dir / "screening.json")
    labels[0]["in_screening_set"] = True
    write(gold_dir / "screening.json", labels)
    shutil.copy(PREFILL_PROMPT, gold_dir / "prefill_prompt.md")


def prepare(
    gold_dir: Path, data_root: Path, claude: Claude, downloads: Downloads, key: str = "WA1"
) -> list[str]:
    return prepare_extraction(
        MODEL, [key], data_root=data_root, gold_dir=gold_dir, download=downloads, runner=claude
    )


# --- helpers -------------------------------------------------------------------------------


def test_the_pages_get_a_marker_each_that_the_prompt_refers_to():
    assert format_pages(["first", "second"]) == "PAGE 1\nfirst\n\nPAGE 2\nsecond"


def test_the_schema_allows_exactly_the_five_scored_fields():
    schema = prefill_schema()

    assert schema["properties"]["fields"]["items"]["properties"]["field"]["enum"] == list(
        SCORED_FIELDS
    )
    assert schema["properties"]["fields"]["items"]["required"] == [
        "field",
        "value",
        "page",
        "quote",
    ]


def test_quote_problems_find_repeated_fields_missing_pages_and_quotes_that_are_not_on_the_page():
    pages = ["Interviews were held\nwith twenty teenagers.", "Page two says something else."]
    fields = [
        {
            "field": "method",
            "value": "v",
            "page": 1,
            "quote": "Interviews were held with twenty teenagers.",
        },
        {"field": "dataset", "value": "v", "page": 2, "quote": "Interviews were held"},
        {"field": "task", "value": "v", "page": 3, "quote": "anything"},
        {"field": "task", "value": "v", "page": 1, "quote": ""},
    ]

    assert quote_problems(fields, pages) == [
        "task appears twice",
        "the quote of dataset is not on page 2",
        "task cites page 3, the PDF has 2",
        "the quote of task is not on page 1",
    ]


# --- freezing ------------------------------------------------------------------------------


def test_a_paper_is_frozen_as_pdf_hash_and_page_text_and_reused_the_second_time(data_root: Path):
    downloads = Downloads()

    page_text = freeze_paper("WA1", "https://fixtures.invalid/WA1.pdf", data_root, downloads)
    again = freeze_paper("WA1", "https://fixtures.invalid/WA1.pdf", data_root, downloads)

    assert downloads.calls == [("https://fixtures.invalid/WA1.pdf", data_root / "pdfs" / "WA1.pdf")]
    assert page_text == again == load_page_text(data_root, "WA1")
    assert page_text.pdf_sha256 == hashlib.sha256(FIXTURE_PDF.read_bytes()).hexdigest()
    assert page_text.pymupdf_version == version("pymupdf")
    assert page_text.pdf_url == "https://fixtures.invalid/WA1.pdf"
    assert page_text.pages == PAGES


def test_a_failed_download_is_reported_with_the_url(data_root: Path):
    with pytest.raises(
        ValueError, match="WA1: the PDF could not be downloaded from https://x.test/a.pdf"
    ):
        freeze_paper("WA1", "https://x.test/a.pdf", data_root, Downloads(succeed=False))


def test_page_text_that_belongs_to_another_pdf_is_refused(data_root: Path):
    freeze_paper("WA1", "https://x.test/a.pdf", data_root, Downloads())
    stored = PageText.model_validate(read(data_root / "pages" / "WA1.json"))
    write(
        data_root / "pages" / "WA1.json",
        stored.model_copy(update={"pdf_sha256": "0" * 64}).model_dump(),
    )

    with pytest.raises(ValueError, match="WA1: the page text belongs to another PDF"):
        freeze_paper("WA1", "https://x.test/a.pdf", data_root, Downloads())


def test_a_pdf_without_text_is_refused(data_root: Path):
    def blank_pdf(url: str, path: Path) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open() as document:
            document.new_page()
            document.save(path)
        return True

    with pytest.raises(ValueError, match="WA1: the PDF has no extractable text"):
        freeze_paper("WA1", "https://x.test/a.pdf", data_root, blank_pdf)


# --- prepare -------------------------------------------------------------------------------


def test_the_pre_fill_gets_the_prompt_the_schema_and_the_marked_pages_in_the_labeling_folder(
    world: None, gold_dir: Path, data_root: Path
):
    claude = Claude(good_fields())

    failures = prepare(gold_dir, data_root, claude, Downloads())

    assert failures == []
    (call,) = claude.calls
    assert call["model"] == MODEL
    assert call["system_prompt"] == PREFILL_PROMPT.read_text("utf-8")
    assert call["schema"] == prefill_schema()
    assert call["text"] == format_pages(PAGES)
    assert call["cwd"] == data_root / "labeling"
    assert read(answer_path(data_root, "WA1"))["structured_output"]["fields"] == good_fields()


def test_the_pre_fill_model_and_prompt_hash_go_into_the_provenance(
    world: None, gold_dir: Path, data_root: Path
):
    prepare(gold_dir, data_root, Claude(good_fields()), Downloads())

    provenance = read(gold_dir / "provenance.json")
    assert provenance["prefill_model"] == MODEL
    assert (
        provenance["prefill_prompt_sha256"]
        == hashlib.sha256(PREFILL_PROMPT.read_bytes()).hexdigest()
    )
    assert provenance["dates"]["extraction_prefill"]


def test_an_answer_that_passes_the_quote_check_is_not_asked_for_again(
    world: None, gold_dir: Path, data_root: Path
):
    prepare(gold_dir, data_root, Claude(good_fields()), Downloads())
    claude = Claude()

    assert prepare(gold_dir, data_root, claude, Downloads()) == []
    assert claude.calls == []


def test_quotes_that_are_not_on_their_page_are_listed_and_sent_back_on_the_next_run(
    world: None, gold_dir: Path, data_root: Path
):
    bad = [{**good_fields()[0], "quote": "A sentence that is not in the paper."}]
    assert prepare(gold_dir, data_root, Claude(bad), Downloads()) == [
        "WA1: the quote of method is not on page 1"
    ]
    claude = Claude(good_fields())

    failures = prepare(gold_dir, data_root, claude, Downloads())

    assert failures == []
    (call,) = claude.calls
    assert call["text"].startswith(format_pages(PAGES))
    assert "had these problems" in call["text"]
    assert "- the quote of method is not on page 1" in call["text"]
    assert len(read(answer_path(data_root, "WA1"))["structured_output"]["fields"]) == 3


@pytest.mark.parametrize(
    ("key", "message"),
    [
        ("WA2", "WA2 must be a gold include in the screening set"),
        ("WA99", "WA99 must be a gold include in the screening set"),
    ],
)
def test_only_gold_includes_of_the_screening_set_are_prepared(
    world: None, gold_dir: Path, data_root: Path, key: str, message: str
):
    with pytest.raises(ValueError, match=message):
        prepare(gold_dir, data_root, Claude(), Downloads(), key)


def test_a_paper_without_a_pdf_link_is_refused(world: None, gold_dir: Path, data_root: Path):
    pool = read(gold_dir / "ta_mini" / "pool.json")
    pool[0]["pdf_url"] = None
    write(gold_dir / "ta_mini" / "pool.json", pool)

    with pytest.raises(ValueError, match="WA1 has no PDF URL"):
        prepare(gold_dir, data_root, Claude(), Downloads())


# --- verify --------------------------------------------------------------------------------


@pytest.fixture
def prefilled(world: None, gold_dir: Path, data_root: Path) -> None:
    prepare(gold_dir, data_root, Claude(list(reversed(good_fields()))), Downloads())


def fill_verdicts(data_root: Path, verdicts: list[str]) -> None:
    path = data_root / "labeling" / "extraction_sheet.csv"
    rows = read_sheet(path)
    for row, verdict in zip(rows, verdicts, strict=True):
        row["verdict"] = verdict
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_the_sheet_lists_every_pre_filled_field_in_field_order_with_an_empty_verdict(
    prefilled: None, data_root: Path
):
    path = write_verification_sheet(data_root=data_root)

    rows = read_sheet(path)
    assert path == data_root / "labeling" / "extraction_sheet.csv"
    assert list(rows[0]) == ["paper_key", "field", "value", "page", "quote", "verdict"]
    assert [(r["paper_key"], r["field"], r["page"]) for r in rows] == [
        ("WA1", "method", "1"),
        ("WA1", "dataset", "1"),
        ("WA1", "limitations", "1"),
    ]
    assert rows[0]["quote"] == SNIPPETS["method"] and rows[0]["verdict"] == ""


def test_the_sheet_needs_answers_that_pass_the_quote_check_and_is_never_overwritten(
    prefilled: None, data_root: Path
):
    write_verification_sheet(data_root=data_root)
    with pytest.raises(ValueError, match="extraction_sheet.csv already exists"):
        write_verification_sheet(data_root=data_root)

    (data_root / "labeling" / "extraction_sheet.csv").unlink()
    broken = read(answer_path(data_root, "WA1"))
    broken["structured_output"]["fields"][0]["quote"] = "not in the paper"
    write(answer_path(data_root, "WA1"), broken)
    with pytest.raises(ValueError, match="WA1: .*not on page.*run extraction_prepare again"):
        write_verification_sheet(data_root=data_root)


def test_the_sheet_without_any_answer_asks_for_the_prepare_step(data_root: Path):
    with pytest.raises(ValueError, match="run extraction_prepare first"):
        write_verification_sheet(data_root=data_root)


def test_ok_rows_become_model_verified_gold_and_wrong_rows_are_dropped(
    prefilled: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    write_verification_sheet(data_root=data_root)
    fill_verdicts(data_root, ["ok", "wrong", " OK "])

    count = import_verification(data_root=data_root, gold_dir=gold_dir)

    assert count == 1
    (paper,) = load_extraction_gold(gold_dir)
    assert (paper.paper_key, paper.topic_id) == ("WA1", "ta_mini")
    assert paper.pdf_sha256 == hashlib.sha256(FIXTURE_PDF.read_bytes()).hexdigest()
    assert paper.pdf_url == "https://fixtures.invalid/WA1.pdf"
    assert [(f.field, f.source, f.page) for f in paper.fields] == [
        ("method", "model_verified", 1),
        ("limitations", "model_verified", 1),
    ]
    assert paper.fields[0].quote == SNIPPETS["method"]
    assert read(gold_dir / "provenance.json")["dates"]["extraction_verification"]


def test_the_imported_extraction_gold_passes_the_validators_quote_and_hash_checks(
    prefilled: None, gold_dir: Path, data_root: Path, topics_dir: Path
):
    write_verification_sheet(data_root=data_root)
    fill_verdicts(data_root, ["ok", "ok", "ok"])
    import_verification(data_root=data_root, gold_dir=gold_dir)

    report = validate(gold_dir, data_root, topics_dir=topics_dir)

    assert [e for e in report.errors if e.startswith("extraction ")] == []
    assert load_screening_gold(gold_dir)[0].in_screening_set


@pytest.mark.parametrize("verdict", ["", "maybe"])
def test_every_row_needs_ok_or_wrong(
    prefilled: None, gold_dir: Path, data_root: Path, verdict: str
):
    write_verification_sheet(data_root=data_root)
    fill_verdicts(data_root, ["ok", verdict, "ok"])

    with pytest.raises(
        ValueError, match=f"extraction_sheet.csv row 3: verdict '{verdict}' is not one of"
    ):
        import_verification(data_root=data_root, gold_dir=gold_dir)

    assert not (gold_dir / "extraction.json").exists()
