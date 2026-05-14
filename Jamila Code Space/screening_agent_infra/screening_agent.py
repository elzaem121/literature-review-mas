import asyncio
import json
from pathlib import Path
from typing import List, Optional

import instructor
from openai import AsyncOpenAI

from screening_schemas import (
    PaperScreeningResult,
    ResearchPaper,
    ScreenedPaper,
    ScreeningDecision,
    ScreeningOutput,
    SearchAgentOutput,
)


class AcademicScreeningAgent:
    """
    Standalone Screening Agent for literature-review pipelines.

    Purpose:
    - takes JSON output from a Search Agent
    - screens papers against inclusion and exclusion criteria
    - returns strict JSON grouped into include / exclude / uncertain

    Important methodological choice:
    The agent only screens based on metadata available in the input JSON
    (title, abstract, year, authors, DOI, URL). It must not invent evidence.
    """
    print("entered2")
    def __init__(
        self,
        model_name: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "local-ollama-key",
        max_concurrent_tasks: int = 3,
    ):
        self.model_name = model_name
        self.max_concurrent_tasks = max_concurrent_tasks
        self.client = instructor.patch(
            AsyncOpenAI(base_url=base_url, api_key=api_key),
            mode=instructor.Mode.JSON,
        )

    @staticmethod
    def load_search_results(input_path: str | Path) -> List[ResearchPaper]:
        """
        Loads Search Agent JSON from disk.

        Expected format:
        {
          "papers": [
            {"title": "...", "abstract": "...", ...}
          ]
        }
        """
        input_path = Path(input_path)
        with input_path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)

        parsed = SearchAgentOutput.model_validate(raw_data)
        return parsed.papers

    async def screen_single_paper(
        self,
        paper: ResearchPaper,
        research_question: str,
        inclusion_criteria: str,
        exclusion_criteria: str,
    ) -> ScreenedPaper:

        system_prompt = """
        You are an academic literature-screening assistant for a systematic or scoping review.

        Your task is to classify exactly one paper using only the provided title, abstract,
        year, authors, DOI and URL. Do not invent missing information.

        Decision policy:
        - Use "include" only if the paper clearly matches the research question and inclusion criteria.
        - Use "exclude" if the paper clearly violates one or more exclusion criteria or is clearly off-topic.
        - Use "uncertain" if the metadata is insufficient, the abstract is missing, or the paper may be relevant but cannot be judged safely.
        - Be conservative: uncertain is better than wrongly excluding a potentially useful paper.
        - Keep the reasoning short and evidence-based.
        """

        user_prompt = f"""
        Research question:
        {research_question}

        Inclusion criteria:
        {inclusion_criteria}

        Exclusion criteria:
        {exclusion_criteria}

        Paper metadata:
        Title: {paper.title}
        Year: {paper.year}
        Authors: {', '.join(paper.authors) if paper.authors else 'Unknown'}
        DOI: {paper.doi or 'No DOI'}
        URL: {paper.url or 'No URL'}
        Abstract: {paper.abstract or 'No abstract available.'}
        """

        result = await self.client.chat.completions.create(
            model=self.model_name,
            response_model=PaperScreeningResult,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        # Preserve the original title even if the model formats it slightly differently.
        #result.title = paper.title
        print("result returned")
        return ScreenedPaper(paper=paper, screening=result)

    async def screen_papers(
        self,
        papers: List[ResearchPaper],
        research_question: str,
        inclusion_criteria: str,
        exclusion_criteria: str,
    ) -> ScreeningOutput:
        """
        Screens a list of papers with limited concurrency.
        """
        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        async def run_with_limit(paper: ResearchPaper) -> ScreenedPaper:
            async with semaphore:
                return await self.screen_single_paper(
                    paper=paper,
                    research_question=research_question,
                    inclusion_criteria=inclusion_criteria,
                    exclusion_criteria=exclusion_criteria,
                )

        screened = await asyncio.gather(*(run_with_limit(paper) for paper in papers))
        print("screened papers returned")

        output = ScreeningOutput()
        for item in screened:
            if item.screening.decision == ScreeningDecision.INCLUDE:
                output.included_papers.append(item)
            elif item.screening.decision == ScreeningDecision.EXCLUDE:
                output.excluded_papers.append(item)
            else:
                output.uncertain_papers.append(item)

        # Sort included and uncertain papers by relevance/confidence for easier review.
        output.included_papers.sort(
            key=lambda x: (x.screening.relevance_score, x.screening.confidence_score),
            reverse=True,
        )
        output.uncertain_papers.sort(
            key=lambda x: (x.screening.relevance_score, x.screening.confidence_score),
            reverse=True,
        )
        output.excluded_papers.sort(
            key=lambda x: (x.screening.relevance_score, x.screening.confidence_score),
            reverse=True,
        )

        return output

    async def screen_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        research_question: str,
        inclusion_criteria: str,
        exclusion_criteria: str,
    ) -> ScreeningOutput:
        """
        Convenience method for local development:
        reads Search Agent JSON, screens it, and writes Screening Agent JSON.
        """
        papers = self.load_search_results(input_path)
        output = await self.screen_papers(
            papers=papers,
            research_question=research_question,
            inclusion_criteria=inclusion_criteria,
            exclusion_criteria=exclusion_criteria,
        )
        print("output returned")

        output_path = Path(output_path)
        with output_path.open("w", encoding="utf-8") as file:
            file.write(output.model_dump_json(indent=2))

        return output
