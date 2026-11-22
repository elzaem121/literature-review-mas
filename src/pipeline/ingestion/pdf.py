from pathlib import Path

import fitz  # PyMuPDF
import requests

from src.llm.settings import get_settings

PDF_MAGIC = b"%PDF"


def pdf_path_for(paper_id: int) -> Path:
    """Return the path of a paper's PDF in the configured PDF directory, keyed by its library id."""
    return get_settings().pdf_dir / f"{paper_id}.pdf"


def is_cached_pdf(path: Path) -> bool:
    """True if the file exists and starts with the PDF magic bytes."""
    if not path.is_file():
        return False
    with path.open("rb") as file:
        return file.read(len(PDF_MAGIC)) == PDF_MAGIC


def get_openalex_pdf_url(doi: str) -> str | None:
    if not doi:
        return None
    doi_clean = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    openalex_url = f"https://api.openalex.org/works/https://doi.org/{doi_clean}"

    try:
        response = requests.get(openalex_url, timeout=20)
        if response.status_code != 200:
            return None

        work = response.json()
        open_access = work.get("open_access") or {}
        locations = work.get("locations") or []

        candidates = []
        if open_access.get("oa_url"):
            candidates.append(open_access["oa_url"])

        for loc in locations:
            pdf_url = loc.get("pdf_url")
            landing_page_url = loc.get("landing_page_url")
            if pdf_url:
                candidates.append(pdf_url)
            if landing_page_url and landing_page_url.endswith(".pdf"):
                candidates.append(landing_page_url)

        for url in candidates:
            if url and (".pdf" in url.lower() or "download" in url.lower() or "pdf" in url.lower()):
                return url

        return candidates[0] if candidates else None
    except Exception as e:
        print(f"[API ERROR] OpenAlex fetch failed: {e}")
        return None


def download_pdf(url: str, output_path: Path) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        if response.status_code != 200:
            return False
        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" not in content_type and not response.content.startswith(PDF_MAGIC):
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return True
    except Exception:
        return False


def extract_pages_from_pdf(pdf_path: Path) -> list[str]:
    """Return the text of each page in order; raises a RuntimeError (PyMuPDF) for a broken PDF."""
    with fitz.open(pdf_path) as document:
        return [page.get_text() for page in document]
