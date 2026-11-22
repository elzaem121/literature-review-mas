"""The ingestion node on the memory repository: upsert, PDF resolution, chunking, skip rules."""

import asyncio
import shutil
from pathlib import Path

import fitz
import pytest

from src.db.repository import get_repository
from src.llm.settings import get_settings
from src.pipeline.ingestion import node as ingestion_node
from src.pipeline.ingestion.chunking import CHUNKER_VERSION
from src.pipeline.ingestion.pdf import pdf_path_for

FIXTURE_PDF = Path(__file__).resolve().parents[1] / "fixtures" / "paper_small_1.pdf"
FIELDS = {"method_chunks", "dataset_chunks", "task_chunks", "findings_chunks", "limitations_chunks"}


class PdfSource:
    """Stands in for the network: records download calls and serves one canned PDF per URL."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        self.downloads: list[str] = []
        self.failing_urls: set[str] = set()
        self.fallback_url: str | None = None
        self.writer = lambda path: shutil.copyfile(FIXTURE_PDF, path)
        monkeypatch.setenv("PDF_DIR", str(tmp_path))
        get_settings.cache_clear()
        monkeypatch.setattr(ingestion_node, "download_pdf", self._download)
        monkeypatch.setattr(ingestion_node, "get_openalex_pdf_url", lambda doi: self.fallback_url)

    def _download(self, url: str, path: Path) -> bool:
        self.downloads.append(url)
        if url in self.failing_urls:
            return False
        self.writer(path)
        return True


@pytest.fixture
def source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> PdfSource:
    return PdfSource(monkeypatch, tmp_path)


def _paper(openalex_id: str, doi: str | None, pdf_url: str | None = "https://x.invalid/a.pdf"):
    return {
        "paper": {
            "title": f"Paper {openalex_id}",
            "openalex_id": openalex_id,
            "doi": doi,
            "year": 2022,
            "authors": ["Ada Lovelace"],
            "venue": None,
            "pdf_url": pdf_url,
        }
    }


def _run(*papers: dict) -> dict:
    state = {"screening_results": {"included_papers": list(papers)}}
    return asyncio.run(ingestion_node.document_processing_node(state))


def _status(result: dict, index: int = 0) -> str:
    paper = result["screening_results"]["included_papers"][index]
    return paper["paper"].get("pdf_status") or paper["pdf_status"]


def test_distinct_papers_are_stored_downloaded_and_chunked_once_each(source: PdfSource):
    result = _run(
        _paper("W1", "10.1/a", "https://x.invalid/1.pdf"),
        _paper("W2", "10.1/b", "https://x.invalid/2.pdf"),
    )

    repository = get_repository()
    assert source.downloads == ["https://x.invalid/1.pdf", "https://x.invalid/2.pdf"]
    assert [repository.get_paper(i).ingestion_status for i in (1, 2)] == ["chunked", "chunked"]
    for paper in result["screening_results"]["included_papers"]:
        assert paper["paper"]["pdf_status"] == "Downloaded"
        assert set(paper["retrieved_chunks_by_field"]) == FIELDS
        assert all(paper["retrieved_chunks_by_field"].values())
    assert "2 out of 2" in result["status_message"]


def test_a_second_run_skips_download_and_chunking_and_returns_the_same_state(
    source: PdfSource, monkeypatch: pytest.MonkeyPatch
):
    first = _run(_paper("W1", "10.1/a"))
    pdf_path_for(1).unlink()  # even a cleared PDF volume must not trigger a new download
    repository = get_repository()
    replacements: list[int] = []
    replace_chunks = repository.replace_chunks
    monkeypatch.setattr(
        repository,
        "replace_chunks",
        lambda paper_id, *args: (replacements.append(paper_id), replace_chunks(paper_id, *args)),
    )

    second = _run(_paper("W1", "10.1/a"))

    assert len(source.downloads) == 1
    assert replacements == []
    assert second["screening_results"] == first["screening_results"]


def test_two_openalex_records_with_one_doi_become_one_paper_with_one_download(source: PdfSource):
    result = _run(_paper("W1", "https://doi.org/10.1/A"), _paper("W2", "10.1/a"))

    first, second = result["screening_results"]["included_papers"]
    assert len(source.downloads) == 1
    assert first["retrieved_chunks_by_field"] == second["retrieved_chunks_by_field"]
    assert get_repository().get_paper(2) is None


def test_the_doi_lookup_is_the_fallback_when_the_stored_url_fails(source: PdfSource):
    source.failing_urls = {"https://x.invalid/a.pdf"}
    source.fallback_url = "https://fallback.invalid/a.pdf"

    result = _run(_paper("W1", "10.1/a"))

    assert source.downloads == ["https://x.invalid/a.pdf", "https://fallback.invalid/a.pdf"]
    assert _status(result) == "Downloaded"


def test_a_paper_without_any_pdf_url_is_flagged_not_available(source: PdfSource):
    result = _run(_paper("W1", "10.1/a", pdf_url=None))

    paper = get_repository().get_paper(1)
    assert _status(result) == "Not Available"
    assert (paper.ingestion_status, paper.last_error) == (
        "pdf_unavailable",
        "No PDF URL found for this paper",
    )
    assert source.downloads == []
    assert "0 out of 1" in result["status_message"]


def test_a_paper_whose_downloads_all_fail_is_flagged_download_failed(source: PdfSource):
    source.failing_urls = {"https://x.invalid/a.pdf", "https://fallback.invalid/a.pdf"}
    source.fallback_url = "https://fallback.invalid/a.pdf"

    result = _run(_paper("W1", "10.1/a"))

    paper = get_repository().get_paper(1)
    assert _status(result) == "Download Failed"
    assert paper.ingestion_status == "pdf_unavailable"
    assert "https://x.invalid/a.pdf" in paper.last_error


def test_a_cached_pdf_is_used_without_downloading(source: PdfSource):
    get_repository().upsert_paper(
        openalex_id="W1", doi=None, title="t", year=None, authors=[], venue=None, pdf_url=None
    )
    shutil.copyfile(FIXTURE_PDF, pdf_path_for(1))

    result = _run(_paper("W1", "10.1/a"))

    assert source.downloads == []
    assert _status(result) == "Downloaded"


def test_a_pdf_without_text_is_flagged_extraction_failed(source: PdfSource):
    def write_blank_pdf(path: Path) -> None:
        document = fitz.open()
        document.new_page()
        document.save(path)

    source.writer = write_blank_pdf

    result = _run(_paper("W1", "10.1/a"))

    paper = get_repository().get_paper(1)
    assert _status(result) == "Extraction Failed"
    assert (paper.ingestion_status, paper.last_error) == (
        "failed",
        "The PDF has no extractable text",
    )


def test_a_broken_pdf_is_flagged_extraction_failed(source: PdfSource):
    source.writer = lambda path: path.write_bytes(b"%PDF-1.7 this is not a pdf")

    result = _run(_paper("W1", "10.1/a"))

    paper = get_repository().get_paper(1)
    assert _status(result) == "Extraction Failed"
    assert paper.ingestion_status == "failed"
    assert paper.last_error.startswith("Text extraction failed")


def test_a_failed_paper_is_attempted_again_on_the_next_run(source: PdfSource):
    source.failing_urls = {"https://x.invalid/a.pdf"}
    assert _status(_run(_paper("W1", "10.1/a"))) == "Download Failed"

    source.failing_urls = set()
    result = _run(_paper("W1", "10.1/a"))

    assert _status(result) == "Downloaded"
    assert get_repository().get_paper(1).last_error is None


def test_a_new_chunker_version_rechunks_from_the_cached_pdf(
    source: PdfSource, monkeypatch: pytest.MonkeyPatch
):
    _run(_paper("W1", "10.1/a"))
    monkeypatch.setattr(ingestion_node, "CHUNKER_VERSION", "v-next")

    _run(_paper("W1", "10.1/a"))

    repository = get_repository()
    model = get_settings().embedding_model
    assert len(source.downloads) == 1
    assert repository.is_chunked(1, model, "v-next")
    assert not repository.is_chunked(1, model, CHUNKER_VERSION)


def test_a_new_embedding_model_rechunks_from_the_cached_pdf(
    source: PdfSource, monkeypatch: pytest.MonkeyPatch
):
    _run(_paper("W1", "10.1/a"))
    monkeypatch.setenv("EMBEDDING_MODEL", "other-model")
    get_settings.cache_clear()

    _run(_paper("W1", "10.1/a"))

    assert len(source.downloads) == 1
    assert get_repository().is_chunked(1, "other-model", CHUNKER_VERSION)


def test_a_paper_without_an_openalex_id_fails_loudly(source: PdfSource):
    paper = _paper("W1", "10.1/a")
    paper["paper"]["openalex_id"] = None

    with pytest.raises(ValueError, match="Paper 'Paper W1' has no openalex_id"):
        _run(paper)
