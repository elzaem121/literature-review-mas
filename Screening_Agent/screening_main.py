import asyncio
import logging
from pathlib import Path

from screening_agent import AcademicScreeningAgent

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    """
    Development entry point for the Screening Agent only.

    This file is intentionally separate from the future shared main.py.
    It allows the Screening Agent to be tested independently while the
    Search Agent and other agents are still being developed by the team.
    """
    protocol = AcademicScreeningAgent.load_review_protocol("review_config_Evaluation.json")

    input_path = Path("testdaten/search_results.json")
    output_path = Path("screening_results.json")

    agent = AcademicScreeningAgent(
        model_name="qwen2.5-coder:7b",
        max_concurrent_tasks=3,
    )

    try:
        result = await agent.screen_file_with_protocol(
            input_path=input_path,
            output_path=output_path,
            protocol=protocol,
        )

        print("\n=== SCREENING SUMMARY ===")
        print(f"Included:  {len(result.included_papers)}")
        print(f"Excluded:  {len(result.excluded_papers)}")
        print(f"Uncertain: {len(result.uncertain_papers)}")
        print(f"Failed:    {len(result.failed_papers)}")
        print(f"\n[SUCCESS] Screening results saved to: {output_path}")

    except Exception as error:
        logger.exception("[ERROR] Screening pipeline failed: %s", error)


if __name__ == "__main__":
    asyncio.run(main())
