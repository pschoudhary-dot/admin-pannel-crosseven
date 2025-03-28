import streamlit as st
from utils.db import AppDatabase
from utils.qa_utils import GEMINI_MODELS, OPENAI_MODELS
from utils.qa_generate_utils import handle_manual_qa, handle_transcript_qa, handle_document_qa
from utils.qa_import_export_utils import handle_qa_import, handle_qa_export
from utils.qa_display_utils import display_qa_pairs
from dotenv import load_dotenv

load_dotenv()

st.title("QA Management")

# Check database connection
db_status, db_info = AppDatabase.check_database_connection()
if not db_status:
    st.error(f"Database connection issue: {db_info}")
    st.stop()

# Check if user is signed in and project is selected
if "user_id" not in st.session_state or "project_id" not in st.session_state:
    st.error("Please sign in and select a project from the Home page first.")
    st.stop()

username = st.session_state.username
project_id = st.session_state.project_id
project_name = st.session_state.project_name
st.write(f"Working on Project: {project_name} (ID: {project_id})")

# Sidebar navigation
st.sidebar.write(f"Current Project: {project_name} (ID: {project_id})")

# AI Model Selection
st.sidebar.subheader("AI Model Settings")
ai_provider = st.sidebar.radio("Select AI Provider", ["Gemini", "OpenAI"])
if ai_provider == "Gemini":
    selected_model = st.sidebar.selectbox("Select Gemini Model", GEMINI_MODELS)
else:
    selected_model = st.sidebar.selectbox("Select OpenAI Model", OPENAI_MODELS)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Generate QA", "Import QA Pairs", "View QA Pairs", "Export QA"])

# Tab 1: Generate QA
with tab1:
    st.header("Generate QA Pairs")
    gen_options = st.radio("Generate QA from:", ["Manual Entry", "Call Transcripts", "Document Upload"])
    if gen_options == "Manual Entry":
        st.subheader("Manual QA Entry")
        handle_manual_qa(project_id)
    elif gen_options == "Call Transcripts":
        st.subheader("Generate from Call Transcripts")
        handle_transcript_qa(project_id, ai_provider, selected_model)
    elif gen_options == "Document Upload":
        st.subheader("Generate from Document")
        handle_document_qa(project_id, ai_provider, selected_model)

# Tab 2: Import QA Pairs
with tab2:
    st.header("Import QA Pairs")
    handle_qa_import(project_id)

# Tab 3: View QA Pairs
with tab3:
    st.header("View QA Pairs")
    display_qa_pairs(project_id)

# Tab 4: Export QA
with tab4:
    st.header("Export QA Pairs")
    handle_qa_export(project_id)