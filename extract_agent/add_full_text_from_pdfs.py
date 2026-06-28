import json
from pathlib import Path

import fitz


INPUT_FILE = Path("papers_with_auto_pdfs.json")
OUTPUT_FILE = Path("papers_with_full_text.json")


def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)

    full_text = ""

    for page in doc:
        full_text += page.get_text()

    return full_text


with INPUT_FILE.open("r", encoding="utf-8") as file:
    data = json.load(file)


for paper in data["papers"]:
    pdf_path = paper.get("pdf_path")

    if pdf_path:
        print(f"[EXTRACTING FULL TEXT] {pdf_path}")

        full_text = extract_text_from_pdf(pdf_path)

        paper["full_text"] = full_text
        paper["full_text_status"] = "full_text_extracted"

        print(f"[DONE] {len(full_text)} characters extracted.")

    else:
        print(f"[SKIPPED] No PDF path for: {paper.get('title')}")


with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)


print(f"\nSaved result to: {OUTPUT_FILE}")