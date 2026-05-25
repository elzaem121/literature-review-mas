import asyncio
import json
from pathlib import Path
from typing import List

import instructor
from openai import AsyncOpenAI

from extraction_schemas import (
    ResearchPaper,
    ScreeningAgentOutput,
    ExtractedPaperInfo,
    ExtractedPaper,
    ExtractionOutput,
)


class AcademicExtractionAgent:
    """
    Standalone Extraction Agent for literature-review pipelines.

    Purpose:
    - takes screened papers as JSON
    - extracts structured scientific information from title and abstract
    - returns strict JSON for later Summary, Comparison and Critic agents

    Important:
    This version does not use hardcoded keyword rules.
    It uses an LLM prompt and a Pydantic schema.
    """

    def __init__(
        self,
        model_name: str = "qwen3:latest",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "local-ollama-key",
        max_concurrent_tasks: int = 2,
    ):
        self.model_name = model_name
        self.max_concurrent_tasks = max_concurrent_tasks
        self.client = instructor.patch(
            AsyncOpenAI(base_url=base_url, api_key=api_key),
            mode=instructor.Mode.JSON,
        )

    @staticmethod
    def load_papers(input_path: str | Path) -> List[ResearchPaper]:
        input_path = Path(input_path)

        with input_path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)

        parsed = ScreeningAgentOutput.model_validate(raw_data)
        return parsed.papers

    async def extract_single_paper(
        self,
        paper: ResearchPaper,
        research_question: str,
    ) -> ExtractedPaper:

        system_prompt = """
        You are an academic information extraction assistant for a literature-review pipeline.

        Your task is to extract structured scientific information from one paper.
        Use only the provided title, abstract, metadata and URL.
        Do not invent missing information.

        Important:
        - Do not use fixed keyword rules.
        - Interpret the content semantically.
        - If information is missing, write "not specified".
        - Keep the output concise and evidence-based.
        - Return only valid JSON matching the schema.
        """
        text_for_analysis = (
            paper.full_text[:6000]
            if paper.full_text
            else paper.abstract
        )
        user_prompt = f"""
        Research question:
        {research_question}

        Paper metadata:
        Title: {paper.title}
        Year: {paper.year}
        Authors: {', '.join(paper.authors) if paper.authors else 'Unknown'}
        DOI: {paper.doi or 'No DOI'}
        URL: {paper.url or 'No URL'}
       Text:
       {text_for_analysis}

        Extract:
        - research method or study type
        - dataset or data source
        - main task or analytical focus
        - main findings
        - limitations
        - relevance to the research question
        - confidence level: high, medium, or low
        """

        result = await self.client.chat.completions.create(
            model=self.model_name,
            response_model=ExtractedPaperInfo,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        return ExtractedPaper(paper=paper, extraction=result)

    async def extract_papers(
        self,
        papers: List[ResearchPaper],
        research_question: str,
    ) -> ExtractionOutput:

        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        async def run_with_limit(paper: ResearchPaper) -> ExtractedPaper:
            async with semaphore:
                return await self.extract_single_paper(
                    paper=paper,
                    research_question=research_question,
                )

        extracted = await asyncio.gather(*(run_with_limit(paper) for paper in papers))

        output = ExtractionOutput()
        output.extracted_papers.extend(extracted)
        return output

    async def extract_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        research_question: str,
    ) -> ExtractionOutput:

        papers = self.load_papers(input_path)

        output = await self.extract_papers(
            papers=papers,
            research_question=research_question,
        )

        output_path = Path(output_path)
        with output_path.open("w", encoding="utf-8") as file:
            file.write(output.model_dump_json(indent=2))

        return output