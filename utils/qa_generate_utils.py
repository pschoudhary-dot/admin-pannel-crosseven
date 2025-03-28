import streamlit as st
import pandas as pd
from utils.db import AppDatabase
import time
from utils.qa_utils import (
    generate_qa_from_transcript, 
    generate_qa_from_document_chunk, 
    preprocess_text, 
    extract_md_sections,
    calculate_qa_similarities
)
from utils.file_utils import save_uploaded_file
from langchain.text_splitter import RecursiveCharacterTextSplitter
import time

def save_and_review_qa_pairs(project_id, qa_pairs, source_type, source_id):
    """Save QA pairs to temporary storage with similarity scoring and provide review interface."""

    # First, verify we have content to process
    if not qa_pairs:
        st.warning("No QA pairs to save.")
        return False
    
    # Calculate similarity scores for all QA pairs
    enhanced_qa_pairs = calculate_qa_similarities(project_id, qa_pairs)
    
    # Store each pair with similarity information
    success_count = 0
    for qa in enhanced_qa_pairs:
        # Extract similarity data
        similarity_score = qa.get('similarity_score', 0.0)
        similar_qa_id = qa.get('similar_qa_id', None)
        
        # Print debug info
        print(f"Storing QA: {qa['question'][:30]}... | Similarity: {similarity_score:.2f} | Similar ID: {similar_qa_id}")
        
        # Store in database with similarity info
        if AppDatabase.store_qa_temp_with_similarity(
            project_id, 
            qa['question'], 
            qa['answer'], 
            source_type, 
            source_id,
            similarity_score,
            similar_qa_id
        ):
            success_count += 1
        else:
            st.error(f"Failed to save QA pair to temporary storage: {qa['question'][:50]}...")
    
    return success_count > 0

