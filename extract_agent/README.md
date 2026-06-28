# RAG-Based Extraction Agent

## Overview

This project implements a RAG-based Extraction Agent for a multi-agent literature-review system.

The agent processes scientific papers and extracts structured academic information using semantic retrieval and LLM-based analysis.

The system is designed to avoid hardcoded rules and instead uses:

* semantic search
* embeddings
* generic query-based retrieval
* field-specific retrieval
* LLM prompting
* self-verification rules to reduce hallucinations

---

## Pipeline

1. Search
2. Screening
3. Automatic PDF download
4. PDF storage
5. Full-text extraction
6. Chunking
7. Embedding generation
8. Semantic retrieval
9. Field-specific chunk retrieval
10. RAG-based extraction with Qwen3
11. Structured JSON output

---

## Technologies

* Python
* Ollama
* Qwen3
* Instructor
* FAISS
* SentenceTransformers
* PyMuPDF
* Pydantic

---

## Files

### Core Files

* `auto_pdf_downloader.py`
* `add_full_text_from_pdfs.py`
* `extraction_schemas.py`
* `rag_chunker.py`
* `rag_retriever.py`
* `rag_extraction_main.py`

### Data Files

* `search_results.json`
* `papers_with_auto_pdfs.json`
* `papers_with_full_text.json`
* `chunked_papers.json`
* `retrieved_chunks.json`
* `rag_extraction_results.json`

---

## RAG Workflow

Search Results  
→ Automatic PDF Download  
→ PDF Storage  
→ Full-text Extraction  
→ Chunking  
→ Embeddings  
→ Semantic Retrieval  
→ Field-specific Relevant Chunks  
→ Qwen3  
→ Structured Extraction

---

## Usage

Run the pipeline step by step:

```bash
python auto_pdf_downloader.py
python add_full_text_from_pdfs.py
python rag_chunker.py
python rag_retriever.py
python rag_extraction_main.py