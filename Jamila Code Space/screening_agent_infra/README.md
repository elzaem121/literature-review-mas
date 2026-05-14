# Standalone Screening Agent

Diese Mini-Infrastruktur ist bewusst **nur für den Screening Agent** gebaut.
Sie ist unabhängig von einer späteren gemeinsamen `main.py`.

## Requirements
Ollama installieren: curl -fsSL https://ollama.com/install.sh | sh
Bei lokalen Tests eine lokale LLM installieren: ollama run qwen3

## Dateien

```text
screening_agent_infra/
├── screening_agent.py          # eigentlicher Screening Agent
├── screening_schemas.py        # Pydantic-Modelle für Input und Output
├── screening_main.py           # lokale Test-Main nur für Screening
├── sample_search_results.json  # Beispielinput im Format des Search Agents
├── requirements.txt
└── README.md
```

## Zweck

Der Screening Agent nimmt Search-Agent-Output im Format

```json
{
  "papers": [
    {
      "title": "...",
      "abstract": "...",
      "year": 2023,
      "authors": ["..."],
      "doi": "...",
      "url": "...",
      "relevance_score": 8
    }
  ]
}
```

und sortiert die Paper nach Kriterien in:

- `included_papers`
- `excluded_papers`
- `uncertain_papers`

## Start

1. Ollama starten.
2. Modell laden, z. B.:

```bash
ollama pull llama3.1:8b
```

oder, (bevorzugt verwende):

```bash
ollama pull qwen3
```

3. Dependencies installieren:

```bash
pip install -r requirements.txt
```

4. Screening Agent testen:

```bash
python screening_main.py
```

Danach entsteht:

```text
screening_results.json
```

## Warum eine eigene `screening_main.py`?

Am Anfang ist das sinnvoll, weil jede Person ihren Agenten unabhängig testen kann.
Später wird die gemeinsame Pipeline ungefähr so aussehen:

```text
Search Agent -> Screening Agent -> Extraction Agent -> Comparison/Critic Agent
```

Dann kann der Inhalt von `screening_main.py` in eine gemeinsame `main.py` oder einen Orchestrator übernommen werden.