def display_review_interface(project_id, source_type, source_id=None):
    """Display and manage QA pairs in temporary storage with similarity information."""
    temp_qa_pairs = AppDatabase.get_project_qa_temp(project_id)
    
    # Convert sqlite3.Row objects to dictionaries first
    temp_qa_pairs = [dict(qa) for qa in temp_qa_pairs]
    
    # Filter based on source and ID
    if source_id:
        temp_qa_pairs = [qa for qa in temp_qa_pairs if qa['source_id'] == source_id and qa['source_type'] == source_type]
    else:
        temp_qa_pairs = [qa for qa in temp_qa_pairs if qa['source_type'] == source_type]

    if not temp_qa_pairs:
        st.warning("No QA pairs in temporary storage to review.")
        return

    st.subheader("Review and Select QA Pairs")
    
    # Create a dataframe with styling for similarity levels
    qa_rows = []
    for qa in temp_qa_pairs:
        similarity = qa.get('similarity_score', 0.0)
        if similarity is None:
            similarity = 0.0
            
        # Format similarity display value
        similarity_display = f"{similarity:.2f}" if similarity != 0.0 else "N/A"
        
        # Determine row styling
        style = ""
        if similarity >= 0.9:
            style = "background-color: rgba(255, 0, 0, 0.2);"  # Red for high similarity
        elif similarity >= 0.7:
            style = "background-color: rgba(255, 255, 0, 0.2);"  # Yellow for medium similarity
        elif similarity >= 0.3:
            style = "background-color: rgba(0, 255, 0, 0.1);"  # Light green for low similarity
            
        qa_rows.append({
            "Select": True,
            "Question": qa["question"],
            "Answer": qa["answer"],
            "Source ID": qa["source_id"] or "N/A",
            "Similarity": similarity_display,
            "Similar QA": qa["similar_qa_id"] if qa["similar_qa_id"] is not None else "None",
            "ID": qa["id"],
            "_style": style
        })
    
    # Create the dataframe
    qa_df = pd.DataFrame(qa_rows)
    
    # Display the legend for similarity scores
    st.write("QA pairs with similarity scores:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("🔴 **Red**: High similarity (≥ 0.9)")
    with col2:
        st.markdown("🟡 **Yellow**: Mid similarity (≥ 0.7)")
    with col3:
        st.markdown("🟢 **Green**: Low similarity (≥ 0.3)")
        
    
    # Create the data editor
    edited_df = st.data_editor(
        qa_df.drop(columns=['_style']),  # Remove the style column
        hide_index=True,
        use_container_width=True,
        column_config={
            "Similarity": st.column_config.NumberColumn(
                "Similarity Score",
                help="How similar this question is to existing QA pairs"
            ),
            "Similar QA": st.column_config.TextColumn(
                "Similar QA ID",
                help="ID of the most similar existing question"
            ),
            "Question": st.column_config.TextColumn(
                "Question",
                width="large"
            ),
            "Answer": st.column_config.TextColumn(
                "Answer",
                width="large"
            )
        }
    )

    col1, col2, col3 = st.columns(3)
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
    with col3:
        if st.button("Deduplicate Similar QA Pairs", key=f"deduplicate_{source_type}_{source_id or 'manual'}"):
            # Keep only one of each highly similar group
            similarity_threshold = 0.9
            kept_questions = set()
            removed_count = 0
            
            # First pass - mark duplicates
            for qa in temp_qa_pairs:
                similarity_score = qa.get('similarity_score', 0)
                if similarity_score is not None and similarity_score >= similarity_threshold:
                    # If we already have a similar question in our kept set, remove this one
                    keep_this = True
                    for kept_q in kept_questions:
                        if qa["question"] == kept_q or calculate_qa_similarities(qa["question"], kept_q) >= similarity_threshold:
                            AppDatabase.remove_qa_temp(project_id, qa["id"])
                            removed_count += 1
                            keep_this = False
                            break
                    
                    if keep_this:
                        kept_questions.add(qa["question"])
            
            if removed_count > 0:
                st.success(f"Removed {removed_count} duplicate QA pairs!")
                time.sleep(1)
                st.rerun()
            else:
                st.info("No duplicate QA pairs found.")
                
    # If similarities exist, show a more detailed view
    similar_pairs = [qa for qa in temp_qa_pairs if qa.get('similarity_score', 0) >= 0.7 and qa.get('similar_qa_id')]
    if similar_pairs:
        st.subheader("Similar Question Analysis")
        st.write("The following questions have similar existing questions in the main QA database:")
        
        for qa in similar_pairs:
            similarity_score = qa.get('similarity_score')
            similar_qa_id = qa.get('similar_qa_id')
            
            if similar_qa_id:
                similar_qa = AppDatabase.get_qa_pair_by_id(project_id, similar_qa_id)
                if similar_qa:
                    # Convert to dict if needed
                    if not isinstance(similar_qa, dict):
                        similar_qa = dict(similar_qa)
                        
                    with st.expander(f"New: '{qa['question']}' (Similarity: {similarity_score:.2f})"):
                        st.write("**New Question:**", qa['question'])
                        st.write("**New Answer:**", qa['answer'])
                        st.write("---")
                        st.write("**Similar Existing Question:**", similar_qa['question'])
                        st.write("**Existing Answer:**", similar_qa['answer'])
                        st.write(f"**Similarity Score:** {similarity_score:.2f}")
                        
                        # Buttons for this specific pair
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Keep New Version", key=f"keep_new_{qa['id']}"):
                                # Replace old with new
                                if AppDatabase.remove_qa_pair(project_id, similar_qa['id']) and \
                                   AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['source_id']):
                                    AppDatabase.remove_qa_temp(project_id, qa['id'])
                                    st.success("Replaced existing QA with new version!")
                                    time.sleep(1)
                                    st.rerun()
                        with c2:
                            if st.button("Discard New Version", key=f"discard_new_{qa['id']}"):
                                # Just remove the new one
                                AppDatabase.remove_qa_temp(project_id, qa['id'])
                                st.success("Discarded new version, keeping existing QA!")
                                time.sleep(1)
                                st.rerun()

