## 🚀 Installation & Start

Folge diesen 3 einfachen Schritten, um den Agenten lokal zu starten:

### 1. Abhängigkeiten installieren
Öffne das Terminal im Projektverzeichnis und installiere die benötigten Pakete:
```bash
pip install -r requirements.txt
```

### 2. Lokales LLM starten
Lade und starte das KI-Modell über Ollama (dies muss im Hintergrund laufen):
```bash
ollama run qwen2.5-coder:7b
```

### 3. Streamlit-UI starten
Öffne ein **neues** Terminal-Fenster und starte die Web-Oberfläche:
```bash
streamlit run app.py
```
*(Die App öffnet sich danach automatisch in deinem Browser).*