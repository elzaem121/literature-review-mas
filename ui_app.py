import os
import streamlit as st
import requests
import pandas as pd
import time

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & CONSTANTS
# ---------------------------------------------------------
st.set_page_config(page_title="Literature Review MAS", layout="wide", page_icon="📚")
APP_TITLE = "Literature Review MAS · Async Orchestrator"
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

DEFAULT_INCLUSION_OPTIONS = [
    "Focus on multi-agent systems, agentic workflows, or collaborative AI environments",
    "Investigates safety evaluation, benchmarking frameworks, or vulnerability assessments",
    "Addresses alignment, adversarial robustness, hallucination containment, or secure tool use",
]

# ---------------------------------------------------------
# 2. SIDEBAR (The Beautiful Form from your old code)
# ---------------------------------------------------------
st.sidebar.header("Review-Protokoll")

with st.sidebar.form("protocol_form", clear_on_submit=False):

    research_question = st.text_area(
        "Forschungsfrage (Research Question)",
        placeholder="e.g., How to evaluate multi-agent systems efficiently?",
        height=100,
    )


    exclusion_criteria = st.text_area(
        "Ausschlusskriterien (Exclusion Criteria)",
        placeholder="One per line... e.g., Animal models\nReview papers",
        height=120,
    )


    additional_info = st.text_area(
        "Zusatzinfos / Instructions",
        placeholder="e.g., Be conservative when excluding papers.",
        height=90,
    )

    min_year = st.number_input(
        "Minimales Jahr (Min Year)",
        min_value=1900, max_value=2100, value=2023, step=1
    )

    target_count = st.number_input(
        "Target Papers Count",
        min_value=1, max_value=100, value=10, step=1
    )

    # Using Streamlit's multiselect for a clean tag UI
    inclusion_criteria = st.multiselect(
        "Einschlusskriterien (Inclusion Criteria)",
        options=DEFAULT_INCLUSION_OPTIONS,
        default=DEFAULT_INCLUSION_OPTIONS[:1],
        accept_new_options=True,
    )

    submitted = st.form_submit_button("Suche starten (Start Pipeline)", use_container_width=True, type="primary")


# ---------------------------------------------------------
# 3. HELPER FUNCTIONS (Formatting & UI)
# ---------------------------------------------------------
def flatten_papers(raw_papers_list):
    """Flattens nested dicts into flat rows for beautiful dataframes"""
    flat_list = []
    for item in raw_papers_list:
        paper_info = item.get("paper", {})
        screening_info = item.get("screening", {})

        flat_list.append({
            "title": paper_info.get("title", "No Title"),
            "year": paper_info.get("year", ""),
            "authors": ", ".join(paper_info.get("authors", [])),
            "decision": screening_info.get("decision", ""),
            "confidence_score": screening_info.get("confidence_score", ""),
            "relevance_score": screening_info.get("relevance_score", ""),
            "reasoning": screening_info.get("reasoning", ""),
            "doi": paper_info.get("doi", ""),
            "url": paper_info.get("url", "")
        })
    return flat_list


def render_beautiful_dataframe(data_list):
    """Renders a dataframe using your old advanced column configs"""
    if not data_list:
        st.info("No papers in this category.")
        return

    df = pd.DataFrame(flatten_papers(data_list))
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "decision": st.column_config.TextColumn("Decision"),
            "url": st.column_config.LinkColumn("URL"),
            "doi": st.column_config.TextColumn("DOI"),
            "reasoning": st.column_config.TextColumn("Reasoning", width="large"),
            "title": st.column_config.TextColumn("Title", width="large"),
            "authors": st.column_config.TextColumn("Authors"),
            "confidence_score": st.column_config.NumberColumn("Conf.", format="%d"),
            "relevance_score": st.column_config.NumberColumn("Rel.", format="%d"),
        }
    )


# ---------------------------------------------------------
# 4. MAIN EXECUTION LOGIC (The New Polling Engine)
# ---------------------------------------------------------
st.title(APP_TITLE)