def handle_manual_qa(project_id):
    """Handle manual QA entry with similarity checking."""
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
            
            # Check for similar questions before saving
            from utils.qa_utils import check_duplicate_qa
            existing_qa = check_duplicate_qa(project_id, question)
            
            if existing_qa and existing_qa.get('similarity_score', 0) > 0.9:
                st.warning(f"This question is very similar to an existing one: '{existing_qa['question']}'")
                st.info("You can still save it or modify your question to be more distinct.")
                
                # Show the existing QA for comparison
                with st.expander("View Similar Existing QA"):
                    st.write("**Existing Question:**", existing_qa['question'])
                    st.write("**Existing Answer:**", existing_qa['answer'])
                    st.write(f"**Similarity Score:** {existing_qa.get('similarity_score', 0):.2f}")
                
                # Offer to continue or cancel
                if st.button("Save Anyway"):
                    qa_pairs = [{
                        "question": question, 
                        "answer": answer, 
                        "call_id": call_id,
                        "similarity_score": existing_qa.get('similarity_score', 0),
                        "similar_qa_id": existing_qa['id']
                    }]
                    if save_and_review_qa_pairs(project_id, qa_pairs, "manual", "manual"):
                        st.success("QA pair saved to temporary storage successfully!")
                        display_review_interface(project_id, "manual", "manual")
            else:
                # No significant similarity found, proceed normally
                qa_pairs = [{"question": question, "answer": answer, "call_id": call_id}]
                if save_and_review_qa_pairs(project_id, qa_pairs, "manual", "manual"):
                    st.success("QA pair saved to temporary storage successfully!")
                    display_review_interface(project_id, "manual", "manual")

def handle_transcript_qa(project_id, ai_provider, selected_model):
    """Handle QA generation from call transcripts with improved generation and similarity checking."""
    calls = AppDatabase.get_project_calls(project_id)
    if not calls:
        st.warning("No calls available. Please add calls in the Call Management page first.")
        return

    call_options = st.radio("Select calls to process:", ["Select specific call", "Process multiple calls", "Process all calls"])
    
    # Enhanced provider and model selection at function level
    col1, col2 = st.columns(2)
    with col1:
        generation_attempts = st.number_input("Generation attempts per call", min_value=1, max_value=3, value=1,
                                           help="If the first attempt generates fewer than 3 QA pairs, try again this many times")
    with col2:
        min_qa_pairs = st.number_input("Minimum QA pairs expected", min_value=1, max_value=10, value=3,
                                     help="Minimum number of QA pairs to consider successful generation")
    
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
                    attempts = 0
                    qa_pairs = []
                    
                    while attempts < generation_attempts and (not qa_pairs or len(qa_pairs) < min_qa_pairs):
                        attempts += 1
                        if attempts > 1:
                            st.info(f"Attempt {attempts}: Generated only {len(qa_pairs)} QA pairs, trying again...")
                        
                        qa_pairs = generate_qa_from_transcript(call["transcript"], call_id, ai_provider, selected_model)
                    
                    if not qa_pairs:
                        st.warning(f"Could not generate any QA pairs from call {call_id} after {attempts} attempts.")
                    elif len(qa_pairs) < min_qa_pairs:
                        st.warning(f"Generated only {len(qa_pairs)} QA pairs (fewer than desired minimum of {min_qa_pairs}).")
                        if save_and_review_qa_pairs(project_id, qa_pairs, "transcript", call_id):
                            st.success(f"Saved {len(qa_pairs)} QA pairs to temporary storage.")
                            display_review_interface(project_id, "transcript", call_id)
                    else:
                        st.success(f"Generated {len(qa_pairs)} QA pairs from transcript!")
                        if save_and_review_qa_pairs(project_id, qa_pairs, "transcript", call_id):
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
                        attempts = 0
                        call_qa_pairs = []
                        
                        while attempts < generation_attempts and (not call_qa_pairs or len(call_qa_pairs) < min_qa_pairs):
                            attempts += 1
                            call_qa_pairs = generate_qa_from_transcript(call["transcript"], call_id, ai_provider, selected_model)
                        
                        if call_qa_pairs:
                            all_qa_pairs.extend(call_qa_pairs)
                            st.write(f"Generated {len(call_qa_pairs)} QA pairs from call {call_id}")
                        else:
                            st.warning(f"Could not generate QA pairs from call {call_id}")
                    
                    progress_bar.progress((i + 1) / len(selected_calls))
                    time.sleep(0.5)
                
                progress_bar.empty()
                
                if not all_qa_pairs:
                    st.warning("No QA pairs could be generated from the selected calls.")
                else:
                    if save_and_review_qa_pairs(project_id, all_qa_pairs, "transcript", None):
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
                        attempts = 0
                        call_qa_pairs = []
                        
                        while attempts < generation_attempts and (not call_qa_pairs or len(call_qa_pairs) < min_qa_pairs):
                            attempts += 1
                            call_qa_pairs = generate_qa_from_transcript(call["transcript"], call["call_id"], ai_provider, selected_model)
                        
                        if call_qa_pairs:
                            all_qa_pairs.extend(call_qa_pairs)
                            st.write(f"Generated {len(call_qa_pairs)} QA pairs from call {call['call_id']}")
                        else:
                            st.warning(f"Could not generate QA pairs from call {call['call_id']}")
                    
                    progress_bar.progress((i + 1) / len(calls_to_process))
                    time.sleep(0.5)
                
                progress_bar.empty()
                
                if not all_qa_pairs:
                    st.warning("No QA pairs could be generated from the calls.")
                else:
                    if save_and_review_qa_pairs(project_id, all_qa_pairs, "transcript", None):
                        st.success(f"Generated and saved {len(all_qa_pairs)} QA pairs to temporary storage!")
                        display_review_interface(project_id, "transcript")

