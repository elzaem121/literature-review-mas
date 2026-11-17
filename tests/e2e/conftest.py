import asyncio

import pytest

INITIAL_STATE = {
    "research_question": "How do teenagers use social media?",
    "min_year": 2020,
    "inclusion_criteria": ["Studies adolescents"],
    "exclusion_criteria": ["Marketing studies"],
    "additional_info": None,
    "target_output_count": 5,
    "current_step": "initialized",
    "status_message": "Starting search...",
}


@pytest.fixture
def final_state(fake_surface) -> dict:
    """Final graph state of one full run on the fake surface."""
    from Orchestration.graph import app

    return asyncio.run(app.ainvoke(dict(INITIAL_STATE)))
