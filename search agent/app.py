import streamlit as st
import asyncio
import json
import pandas as pd
import time
from agent import AcademicSearchAgent

# Page configuration for a wider, modern layout
st.set_page_config(page_title="AI Academic Search Agent", page_icon="🧬", layout="wide")

# Main Title and Subtitle
st.title("🧬 AI-Powered Academic Research Agent")
st.markdown(
    "Automate your literature review. This agent expands your query, fetches papers, and structures the data instantly.")

# --- AGENT DETAILS SECTION ---
with st.expander("🤖 How does this Agent work? (System Architecture)", expanded=False):
    st.markdown("""
    **The Two-Stage Retrieval Pipeline:**
    1. **Intelligent Query Expansion:** The local LLM (`qwen2.5-coder:7b`) analyzes your question and generates 3-5 academic synonyms to maximize search recall.
    2. **Parallel API Retrieval:** The agent fetches data concurrently from the *OpenAlex API* to ensure high speed.
    3. **Deduplication:** A deterministic filter removes duplicate papers using exact DOI matching.
    4. **Strict JSON Formatting:** The output is forced into a strict JSON structure using *Pydantic* for seamless downstream processing.
    """)

# Sidebar Configuration
st.sidebar.header("⚙️ Search Configuration")
research_query = st.sidebar.text_area("Research Question:",
                                      placeholder="e.g., How does social media shape adolescents' lifeworlds?")

min_year = st.sidebar.number_input("Minimum Publication Year:", min_value=2000, max_value=2025, value=2020)

st.sidebar.divider()

# Main Action Button
if st.sidebar.button("🚀 Execute Research Pipeline", use_container_width=True):
    if not research_query:
        st.error("⚠️ Please enter a research question to proceed.")
    else:
        agent = AcademicSearchAgent(model_name="qwen2.5-coder:7b")

        # Track execution time
        start_time = time.time()

        with st.status("🔄 Orchestrating Agent Tasks...", expanded=True) as status:
            try:
                st.write("🧠 1. Analyzing query and generating academic keywords...")
                st.write("🌐 2. Fetching research papers concurrently from OpenAlex...")
                st.write("🧹 3. Deduplicating and structuring data...")

                # Run the async pipeline (removed criteria)
                json_result = asyncio.run(agent.run_pipeline(
                    user_query=research_query,
                    min_year=min_year
                ))

                status.update(label="✅ Pipeline Execution Completed Successfully!", state="complete", expanded=False)

                # Calculate total execution time
                end_time = time.time()
                execution_time = round(end_time - start_time, 2)

                # Parse results
                data = json.loads(json_result)
                papers = data.get("papers", [])

                if not papers:
                    # Updated warning message
                    st.warning("No papers found matching your research question.")
                else:
                    # --- METRICS DASHBOARD ---
                    st.write("### 📈 Search Analytics")
                    col1, col2, col3 = st.columns(3)
                    col1.metric(label="Total Unique Papers", value=len(papers))
                    col2.metric(label="Execution Time", value=f"{execution_time} seconds")
                    col3.metric(label="Data Source", value="OpenAlex API")

                    st.divider()

                    # --- TABS FOR RESULTS PRESENTATION ---
                    tab1, tab2 = st.tabs(["📊 Overview Table", "📄 Detailed Abstract View"])

                    with tab1:
                        st.subheader("Data Overview")
                        # Create a clean dataframe for the table
                        df = pd.DataFrame(papers)[['title', 'year', 'doi', 'relevance_score']]
                        st.dataframe(df, use_container_width=True, hide_index=True)

                    with tab2:
                        st.subheader("Paper Details")
                        for i, paper in enumerate(papers):
                            with st.expander(f"📌 {paper['title']} ({paper['year']})"):
                                st.markdown(f"**👥 Authors:** {', '.join(paper['authors'])}")
                                st.markdown(f"**⭐ Relevance Score:** {paper['relevance_score']} (Unscreened)")
                                st.markdown(f"**📖 Abstract:** {paper['abstract']}")
                                if paper['url']:
                                    st.link_button("🔗 Read Full Paper", paper['url'])

                    # --- DOWNLOAD OPTION ---
                    st.sidebar.write("### 📥 Export Data")
                    st.sidebar.download_button(
                        label="Download Full JSON",
                        data=json_result,
                        file_name="research_results.json",
                        mime="application/json",
                        use_container_width=True
                    )

            except Exception as e:
                st.error(f"❌ Critical Error: {e}")
                status.update(label="❌ Pipeline Failed", state="error")
else:
    # A welcoming message when the app first loads
    st.info(
        "👋 Welcome! Please fill in your search parameters on the left sidebar and click 'Execute Research Pipeline'.")