if submitted:
    if not research_question.strip():
        st.sidebar.error("Forschungsfrage fehlt.")
        st.stop()

    payload = {
        "research_question": research_question.strip(),
        "min_year": min_year,
        "inclusion_criteria": inclusion_criteria,
        "exclusion_criteria": [line.strip() for line in exclusion_criteria.split('\n') if line.strip()],
        "additional_info": additional_info.strip(),
        "target_output_count": target_count
    }

    try:
        start_response = requests.post(f"{BACKEND_URL}/start_pipeline", json=payload)

        if start_response.status_code == 200:
            job_id = start_response.json().get("job_id")

            with st.status("🚀 Pipeline is running...", expanded=True) as status_box:
                live_text = st.empty()

                while True:
                    res = requests.get(f"{BACKEND_URL}/status/{job_id}")
                    if res.status_code == 200:
                        data = res.json()
                        current_step = data.get("current_step")
                        msg = data.get("status_message")

                        live_text.info(f"**Live Status:** {msg}")

                        if current_step == "completed":
                            status_box.update(label="✅ Pipeline Completed Successfully!", state="complete")
                            st.session_state.results = data
                            break
                        elif current_step == "error":
                            status_box.update(label="❌ Pipeline Failed!", state="error")
                            st.error(msg)
                            break
                        elif current_step == "document_processing":
                            status_box.update(label="📄 PDFs werden heruntergeladen und verarbeitet...", state="running")
                        elif current_step == "extraction":
                            status_box.update(label="📝 RAG-Extraktion läuft...", state="running")
                    time.sleep(1)
        else:
            st.error("Failed to start pipeline.")

    except requests.exceptions.ConnectionError:
        st.error("❌ Connection Error: Ensure your FastAPI backend is running.")

# ---------------------------------------------------------
# 5. DISPLAY RESULTS
# ---------------------------------------------------------
if "results" in st.session_state and st.session_state.results:
    res = st.session_state.results
    screening = res.get("screening_results", {})

    st.divider()
    st.subheader("📊 Screening Summary")

    # Your beautiful metrics columns
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Found", res.get("raw_papers_count", 0))
    col2.metric("✅ Included", len(screening.get("included_papers", [])))
    col3.metric("❌ Excluded", len(screening.get("excluded_papers", [])))
    col4.metric("❓ Uncertain", len(screening.get("uncertain_papers", [])))

    st.write("### Paper Details")
    tabs = st.tabs(["✅ Included", "❌ Excluded", "❓ Uncertain", "⚠️ Failed"])

    with tabs[0]:
        render_beautiful_dataframe(screening.get("included_papers", []))
    with tabs[1]:
        render_beautiful_dataframe(screening.get("excluded_papers", []))
    with tabs[2]:
        render_beautiful_dataframe(screening.get("uncertain_papers", []))
    with tabs[3]:
        failed = screening.get("failed_papers", [])
        if failed:
            st.json(failed)
        else:
            st.info("No failed papers.")

    # ---------------------------------------------------------
    # NEW: DISPLAY EXTRACTION RESULTS
    # ---------------------------------------------------------
    if res.get("current_step") == "completed" and res.get("extracted_papers"):
        st.divider()
        st.subheader("📝 Extrahierte Daten (RAG Extraction)")

        extracted_data = res["extracted_papers"]


        table_data = []
        for item in extracted_data:
            paper_info = item.get("paper", {})
            rag_info = item.get("rag_extraction", {})

            table_data.append({
                "Titel": paper_info.get("title", "N/A"),
                "Paper Type": rag_info.get("paper_type", "N/A"),
                "Method": rag_info.get("method", "N/A"),
                "Dataset": rag_info.get("dataset", "N/A"),
                "Task": rag_info.get("task", "N/A"),
                "Main Findings": rag_info.get("main_findings", "N/A"),
                "Limitations": rag_info.get("limitations", "N/A"),
                "Confidence": rag_info.get("confidence", "N/A")
            })

        df_extracted = pd.DataFrame(table_data)


        st.dataframe(
            df_extracted,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Titel": st.column_config.TextColumn("Titel", width="medium"),
                "Paper Type": st.column_config.TextColumn("Type"),
                "Method": st.column_config.TextColumn("Method"),
                "Dataset": st.column_config.TextColumn("Dataset"),
                "Task": st.column_config.TextColumn("Task", width="medium"),
                "Main Findings": st.column_config.TextColumn("Findings", width="large"),
                "Limitations": st.column_config.TextColumn("Limitations", width="medium"),
                "Confidence": st.column_config.TextColumn("Conf."),
            }
        )


        csv = df_extracted.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Daten als CSV herunterladen",
            data=csv,
            file_name='extrahierte_daten.csv',
            mime='text/csv',
            type="primary"
        )
