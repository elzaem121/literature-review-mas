"""Step `label_prepare`: one input file per pool paper, plus the rendered prompt and schema."""

from pathlib import Path

from eval.gold_build.files import labeling_dir, load_topics, write_json
from eval.harness.gold import DEFAULT_GOLD_DIR, load_pool
from eval.harness.topics import TOPICS_DIR, labeling_json_schema, render_labeling_prompt

LABELING_PROMPT_FILE = "labeling_prompt.md"
INPUTS = "inputs"
PROMPT_FILE = "prompt.md"
SCHEMA_FILE = "schema.json"


def inputs_dir(data_root: Path, topic_id: str) -> Path:
    """The folder a topic's labeling calls run in: the papers' inputs, the prompt, the schema."""
    return labeling_dir(data_root) / INPUTS / topic_id


def paper_input_text(title: str, abstract: str) -> str:
    """What the labeler sees of one paper: its title and abstract, nothing else."""
    return f"Title: {title}\n\nAbstract: {abstract}\n"


def prepare_labeling(
    *, data_root: Path, gold_dir: Path = DEFAULT_GOLD_DIR, topics_dir: Path = TOPICS_DIR
) -> int:
    """Write the labeling inputs and the committed prompt file; return the number of papers."""
    sections = []
    count = 0
    for topic_id, topic in load_topics(topics_dir).items():
        folder = inputs_dir(data_root, topic_id)
        prompt = render_labeling_prompt(topic)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / PROMPT_FILE).write_text(prompt + "\n", encoding="utf-8")
        write_json(folder / SCHEMA_FILE, labeling_json_schema(topic))
        for paper in load_pool(gold_dir, topic_id):
            text = paper_input_text(paper.title, paper.abstract)
            (folder / f"{paper.paper_key}.txt").write_text(text, encoding="utf-8")
            count += 1
        sections.append(f"## {topic_id}\n\n{prompt}\n")
    (gold_dir / LABELING_PROMPT_FILE).write_text(
        "# Labeling prompts\n\nOne system prompt per topic, rendered from the topic configs.\n\n"
        + "\n".join(sections),
        encoding="utf-8",
    )
    return count
