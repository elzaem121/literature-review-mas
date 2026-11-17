import re
from pathlib import Path

import fitz  # PyMuPDF
import requests

PDF_DIR = Path("pdfs_auto")
PDF_DIR.mkdir(exist_ok=True)


def safe_filename(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9]+", "_", title)
    title = title.strip("_")
    return title[:80] + ".pdf"


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
        if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
            return False
        output_path.write_bytes(response.content)
        return True
    except Exception:
        return False


def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        return "".join([page.get_text() for page in doc])
    except Exception:
        return ""
