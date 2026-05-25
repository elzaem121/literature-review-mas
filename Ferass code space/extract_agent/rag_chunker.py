import json
from pathlib import Path


INPUT_FILE = Path("papers_with_full_text.json")
OUTPUT_FILE = Path("chunked_papers.json")

CHUNK_SIZE = 1200


def chunk_text(text: str, chunk_size: int = 1200):
    chunks = []

    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        chunks.append(chunk)

    return chunks


with INPUT_FILE.open("r", encoding="utf-8") as file:
    data = json.load(file)


for paper in data["papers"]:

    full_text = paper.get("full_text")

    if full_text:

        chunks = chunk_text(full_text, CHUNK_SIZE)

        paper["chunks"] = chunks

        print(f"[CHUNKED] {paper['title']}")
        print(f"Chunks: {len(chunks)}")

    else:
        print(f"[SKIPPED] No full text: {paper['title']}")


with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)


print(f"\nSaved chunked papers to: {OUTPUT_FILE}")