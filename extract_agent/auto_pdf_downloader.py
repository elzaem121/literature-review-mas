import json
import re
import requests
from pathlib import Path


INPUT_FILE = Path("search_results.json")
OUTPUT_FILE = Path("papers_with_auto_pdfs.json")
PDF_DIR = Path("pdfs_auto")

PDF_DIR.mkdir(exist_ok=True)


def safe_filename(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9]+", "_", title)
    title = title.strip("_")
    return title[:80] + ".pdf"


def get_openalex_pdf_url(doi: str):
    doi_clean = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    openalex_url = f"https://api.openalex.org/works/https://doi.org/{doi_clean}"

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
        source = loc.get("source") or {}
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


def download_pdf(url: str, output_path: Path) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)

        if response.status_code != 200:
            print(f"[DOWNLOAD FAILED] Status code: {response.status_code}")
            return False

        content_type = response.headers.get("Content-Type", "").lower()

        if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
            print(f"[NOT A PDF] Content-Type: {content_type}")
            return False

        output_path.write_bytes(response.content)
        return True

    except Exception as e:
        print(f"[DOWNLOAD ERROR] {e}")
        return False


def main():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    results = []

    for paper in data["papers"]:
        title = paper.get("title", "unknown")
        doi = paper.get("doi")

        print(f"\n[PROCESSING] {title}")

        if not doi:
            paper["pdf_status"] = "no_doi"
            paper["pdf_path"] = None
            results.append(paper)
            print("[SKIPPED] No DOI")
            continue

        pdf_url = get_openalex_pdf_url(doi)

        if not pdf_url:
            paper["pdf_status"] = "no_open_access_pdf_found"
            paper["pdf_path"] = None
            results.append(paper)
            print("[NO PDF FOUND]")
            continue

        print(f"[PDF URL] {pdf_url}")

        filename = safe_filename(title)
        output_path = PDF_DIR / filename

        success = download_pdf(pdf_url, output_path)

        if success:
            paper["pdf_status"] = "downloaded"
            paper["pdf_url"] = pdf_url
            paper["pdf_path"] = str(output_path).replace("\\", "/")
            print(f"[DOWNLOADED] {output_path}")
        else:
            paper["pdf_status"] = "download_failed"
            paper["pdf_url"] = pdf_url
            paper["pdf_path"] = None
            print("[FAILED] Could not download PDF")

        results.append(paper)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump({"papers": results}, f, indent=2, ensure_ascii=False)

    print(f"\nSaved result to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
