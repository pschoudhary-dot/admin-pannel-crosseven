import streamlit as st
import pandas as pd
from utils.db import AppDatabase
# In qa_generate_utils.py - fix the imports
from utils.qa_utils import generate_qa_from_transcript, generate_qa_from_document_chunk, preprocess_text, extract_md_sections
from utils.file_utils import save_uploaded_file
from langchain.text_splitter import RecursiveCharacterTextSplitter
import time

def save_and_review_qa_pairs(project_id, qa_pairs, source_type, source_id):
    """Save QA pairs to temporary storage and provide review interface."""
    for qa in qa_pairs:
        if not AppDatabase.store_qa_temp(project_id, qa['question'], qa['answer'], source_type, source_id):
            st.error(f"Failed to save a QA pair to temporary storage.")
            return False
    return True

def display_review_interface(project_id, source_type, source_id=None):
    """Display and manage QA pairs in temporary storage."""
    temp_qa_pairs = AppDatabase.get_project_qa_temp(project_id)
    if source_id:
        temp_qa_pairs = [qa for qa in temp_qa_pairs if qa['source_id'] == source_id and qa['source_type'] == source_type]
    else:
        temp_qa_pairs = [qa for qa in temp_qa_pairs if qa['source_type'] == source_type]

    if not temp_qa_pairs:
        st.warning("No QA pairs in temporary storage to review.")
        return

    st.subheader("Review and Select QA Pairs")
    qa_df = pd.DataFrame([{
        "Select": True,
        "Question": qa["question"],
        "Answer": qa["answer"],
        "Source ID": qa["source_id"],
        "ID": qa["id"]
    } for qa in temp_qa_pairs])
    edited_df = st.data_editor(qa_df, hide_index=True, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Selected QA Pairs", key=f"save_selected_{source_type}_{source_id or 'manual'}"):
            selected_rows = edited_df[edited_df["Select"]]
            saved_count = 0
            for _, row in selected_rows.iterrows():
                qa = next(q for q in temp_qa_pairs if q["id"] == row["ID"])
                if AppDatabase.store_qa_pair(project_id, qa["question"], qa["answer"], qa["source_id"]):
                    AppDatabase.remove_qa_temp(project_id, qa["id"])
                    saved_count += 1
            if saved_count > 0:
                st.success(f"Saved {saved_count} QA pairs to the project!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to save selected QA pairs.")
    with col2:
        if st.button("Remove Unselected QA Pairs", key=f"remove_unselected_{source_type}_{source_id or 'manual'}"):
            unselected_rows = edited_df[~edited_df["Select"]]
            removed_count = 0
            for _, row in unselected_rows.iterrows():
                AppDatabase.remove_qa_temp(project_id, row["ID"])
                removed_count += 1
            if removed_count > 0:
                st.success(f"Removed {removed_count} QA pairs from temporary storage!")
                time.sleep(1)
                st.rerun()

def handle_manual_qa(project_id):
    """Handle manual QA entry."""
    with st.form(key="manual_qa_form"):
        question = st.text_input("Question", key="manual_question")
        answer = st.text_area("Answer", key="manual_answer")
        call_id = st.text_input("Associated Call ID (optional)", key="manual_call_id")
        submit_button = st.form_submit_button(label="Save to Temporary Storage")

    if submit_button:
        if not question or not answer:
            st.error("Question and Answer are required.")
        else:
            question = question.strip()
            answer = answer.strip()
            call_id = call_id.strip() if call_id else None
            qa_pairs = [{"question": question, "answer": answer, "call_id": call_id}]
            if save_and_review_qa_pairs(project_id, qa_pairs, "manual", "manual"):
                st.success("QA pair saved to temporary storage successfully!")
                display_review_interface(project_id, "manual", "manual")

def handle_transcript_qa(project_id, ai_provider, selected_model):
    """Handle QA generation from call transcripts."""
    calls = AppDatabase.get_project_calls(project_id)
    if not calls:
        st.warning("No calls available. Please add calls in the Call Management page first.")
        return

    call_options = st.radio("Select calls to process:", ["Select specific call", "Process multiple calls", "Process all calls"])
    
    if call_options == "Select specific call":
        call_id = st.selectbox("Select Call ID", [call["call_id"] for call in calls])
        if call_id:
            call = AppDatabase.get_call(project_id, call_id)
            if call and call["transcript"]:
                with st.expander(f"Transcript for Call {call_id}", expanded=False):
                    st.text_area("Transcript", call["transcript"], height=200, disabled=True)
        if st.button("Generate QA from Selected Call", key="gen_qa_specific"):
            with st.spinner("Generating QA pairs..."):
                call = AppDatabase.get_call(project_id, call_id)
                if call and call["transcript"]:
                    qa_pairs = generate_qa_from_transcript(call["transcript"], call_id, ai_provider, selected_model)
                    if not qa_pairs:
                        st.warning(f"No QA pairs could be generated from call {call_id}.")
                    elif save_and_review_qa_pairs(project_id, qa_pairs, "transcript", call_id):
                        st.success(f"Generated and saved {len(qa_pairs)} QA pairs to temporary storage!")
                        display_review_interface(project_id, "transcript", call_id)

    elif call_options == "Process multiple calls":
        num_calls = st.slider("Number of calls to process", min_value=1, max_value=min(50, len(calls)), value=5)
        selected_calls = st.multiselect("Select specific calls (optional)", 
                                       [call["call_id"] for call in calls], 
                                       max_selections=num_calls)
        if st.button("Generate QA from Selected Calls"):
            if not selected_calls:
                selected_calls = [call["call_id"] for call in calls[:num_calls]]
            with st.spinner(f"Generating QA pairs from {len(selected_calls)} calls..."):
                all_qa_pairs = []
                progress_bar = st.progress(0)
                for i, call_id in enumerate(selected_calls):
                    call = AppDatabase.get_call(project_id, call_id)
                    if call and call["transcript"]:
                        qa_pairs = generate_qa_from_transcript(call["transcript"], call_id, ai_provider, selected_model)
                        all_qa_pairs.extend(qa_pairs)
                    progress_bar.progress((i + 1) / len(selected_calls))
                    time.sleep(0.5)
                progress_bar.empty()
                if not all_qa_pairs:
                    st.warning("No QA pairs could be generated from the selected calls.")
                elif save_and_review_qa_pairs(project_id, all_qa_pairs, "transcript", None):
                    st.success(f"Generated and saved {len(all_qa_pairs)} QA pairs to temporary storage!")
                    display_review_interface(project_id, "transcript")

    elif call_options == "Process all calls":
        max_calls = st.slider("Maximum number of calls to process", min_value=1, max_value=len(calls), value=min(20, len(calls)))
        if st.button("Generate QA from All Calls"):
            calls_to_process = calls[:max_calls]
            with st.spinner(f"Generating QA pairs from {len(calls_to_process)} calls..."):
                all_qa_pairs = []
                progress_bar = st.progress(0)
                for i, call in enumerate(calls_to_process):
                    if call and call["transcript"]:
                        qa_pairs = generate_qa_from_transcript(call["transcript"], call["call_id"], ai_provider, selected_model)
                        all_qa_pairs.extend(qa_pairs)
                    progress_bar.progress((i + 1) / len(calls_to_process))
                    time.sleep(0.5)
                progress_bar.empty()
                if not all_qa_pairs:
                    st.warning("No QA pairs could be generated from the calls.")
                elif save_and_review_qa_pairs(project_id, all_qa_pairs, "transcript", None):
                    st.success(f"Generated and saved {len(all_qa_pairs)} QA pairs to temporary storage!")
                    display_review_interface(project_id, "transcript")

def handle_document_qa(project_id, ai_provider, selected_model):
    """Handle QA generation from uploaded documents with chunk preview and improved error handling."""
    st.write("Upload a document to generate QA pairs from its content.")
    uploaded_file = st.file_uploader("Upload .txt or .md file", type=["txt", "md"])
    
    if uploaded_file:
        try:
            file_type = uploaded_file.name.split(".")[-1].lower()
            text = uploaded_file.read().decode("utf-8")
            
            if not text.strip():
                st.error("The uploaded file is empty. Please upload a file with content.")
                return
                
            preprocessed_text = preprocess_text(text)
            
            # Display original and preprocessed text
            col1, col2 = st.columns(2)
            with col1:
                st.write("Original Text Sample (first 500 chars):")
                st.text_area("Original", text[:500], height=200, disabled=True)
            with col2:
                st.write("Preprocessed Text Sample (first 500 chars):")
                st.text_area("Preprocessed", preprocessed_text[:500], height=200, disabled=True)

            # Chunking options with explanations
            st.info("Adjust chunk size based on the complexity of your document. Larger chunks provide more context but may result in fewer but more comprehensive QA pairs.")
            chunk_size = st.slider("Chunk Size", min_value=500, max_value=5000, value=1500, step=100)
            
            # Text splitter with adjustable overlap
            chunk_overlap = st.slider("Chunk Overlap", min_value=0, max_value=500, value=200, step=50,
                                    help="Overlap between chunks to ensure context is maintained.")
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            chunks = text_splitter.split_text(preprocessed_text)
            
            if not chunks:
                st.warning("The document could not be split into chunks. Please check the content or adjust chunk size.")
                return
                
            # Chunk preview with more detail
            st.subheader("Preview Chunks")
            st.write(f"Document split into {len(chunks)} chunks for processing.")
            num_chunks_to_preview = st.slider("Number of chunks to preview", min_value=1, max_value=min(len(chunks), 10), value=min(3, len(chunks)))
            for i, chunk in enumerate(chunks[:num_chunks_to_preview]):
                with st.expander(f"Chunk {i + 1} ({len(chunk)} characters)"):
                    st.text_area(f"Chunk {i + 1}", chunk, height=150, disabled=True)

            # Choose the number of chunks to process
            max_chunks = st.slider("Maximum chunks to process", min_value=1, max_value=len(chunks), value=min(5, len(chunks)),
                                 help="Processing more chunks will generate more QA pairs but take longer.")

            if st.button("Process Document"):
                with st.spinner("Processing document and generating QA pairs..."):
                    try:
                        # Store the document first
                        file_path = save_uploaded_file(project_id, uploaded_file)
                        if not AppDatabase.store_document(project_id, uploaded_file.name, file_path, file_type):
                            st.warning("Document was processed but could not be stored in the database.")
                        
                        all_qa_pairs = []
                        progress_bar = st.progress(0)
                        chunks_to_process = chunks[:max_chunks]
                        
                        for i, chunk in enumerate(chunks_to_process):
                            try:
                                # Add debugging
                                if i == 0:  # Just show debug for first chunk
                                    st.write(f"Debug - Processing chunk {i+1} with {len(chunk)} characters.")
                                    
                                chunk_qa_pairs = generate_qa_from_document_chunk(chunk, uploaded_file.name, ai_provider, selected_model)
                                
                                if chunk_qa_pairs:
                                    all_qa_pairs.extend(chunk_qa_pairs)
                                else:
                                    st.info(f"No QA pairs generated for chunk {i+1}. This could be because the content is not suitable for QA generation.")
                                    
                            except Exception as e:
                                st.error(f"Error processing chunk {i+1}: {str(e)}")
                                continue
                            finally:
                                progress_bar.progress((i + 1) / len(chunks_to_process))
                        
                        # Process complete
                        progress_bar.empty()
                        
                        if not all_qa_pairs:
                            st.warning("No QA pairs could be generated from the document. The content may not be suitable for QA generation or there might be API issues.")
                        else:
                            if save_and_review_qa_pairs(project_id, all_qa_pairs, file_type, uploaded_file.name):
                                st.success(f"Generated and saved {len(all_qa_pairs)} QA pairs to temporary storage!")
                                display_review_interface(project_id, file_type, uploaded_file.name)
                            else:
                                st.error("Failed to save generated QA pairs to temporary storage. Please check database connectivity.")
                    except Exception as e:
                        st.error(f"Error processing document: {str(e)}")
        except UnicodeDecodeError:
            st.error("Unable to decode the uploaded file. Please ensure it's a valid text file with UTF-8 encoding.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")