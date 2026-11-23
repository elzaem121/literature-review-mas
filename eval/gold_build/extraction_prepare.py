"""Step `extraction_prepare`: freeze the PDFs and page text, pre-fill the extraction gold."""

from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

from eval.gold_build import claude_cli
from eval.gold_build.files import (
    labeling_dir,
    load_labels,
    read_json,
    sha256_bytes,
    update_provenance,
    write_json,
)
from eval.gold_build.label_run import Runner
from eval.harness.gold import DEFAULT_GOLD_DIR, PageText, load_page_text, load_pool
from eval.harness.records import SCORED_FIELDS
from eval.harness.text import quote_on_page
from src.pipeline.ingestion.pdf import download_pdf, extract_pages_from_pdf

PREFILL_PROMPT_FILE = "prefill_prompt.md"
EXTRACTION_ANSWERS = "extraction_answers"
PDFS = "pdfs"
PAGES = "pages"
PYMUPDF_DISTRIBUTION = "pymupdf"
Downloader = Callable[[str, Path], bool]


def prefill_schema() -> dict[str, Any]:
    """The JSON schema of the pre-fill answer: a list of fields with value, page and quote."""
    item = {
        "type": "object",
        "properties": {
            "field": {"type": "string", "enum": list(SCORED_FIELDS)},
            "value": {"type": "string"},
            "page": {"type": "integer", "minimum": 1},
            "quote": {"type": "string"},
        },
        "required": ["field", "value", "page", "quote"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"fields": {"type": "array", "items": item}},
        "required": ["fields"],
        "additionalProperties": False,
    }


def format_pages(pages: list[str]) -> str:
    """The paper text as the pre-fill prompt describes it: a `PAGE n` marker before each page."""
    return "\n\n".join(f"PAGE {number}\n{text}" for number, text in enumerate(pages, start=1))


def answer_path(data_root: Path, paper_key: str) -> Path:
    """Where the raw pre-fill answer of a paper is saved."""
    return labeling_dir(data_root) / EXTRACTION_ANSWERS / f"{paper_key}.json"


def quote_problems(fields: list[dict[str, Any]], pages: list[str]) -> list[str]:
    """Fields that repeat, cite a page the PDF lacks, or quote text that is not on that page."""
    problems = []
    names = [item["field"] for item in fields]
    problems += [f"{name} appears twice" for name in sorted(set(names)) if names.count(name) > 1]
    for item in fields:
        if item["page"] > len(pages):
            problems.append(f"{item['field']} cites page {item['page']}, the PDF has {len(pages)}")
        elif not quote_on_page(item["quote"], pages[item["page"] - 1]):
            problems.append(f"the quote of {item['field']} is not on page {item['page']}")
    return problems


def freeze_paper(paper_key: str, pdf_url: str, data_root: Path, download: Downloader) -> PageText:
    """Download the PDF, hash it and store its page text; a frozen paper is reused."""
    pdf_path = data_root / PDFS / f"{paper_key}.pdf"
    if not pdf_path.is_file() and not download(pdf_url, pdf_path):
        raise ValueError(f"{paper_key}: the PDF could not be downloaded from {pdf_url}")
    digest = sha256_bytes(pdf_path.read_bytes())
    pages_path = data_root / PAGES / f"{paper_key}.json"
    if pages_path.is_file():
        page_text = load_page_text(data_root, paper_key)
        if page_text.pdf_sha256 != digest:
            raise ValueError(f"{paper_key}: the page text belongs to another PDF than {pdf_path}")
        return page_text
    pages = extract_pages_from_pdf(pdf_path)
    if not any(page.strip() for page in pages):
        raise ValueError(f"{paper_key}: the PDF has no extractable text (is it a scan?)")
    page_text = PageText(
        paper_key=paper_key,
        pymupdf_version=version(PYMUPDF_DISTRIBUTION),
        pdf_url=pdf_url,
        pdf_sha256=digest,
        pages=pages,
    )
    write_json(pages_path, page_text.model_dump(mode="json"))
    return page_text


def _retry_note(problems: list[str]) -> str:
    return (
        "\n\nYour previous answer for this paper had these problems; copy every quote "
        "character for character from the page you name:\n- " + "\n- ".join(problems)
    )


def prepare_extraction(
    model: str,
    paper_keys: list[str],
    *,
    data_root: Path,
    gold_dir: Path = DEFAULT_GOLD_DIR,
    download: Downloader = download_pdf,
    runner: Runner = claude_cli.run_claude,
) -> list[str]:
    """Freeze and pre-fill each paper; return the quote-check failures to re-run, if any.

    A paper whose saved answer already passes the quote check is not asked again; one that
    fails is asked again with its problems.
    """
    prompt_file = gold_dir / PREFILL_PROMPT_FILE
    labels = {r.paper_key: r for r in load_labels(gold_dir)}
    update_provenance(
        gold_dir,
        {"prefill_model": model, "prefill_prompt_sha256": sha256_bytes(prompt_file.read_bytes())},
        dated="extraction_prefill",
    )
    failures: list[str] = []
    for key in paper_keys:
        label = labels.get(key)
        if label is None or not label.in_screening_set or label.decision != "include":
            raise ValueError(f"{key} must be a gold include in the screening set")
        pool_paper = next(p for p in load_pool(gold_dir, label.topic_id) if p.paper_key == key)
        if not pool_paper.pdf_url:
            raise ValueError(f"{key} has no PDF URL")
        page_text = freeze_paper(key, pool_paper.pdf_url, data_root, download)
        path = answer_path(data_root, key)
        problems: list[str] = []
        if path.is_file():
            problems = quote_problems(
                read_json(path)["structured_output"]["fields"], page_text.pages
            )
            if not problems:
                continue
        output = runner(
            model=model,
            system_prompt=prompt_file.read_text(encoding="utf-8"),
            schema=prefill_schema(),
            text=format_pages(page_text.pages) + (_retry_note(problems) if problems else ""),
            cwd=labeling_dir(data_root),
        )
        write_json(path, output)
        failures += [
            f"{key}: {problem}"
            for problem in quote_problems(output["structured_output"]["fields"], page_text.pages)
        ]
    return failures
