# RAG-Based Extraction Agent

## Overview

This project implements a RAG-based Extraction Agent for a multi-agent literature-review system.

The agent processes scientific papers and extracts structured academic information using semantic retrieval and LLM-based analysis.

The system is designed to avoid hardcoded rules and instead uses:
- semantic search
- embeddings
- query-based retrieval
- LLM prompting

---

## Pipeline

1. Search
2. Screening
3. Full-text collection
4. PDF storage
5. Full-text extraction
6. Chunking
7. Embedding generation
8. Semantic retrieval
9. RAG-based extraction with Qwen3

---

## Technologies

- Python
- Ollama
- Qwen3
- Instructor
- FAISS
- SentenceTransformers
- PyMuPDF
- Pydantic

---

## Files

### Core Files

- `extraction_agent.py`
- `rag_chunker.py`
- `rag_retriever.py`
- `rag_extraction_main.py`

### Data Files

- `papers_with_full_text.json`
- `chunked_papers.json`
- `retrieved_chunks.json`
- `rag_extraction_results.json`

---

## RAG Workflow

Full Text
→ Chunking
→ Embeddings
→ Semantic Retrieval
→ Relevant Chunks
→ Qwen3
→ Structured Extraction

---

## Usage

Run the pipeline step by step:

```bash
python add_full_text_from_pdfs.py
python rag_chunker.py
python rag_retriever.py
python rag_extraction_main.py