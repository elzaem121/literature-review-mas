import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional

from src.llm.client import get_llm
from src.llm.prompts.screening import render_system_prompt, render_user_prompt
from src.pipeline.screening.screening_schemas import (
    PaperScreeningResult,
    ResearchPaper,
    ReviewProtocol,
    ScreenedPaper,
    ScreeningDecision,
    ScreeningError,
    ScreeningOutput,
    SearchAgentOutput,
)

logger = logging.getLogger(__name__)


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

    def __init__(self, model_name: str, max_concurrent_tasks: int = 3):
        self.model_name = model_name
        self.max_concurrent_tasks = max_concurrent_tasks
        self.client = get_llm("screening")

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

    @staticmethod
    def load_review_protocol(path: str | Path) -> ReviewProtocol:
        path = Path(path)

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return ReviewProtocol.model_validate(data)

    @staticmethod
    def apply_publication_year_filter(
        papers: List[ResearchPaper],
        protocol: ReviewProtocol,
    ) -> tuple[List[ResearchPaper], List[ScreenedPaper]]:
        year_filter = protocol.publication_year
        if year_filter.min_year is None and year_filter.max_year is None:
            return papers, []

        eligible: List[ResearchPaper] = []
        excluded: List[ScreenedPaper] = []

        for paper in papers:
            if paper.year is None:
                eligible.append(paper)
                continue

            if year_filter.min_year is not None and paper.year < year_filter.min_year:
                excluded.append(
                    AcademicScreeningAgent._make_year_excluded_paper(
                        paper,
                        f"below minimum {year_filter.min_year}",
                    )
                )
                continue

            if year_filter.max_year is not None and paper.year > year_filter.max_year:
                excluded.append(
                    AcademicScreeningAgent._make_year_excluded_paper(
                        paper,
                        f"above maximum {year_filter.max_year}",
                    )
                )
                continue

            eligible.append(paper)

        return eligible, excluded

    @staticmethod
    def _make_year_excluded_paper(paper: ResearchPaper, reason: str) -> ScreenedPaper:
        return ScreenedPaper(
            paper=paper,
            screening=PaperScreeningResult(
                decision=ScreeningDecision.EXCLUDE,
                confidence_score=10,
                relevance_score=1,
                reasoning=(
                    f"Publication year {paper.year} is outside the allowed range ({reason})."
                ),
            ),
        )

    @staticmethod
    def build_screening_output(
        screened: List[ScreenedPaper],
        failed: Optional[List[ScreeningError]] = None,
        pre_excluded: Optional[List[ScreenedPaper]] = None,
    ) -> ScreeningOutput:
        output = ScreeningOutput()
        if failed:
            output.failed_papers.extend(failed)
        if pre_excluded:
            output.excluded_papers.extend(pre_excluded)

        for item in screened:
            if item.screening.decision == ScreeningDecision.INCLUDE:
                output.included_papers.append(item)
            elif item.screening.decision == ScreeningDecision.EXCLUDE:
                output.excluded_papers.append(item)
            else:
                output.uncertain_papers.append(item)

        def sort_key(item: ScreenedPaper) -> tuple[int, int]:
            return (item.screening.relevance_score, item.screening.confidence_score)

        output.included_papers.sort(key=sort_key, reverse=True)
        output.uncertain_papers.sort(key=sort_key, reverse=True)
        output.excluded_papers.sort(key=sort_key, reverse=True)

        return output

    async def screen_single_paper(
        self,
        paper: ResearchPaper,
        research_question: str,
        inclusion_criteria: str,
        exclusion_criteria: str,
        additional_instructions: Optional[str] = None,
    ) -> ScreenedPaper:
        result = await self.client.chat.completions.create(
            model=self.model_name,
            response_model=PaperScreeningResult,
            messages=[
                {"role": "system", "content": render_system_prompt(additional_instructions)},
                {
                    "role": "user",
                    "content": render_user_prompt(
                        research_question=research_question,
                        inclusion_criteria=inclusion_criteria,
                        exclusion_criteria=exclusion_criteria,
                        title=paper.title,
                        year=paper.year,
                        authors=paper.authors,
                        doi=paper.doi,
                        url=paper.url,
                        abstract=paper.abstract,
                    ),
                },
            ],
            temperature=0,
        )
        return ScreenedPaper(paper=paper, screening=result)

    async def screen_papers(
        self,
        papers: List[ResearchPaper],
        research_question: str,
        inclusion_criteria: str,
        exclusion_criteria: str,
        additional_instructions: Optional[str] = None,
        pre_excluded: Optional[List[ScreenedPaper]] = None,
    ) -> ScreeningOutput:
        """
        Screens a list of papers with limited concurrency.
        """
        if not papers:
            return self.build_screening_output([], pre_excluded=pre_excluded)

        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        async def run_with_limit(paper: ResearchPaper):
            async with semaphore:
                return await self.screen_single_paper(
                    paper=paper,
                    research_question=research_question,
                    inclusion_criteria=inclusion_criteria,
                    exclusion_criteria=exclusion_criteria,
                    additional_instructions=additional_instructions,
                )

        results = await asyncio.gather(
            *(run_with_limit(paper) for paper in papers),
            return_exceptions=True,
        )

        screened: List[ScreenedPaper] = []
        failed: List[ScreeningError] = []
        for paper, result in zip(papers, results):
            if isinstance(result, Exception):
                failed.append(ScreeningError(paper=paper, error=str(result)))
                logger.error("Failed to screen '%s': %s", paper.title, result)
            else:
                screened.append(result)

        return self.build_screening_output(
            screened,
            failed=failed,
            pre_excluded=pre_excluded,
        )

    async def screen_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        research_question: str,
        inclusion_criteria: str,
        exclusion_criteria: str,
        additional_instructions: Optional[str] = None,
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
            additional_instructions=additional_instructions,
        )

        output_path = Path(output_path)
        with output_path.open("w", encoding="utf-8") as file:
            file.write(output.model_dump_json(indent=2))

        return output

    async def screen_file_with_protocol(
        self,
        input_path: str | Path,
        output_path: str | Path,
        protocol: ReviewProtocol,
    ) -> ScreeningOutput:
        """
        Reads Search Agent JSON, applies review protocol settings, screens papers,
        and writes Screening Agent JSON.
        """
        papers = self.load_search_results(input_path)
        eligible_papers, pre_excluded = self.apply_publication_year_filter(papers, protocol)

        output = await self.screen_papers(
            papers=eligible_papers,
            research_question=protocol.research_question,
            inclusion_criteria=protocol.format_inclusion_criteria(),
            exclusion_criteria=protocol.format_exclusion_criteria(),
            additional_instructions=protocol.additional_instructions,
            pre_excluded=pre_excluded,
        )

        output_path = Path(output_path)
        with output_path.open("w", encoding="utf-8") as file:
            file.write(output.model_dump_json(indent=2))

        logger.info(
            "Screening complete: included=%s excluded=%s uncertain=%s failed=%s",
            len(output.included_papers),
            len(output.excluded_papers),
            len(output.uncertain_papers),
            len(output.failed_papers),
        )

        return output
