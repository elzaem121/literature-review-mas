import pytest

from src.llm.prompts import extraction, screening, search


@pytest.mark.parametrize("module", [search, screening, extraction])
def test_every_role_prompt_is_versioned(module):
    assert module.PROMPT_VERSION == "v1"


def test_screening_system_prompt_appends_additional_instructions():
    base = screening.render_system_prompt(None)
    extended = screening.render_system_prompt("Be strict {x}")

    assert base == screening.SYSTEM_PROMPT
    assert extended == base + "\nAdditional review instructions:\nBe strict {x}\n"


def test_screening_user_prompt_uses_v1_fallbacks_for_missing_fields():
    prompt = screening.render_user_prompt("RQ", "- i", "- e", "Title", None, [], None, None, "")

    assert "Authors: Unknown" in prompt
    assert "DOI: No DOI" in prompt
    assert "URL: No URL" in prompt
    assert "Abstract: No abstract available." in prompt


def test_extraction_user_prompt_keeps_the_json_template_braces():
    prompt = extraction.render_user_prompt("RQ", "Title", {"method_chunks": ["m1", "m2"]})

    assert '"paper_type": "...",' in prompt
    assert "m1\n\n--- METHOD CHUNK ---\n\nm2" in prompt
