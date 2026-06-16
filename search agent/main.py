import asyncio
from agent import AcademicSearchAgent


async def main():
    # Define the primary research question
    research_question = "How does social media shape adolescents' lifeworlds and everyday experiences?"

    # Set the minimum publication year (e.g., to get recent studies on social media)
    min_publish_year = 2020

    # Initialize the agent orchestrator
    agent = AcademicSearchAgent(model_name="qwen2.5-coder:7b")

    try:
        # Trigger the pipeline (removed the criteria argument)
        final_json_output = await agent.run_pipeline(
            user_query=research_question,
            min_year=min_publish_year
        )

        # Output is meticulously formatted and guaranteed to be valid JSON
        print("\n=== FINAL OUTPUT FOR DOWNSTREAM SCREENING AGENT ===")
        print(final_json_output)

        # Save the generated JSON to a local file for the Screening Agent to process later
        with open("search_results.json", "w", encoding="utf-8") as f:
            f.write(final_json_output)

        print("\n[SUCCESS] Results successfully saved to: search_results.json")

    except Exception as e:
        print(f"CRITICAL ERROR: Pipeline execution halted: {e}")


if __name__ == "__main__":
    # Execute the async main loop
    asyncio.run(main())