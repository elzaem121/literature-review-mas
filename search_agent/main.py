import json
from agent import UniversalAcademicSearchAgent


def main():
    # Insert your OpenAlex Polite Pool email here
    OPENALEX_EMAIL = "elzaem408@gmail.com"
    OPENALEX_API_KEY = None  # Optional

    # Initialize the search_agent with local Ollama defaults
    search_agent = UniversalAcademicSearchAgent(
        openalex_email=OPENALEX_EMAIL,
        openalex_api_key=OPENALEX_API_KEY,
        model_name="qwen2.5-coder:7b",
    )

    # Restored the original research query about evaluating Multi-Agent Systems
    # sample_query = "How does social media shape adolescents' lifeworlds and everyday experiences?"
    sample_query = "How to evaluate Multiagentsystems in an efficient way?"

    print(" Initiating local retrieval sequence...\n" + "=" * 50)

    # Run the retrieval pipeline
    results = search_agent.run_precise_retrieval_cycle(
        user_query=sample_query, target_output_count=25, min_citations=0, start_year=2018
    )

    print("\n" + "=" * 50)
    print(f" Success! Handing off {len(results)} high-precision papers to Screening Agent.")

    # Optional: Save results to pass to the next agent
    with open("../Screening_Agent/search_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
