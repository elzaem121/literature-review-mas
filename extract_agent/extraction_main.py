import json
import fitz
import os
import asyncio
from pathlib import Path

from extraction_agent import AcademicExtractionAgent


def extract_text_from_pdf(pdf_path):

    doc = fitz.open(pdf_path)

    full_text = ""

    for page in doc:
        full_text += page.get_text()

    return full_text
async def main():
    research_question = "How does social media shape adolescents' lifeworlds and everyday experiences?"

    input_path = Path("sample_screening_results.json")
    output_path = Path("extraction_results.json")
    pdf_folder = "extract_agent/pdfs"

    pdf_texts = {}

    for filename in os.listdir(pdf_folder):

        if filename.endswith(".pdf"):
            pdf_path = os.path.join(pdf_folder, filename)

            full_text = extract_text_from_pdf(pdf_path)

            pdf_texts[filename] = full_text

    print(f"Loaded {len(pdf_texts)} PDF full texts.")
    input_path = Path("sample_screening_results.json")

    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    for paper, full_text in zip(data["papers"], pdf_texts.values()):
        paper["full_text"] = full_text

    with input_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    print(f"Added full_text to {min(len(data['papers']), len(pdf_texts))} papers.")

    agent = AcademicExtractionAgent(
        model_name="qwen2.5-coder:7b",
        max_concurrent_tasks=2,
    )

    try:
        result = await agent.extract_file(
            input_path=input_path,
            output_path=output_path,
            research_question=research_question,
        )

        print("\n=== EXTRACTION SUMMARY ===")
        print(f"Extracted papers: {len(result.extracted_papers)}")
        print(f"[SUCCESS] Extraction results saved to: {output_path}")

    except Exception as error:
        print(f"[ERROR] Extraction pipeline failed: {error}")


if __name__ == "__main__":
    asyncio.run(main())