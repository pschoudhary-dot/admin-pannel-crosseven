import streamlit as st
import pandas as pd
from utils.db import AppDatabase

# Replace the entire display_qa_pairs function with this:
def display_qa_pairs(project_id):
    """Display and manage stored QA pairs from main or temporary storage."""
    view_option = st.radio("View QA Pairs from:", ["Main QA Storage", "Temporary QA Storage"], key="view_option")

    if view_option == "Main QA Storage":
        qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
        source_table = "qa_pairs"
    else:
        qa_pairs = AppDatabase.get_project_qa_temp(project_id)
        source_table = "qa_temp"

    if not qa_pairs:
        st.write(f"No QA pairs stored in {view_option.lower()} yet.")
        return

    st.write(f"Total QA pairs in {view_option.lower()}: {len(qa_pairs)}")
    # Convert sqlite3.Row to dict for consistent access
    qa_pairs = [dict(qa) for qa in qa_pairs]
    
    # Extract call_ids/source_ids depending on the source table
    if source_table == "qa_pairs":
        call_ids = list(set([qa["call_id"] for qa in qa_pairs if qa["call_id"] is not None]))
    else:  # qa_temp
        call_ids = list(set([qa["source_id"] for qa in qa_pairs if qa["source_id"] is not None and qa["source_type"] == "transcript"]))

    search_query = st.text_input("Search for questions containing:", key="qa_search")
    selected_call_id = "All"
    if call_ids:
        filter_call = st.checkbox("Filter by Call ID")
        if filter_call:
            selected_call_id = st.selectbox("Select Call ID", ["All"] + call_ids, key="filter_call_id")
    
    filtered_qa_pairs = [
        qa for qa in qa_pairs 
        if (not search_query or search_query.lower() in qa["question"].lower()) and
           (selected_call_id == "All" or 
            (source_table == "qa_pairs" and qa["call_id"] == selected_call_id) or 
            (source_table == "qa_temp" and qa["source_id"] == selected_call_id and qa["source_type"] == "transcript"))
    ]
    st.write(f"Showing {len(filtered_qa_pairs)} of {len(qa_pairs)} QA pairs")
    items_per_page = st.slider("Items per page", 5, 50, 10)
    total_pages = max(1, (len(filtered_qa_pairs) + items_per_page - 1) // items_per_page)
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        page_number = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    start_idx = (page_number - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(filtered_qa_pairs))
    page_items = filtered_qa_pairs[start_idx:end_idx]

    for qa in page_items:
        with st.expander(f"#{qa['id']} - {qa['question'][:50]}..."):
            st.write(f"**Question:** {qa['question']}")
            st.write(f"**Answer:** {qa['answer']}")
            if source_table == "qa_pairs":
                st.write(f"**Call ID:** {qa['call_id'] or 'None'}")
            else:
                st.write(f"**Source Type:** {qa['source_type']}")
                st.write(f"**Source ID:** {qa['source_id'] or 'None'}")
            st.write(f"**Created on:** {qa['created_at']}")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Edit", key=f"edit_{qa['id']}"):
                    st.session_state.editing_qa_id = qa['id']
                    st.session_state.editing_question = qa['question']
                    st.session_state.editing_answer = qa['answer']
                    st.session_state.editing_call_id = qa['call_id'] if source_table == "qa_pairs" else qa['source_id']
                    st.session_state.editing_source = source_table
                    st.rerun()
            with col2:
                if st.button("Delete", key=f"delete_{qa['id']}"):
                    if source_table == "qa_pairs" and AppDatabase.remove_qa_pair(project_id, qa["id"]):
                        st.success("QA pair deleted successfully from main storage!")
                        st.rerun()
                    elif source_table == "qa_temp" and AppDatabase.remove_qa_temp(project_id, qa["id"]):
                        st.success("QA pair deleted successfully from temporary storage!")
                        st.rerun()
                    else:
                        st.error("Failed to delete QA pair.")
            with col3:
                move_label = "Move to Temp" if source_table == "qa_pairs" else "Move to Main"
                if st.button(move_label, key=f"move_{qa['id']}"):
                    if source_table == "qa_pairs":
                        if AppDatabase.store_qa_temp(project_id, qa["question"], qa["answer"], "moved", qa["call_id"]) and AppDatabase.remove_qa_pair(project_id, qa["id"]):
                            st.success("QA pair moved to temporary storage!")
                            st.rerun()
                        else:
                            st.error("Failed to move QA pair to temporary storage.")
                    else:
                        if AppDatabase.store_qa_pair(project_id, qa["question"], qa["answer"], qa["source_id"] if qa["source_type"] == "transcript" else None) and AppDatabase.remove_qa_temp(project_id, qa["id"]):
                            st.success("QA pair moved to main storage!")
                            st.rerun()
                        else:
                            st.error("Failed to move QA pair to main storage.")

    if hasattr(st.session_state, 'editing_qa_id'):
        st.subheader(f"Edit QA Pair #{st.session_state.editing_qa_id}")
        edited_question = st.text_area("Question", st.session_state.editing_question, key="edit_question")
        edited_answer = st.text_area("Answer", st.session_state.editing_answer, key="edit_answer")
        edited_call_id = st.text_input("Call ID (optional)", st.session_state.editing_call_id or "", key="edit_call_id")
        if edited_call_id.strip() == "":
            edited_call_id = None
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save Changes"):
                source_table = st.session_state.editing_source
                if source_table == "qa_pairs":
                    AppDatabase.remove_qa_pair(project_id, st.session_state.editing_qa_id)
                    if AppDatabase.store_qa_pair(project_id, edited_question, edited_answer, edited_call_id):
                        st.success("QA pair updated successfully in main storage!")
                        del st.session_state.editing_qa_id
                        del st.session_state.editing_question
                        del st.session_state.editing_answer
                        del st.session_state.editing_call_id
                        del st.session_state.editing_source
                        st.rerun()
                    else:
                        st.error("Failed to update QA pair in main storage.")
                else:
                    AppDatabase.remove_qa_temp(project_id, st.session_state.editing_qa_id)
                    if AppDatabase.store_qa_temp(project_id, edited_question, edited_answer, "manual" if not edited_call_id else "transcript", edited_call_id):
                        st.success("QA pair updated successfully in temporary storage!")
                        del st.session_state.editing_qa_id
                        del st.session_state.editing_question
                        del st.session_state.editing_answer
                        del st.session_state.editing_call_id
                        del st.session_state.editing_source
                        st.rerun()
                    else:
                        st.error("Failed to update QA pair in temporary storage.")
        with col2:
            if st.button("Cancel"):
                del st.session_state.editing_qa_id
                del st.session_state.editing_question
                del st.session_state.editing_answer
                del st.session_state.editing_call_id
                del st.session_state.editing_source
                st.rerun()