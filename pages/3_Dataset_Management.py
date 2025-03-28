import streamlit as st
import os
from datetime import datetime
from utils.db import AppDatabase
from utils.dataset_utils import create_dataset_df, generate_jsonl_content, save_dataset

st.set_page_config(page_title="Dataset Management", layout="wide")
st.title("Dataset Management")

# Check authentication and project selection
if "user_id" not in st.session_state or "project_id" not in st.session_state:
    st.error("Please sign in and select a project from the Home page first.")
    st.stop()

project_id = st.session_state.project_id
project_name = st.session_state.project_name
st.write(f"Working on Project: {project_name} (ID: {project_id})")

# Fetch QA pairs
qa_pairs = AppDatabase.get_project_qa_pairs(project_id)

if not qa_pairs:
    st.warning("No QA pairs available to create a dataset.")
else:
    st.header("Create a New Dataset")
    
    # Create DataFrame for selection
    df = create_dataset_df(qa_pairs)
    
    # Display QA pairs with selection
    st.subheader("Select QA Pairs for Dataset")
    edited_df = st.data_editor(
        df,
        column_config={
            "Include": st.column_config.CheckboxColumn("Select", default=False),
            "id": st.column_config.NumberColumn("ID", width="small"),
            "question": st.column_config.TextColumn("Question", width="medium"),
            "answer": st.column_config.TextColumn("Answer", width="large")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Get selected QA pairs
    selected_ids = edited_df[edited_df['Include']]['id'].tolist()
    selected_count = len(selected_ids)
    
    # Dataset name input
    dataset_name = st.text_input("Dataset Name", placeholder="Enter a unique name for the dataset")
    
    if st.button("Create Dataset"):
        if not dataset_name:
            st.error("Please provide a dataset name.")
        elif selected_count == 0:
            st.error("Please select at least one QA pair.")
        else:
            # Check for duplicate dataset name
            existing_datasets = AppDatabase.get_project_datasets(project_id)
            if any(ds['dataset_name'] == dataset_name for ds in existing_datasets):
                st.error("A dataset with this name already exists. Please choose a different name.")
            else:
                with st.spinner("Creating dataset..."):
                    # Generate unique file name and path
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = f"dataset_{project_id}_{timestamp}.jsonl"
                    file_path = os.path.join("datasets", f"project_{project_id}", file_name)
                    
                    # Generate JSONL content
                    jsonl_content = generate_jsonl_content(qa_pairs, selected_ids)
                    
                    # Save dataset
                    success, message = save_dataset(
                        project_id=project_id,
                        dataset_name=dataset_name,
                        file_path=file_path,
                        jsonl_content=jsonl_content,
                        qa_pairs_ids=selected_ids
                    )
                    
                    if success:
                        st.success(f"Dataset '{dataset_name}' created successfully with {selected_count} QA pairs!")
                        st.write(f"File saved at: {file_path}")
                    else:
                        st.error(message)