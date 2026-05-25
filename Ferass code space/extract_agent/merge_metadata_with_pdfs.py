import json
from pathlib import Path


SEARCH_RESULTS_FILE = Path("search_results.json")
MAPPING_FILE = Path("manual_pdf_mapping.json")
OUTPUT_FILE = Path("papers_with_manual_pdfs.json")


with SEARCH_RESULTS_FILE.open("r", encoding="utf-8") as file:
    search_data = json.load(file)

with MAPPING_FILE.open("r", encoding="utf-8") as file:
    pdf_mapping = json.load(file)


papers = []

for paper in search_data["papers"]:
    title = paper.get("title")

    if title in pdf_mapping:
        paper["pdf_path"] = pdf_mapping[title]
        papers.append(paper)
        print(f"[MATCHED] {title}")
    else:
        print(f"[NO PDF MATCH] {title}")


with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump({"papers": papers}, file, indent=2, ensure_ascii=False)


print(f"\nSaved merged metadata and pdf paths to: {OUTPUT_FILE}")
print(f"Total papers with PDFs: {len(papers)}")