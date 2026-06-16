# App Main Start

## Step 1: Ins richtige Projektverzeichnis zum Starten der App gehen
```bash
cd ~/PycharmProjects/literature-review-mas
source .venv/bin/activate

PYTHONPATH="$PWD/Screening_Agent:$PWD/App_Main" \
python -m streamlit run ./App_Main/streamlit-app.py
```