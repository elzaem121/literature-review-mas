import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


INPUT_FILE = Path("chunked_papers.json")
OUTPUT_FILE = Path("retrieved_chunks.json")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

QUERIES = [
    "research method study design data collection sample participants",
    "dataset data source interviews survey observations participants",
    "main findings results key outcomes social media adolescents",
    "limitations weaknesses study limitations future research",
]


def embed_texts(model, texts):
    embeddings = model.encode(texts, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")
    faiss.normalize_L2(embeddings)
    return embeddings


with INPUT_FILE.open("r", encoding="utf-8") as file:
    data = json.load(file)


print("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)


for paper in data["papers"]:
    chunks = paper.get("chunks", [])

    if not chunks:
        print(f"[SKIPPED] No chunks: {paper.get('title')}")
        continue

    print(f"\n[PROCESSING] {paper.get('title')}")
    print(f"Chunks: {len(chunks)}")

    chunk_embeddings = embed_texts(model, chunks)

    dimension = chunk_embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(chunk_embeddings)

    selected_chunks = []

    query_embeddings = embed_texts(model, QUERIES)

    distances, indices = index.search(query_embeddings, k=3)

    for query_idx, query in enumerate(QUERIES):
        for chunk_idx in indices[query_idx]:
            chunk_text = chunks[int(chunk_idx)]

            if chunk_text not in selected_chunks:
                selected_chunks.append(chunk_text)

    paper["retrieved_chunks"] = selected_chunks

    print(f"Retrieved chunks: {len(selected_chunks)}")


with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)


print(f"\nSaved retrieved chunks to: {OUTPUT_FILE}")