def handle_document_qa(project_id, ai_provider, selected_model):
    """Handle QA generation from uploaded documents with improved processing and similarity checking."""
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

            # Improved chunk options
            st.subheader("Chunking Settings")
            st.info("Adjust chunk size based on the complexity of your document. Larger chunks provide more context but may result in fewer but more comprehensive QA pairs.")
            
            col1, col2 = st.columns(2)
            with col1:
                chunk_size = st.slider("Chunk Size", min_value=500, max_value=5000, value=1500, step=100)
            with col2:
                chunk_overlap = st.slider("Chunk Overlap", min_value=0, max_value=500, value=200, step=50,
                                        help="Overlap between chunks to ensure context is maintained.")
            
            # Generation settings
            col1, col2 = st.columns(2)
            with col1:
                generation_attempts = st.number_input("Generation attempts per chunk", min_value=1, max_value=3, value=1,
                                                  help="If the first attempt generates fewer than min QA pairs, try again")
            with col2:
                min_qa_pairs = st.number_input("Minimum QA pairs per chunk", min_value=1, max_value=10, value=3,
                                             help="Minimum number of QA pairs to consider successful for each chunk")
            
            # Create text splitter and get chunks
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
                                # Generate QA pairs from the chunk with retry logic
                                attempts = 0
                                chunk_qa_pairs = []
                                
                                while attempts < generation_attempts and (not chunk_qa_pairs or len(chunk_qa_pairs) < min_qa_pairs):
                                    attempts += 1
                                    chunk_qa_pairs = generate_qa_from_document_chunk(
                                        chunk, uploaded_file.name, ai_provider, selected_model
                                    )
                                
                                if chunk_qa_pairs:
                                    all_qa_pairs.extend(chunk_qa_pairs)
                                    st.write(f"Generated {len(chunk_qa_pairs)} QA pairs from chunk {i+1}")
                                else:
                                    st.info(f"No QA pairs generated for chunk {i+1}.")
                                    
                            except Exception as e:
                                st.error(f"Error processing chunk {i+1}: {str(e)}")
                                continue
                            finally:
                                progress_bar.progress((i + 1) / len(chunks_to_process))
                        
                        # Process complete
                        progress_bar.empty()
                        
                        if not all_qa_pairs:
                            st.warning("No QA pairs could be generated from the document.")
                        else:
                            total_qa_pairs = len(all_qa_pairs)
                            st.success(f"Generated a total of {total_qa_pairs} QA pairs from {len(chunks_to_process)} chunks!")
                            
                            # Calculate similarities and store in temp
                            if save_and_review_qa_pairs(project_id, all_qa_pairs, file_type, uploaded_file.name):
                                display_review_interface(project_id, file_type, uploaded_file.name)
                            else:
                                st.error("Failed to save QA pairs to temporary storage.")
                    except Exception as e:
                        st.error(f"Error processing document: {str(e)}")
        except UnicodeDecodeError:
            st.error("Unable to decode the uploaded file. Please ensure it's a valid text file with UTF-8 encoding.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")