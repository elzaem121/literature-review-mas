from Orchestration.graph import app

V1_STATE_KEYS = {
    "research_question",
    "min_year",
    "inclusion_criteria",
    "exclusion_criteria",
    "additional_info",
    "target_output_count",
    "raw_papers",
    "screening_results",
    "extracted_papers",
    "current_step",
    "status_message",
}


def test_graph_compiles_with_the_v1_nodes():
    assert set(app.get_graph().nodes) >= {
        "pre_search",
        "search_agent",
        "pre_screening",
        "screening_agent",
        "pre_document_processing",
        "document_processing_node",
        "pre_extraction",
        "extraction_node",
    }


def test_full_fake_run_completes_with_the_v1_state_shape(final_state):
    assert set(final_state) == V1_STATE_KEYS
    assert final_state["current_step"] == "completed"
    assert len(final_state["raw_papers"]) == 5
    buckets = final_state["screening_results"]
    assert {name: len(papers) for name, papers in buckets.items()} == {
        "included_papers": 2,
        "excluded_papers": 1,
        "uncertain_papers": 1,
        "failed_papers": 1,
    }
    assert len(final_state["extracted_papers"]) == 2
    for paper in buckets["included_papers"]:
        assert paper["paper"]["pdf_status"] == "Downloaded"
        assert set(paper["retrieved_chunks_by_field"]) == {
            "method_chunks",
            "dataset_chunks",
            "task_chunks",
            "findings_chunks",
            "limitations_chunks",
        }
