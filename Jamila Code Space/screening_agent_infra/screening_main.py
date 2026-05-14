import asyncio
from pathlib import Path

from screening_agent import AcademicScreeningAgent


async def main():
    """
    Development entry point for the Screening Agent only.

    This file is intentionally separate from the future shared main.py.
    It allows the Screening Agent to be tested independently while the
    Search Agent and other agents are still being developed by the team.
    """
    research_question = "How does social media shape adolescents' lifeworlds and everyday experiences?"
    #test
    print(research_question)

    inclusion_criteria = """
    Include papers that focus on adolescents, teenagers, youth, or young people
    and investigate social media use in relation to everyday life, lifeworlds,
    identity, wellbeing, peer relations, social interaction, behavior, or
    psychological/social impact.
    """

    exclusion_criteria = """
    Exclude papers that focus only on adults, purely technical recommender systems,
    marketing performance, severe psychiatric clinical treatment, unrelated digital
    technologies without social media, or papers without enough title/abstract
    information to judge the topic clearly.
    """

    input_path = Path("search_results.json")
    output_path = Path("screening_results.json")

    agent = AcademicScreeningAgent(
        model_name="qwen3:latest",
        max_concurrent_tasks=3,
    )
    print("first step")

    try:
        result = await agent.screen_file(
            input_path=input_path,
            output_path=output_path,
            research_question=research_question,
            inclusion_criteria=inclusion_criteria,
            exclusion_criteria=exclusion_criteria,
        )
        print("second step")

        print("\n=== SCREENING SUMMARY ===")
        print(f"Included:  {len(result.included_papers)}")
        print(f"Excluded:  {len(result.excluded_papers)}")
        print(f"Uncertain: {len(result.uncertain_papers)}")
        print(f"\n[SUCCESS] Screening results saved to: {output_path}")

    except Exception as error:
        print(f"[ERROR] Screening pipeline failed: {error}")


if __name__ == "__main__":
    asyncio.run(main())
