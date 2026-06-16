import json
from pathlib import Path


INPUT_FILE = Path("sample_screening_results.json")
MAPPING_FILE = Path("manual_pdf_mapping.json")
OUTPUT_FILE = Path("papers_with_manual_pdfs.json")


with INPUT_FILE.open("r", encoding="utf-8") as file:
    data = json.load(file)

with MAPPING_FILE.open("r", encoding="utf-8") as file:
    mapping = json.load(file)


for paper in data["papers"]:
    title = paper.get("title", "")

    if title in mapping:
        pdf_path = mapping[title]

        paper["full_text_status"] = "local_pdf_available"
        paper["pdf_path"] = pdf_path
        paper["download_message"] = "Matched manually with local PDF file."

        print(f"[MATCHED] {title} -> {pdf_path}")
    else:
        print(f"[NO MANUAL MATCH] {title}")


with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)


print(f"\nSaved result to: {OUTPUT_FILE}")