import streamlit as st
from utils.db import AppDatabase
from utils.file_utils import save_uploaded_file
from utils.qa_utils import preprocess_text, generate_qa_from_transcript, extract_md_sections, generate_qa_from_md_section, check_duplicate_qa
from dotenv import load_dotenv
import os
import pandas as pd
import google.generativeai as genai
from langchain.text_splitter import RecursiveCharacterTextSplitter
import io
import json
import re
import time

# Load environment variables
load_dotenv()

# Initialize Gemini API client
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    st.error("GEMINI_API_KEY not found in environment variables. Please set it in your .env file.")
    st.stop()

genai.configure(api_key=gemini_api_key)
gemini_model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')  # gemini-1.5-flash

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

# Helper function to preprocess text documents
def preprocess_text(text):
    """Preprocess text to standardize formatting and remove inconsistencies"""
    # Convert to lowercase
    text = text.lower()
    
    # Replace multiple newlines with a single one
    text = re.sub(r'\n{2,}', '\n', text)
    
    # Remove special characters except necessary punctuation
    text = re.sub(r'[^\w\s\.,;:?!\'"-]', ' ', text)
    
    # Replace multiple spaces with a single space
    text = re.sub(r'\s{2,}', ' ', text)
    
    # Fix header formatting for markdown
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Fix headers
        if re.match(r'^[a-z0-9\s]+:$', line):
            formatted_lines.append(f"## {line}")
        # Fix sub-headers
        elif line.endswith(':') and ':' in line and len(line.split(':')[0].strip().split()) <= 5:
            formatted_lines.append(f"### {line}")
        else:
            formatted_lines.append(line)
    
    # Join lines back together
    text = '\n'.join(formatted_lines)
    
    return text

# Helper function to generate QA pairs from transcript
def generate_qa_from_transcript(transcript, call_id):
    prompt = f"""
    Below is a transcript from a customer service call about ESA (Emotional Support Animal) letters from Wellness Wag.
    Generate 5-8 question-answer pairs that simulate a NATURAL conversation between a customer and a Wellness Wag support agent.

    WHAT I NEED:
    - Create question-answer pairs that sound like they come from REAL HUMAN CONVERSATIONS
    - Questions should be in NATURAL, CASUAL language - not perfect or formal
    - Focus on how REAL CUSTOMERS actually speak (with hesitations, simple language, etc.)
    - The answers should be helpful but conversational, like a real support agent would speak

    IMPORTANT REQUIREMENTS FOR QUESTIONS:
    1. Make questions sound NATURAL and CONVERSATIONAL - use contractions, simple language
    2. Include natural speech patterns like "Um," "So," "Hey," "I was wondering," etc.
    3. Keep questions SHORT and SIMPLE as real customers would ask
    4. Avoid formal language or perfectly structured sentences in questions
    5. Questions should only contain information the customer would actually know
    6. Make questions sound like they're spoken, not written

    IMPORTANT REQUIREMENTS FOR ANSWERS:
    1. Answers should be HELPFUL and COMPLETE but still sound conversational
    2. Include Wellness Wag's contact info (email: hello@wellnesswag.com, phone: (415) 570-7864) when relevant
    3. Focus ONLY on topics discussed in this specific transcript
    4. Include exact prices, timeframes, and processes mentioned in the transcript
    5. Make the answers thorough but still sound like a real person speaking
    6. If a question asks for info not in the conversation, direct them to contact Wellness Wag

    Transcript:
    {transcript}

    Format your response as a JSON array of objects, each with 'question' and 'answer' fields.
    If you cannot generate relevant questions from this transcript, return an empty array [].
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        response_text = response.text.replace('```json', '').replace('```', '').strip()
        qa_pairs = json.loads(response_text)
        
        for qa in qa_pairs:
            if not qa['question'].endswith('?'):
                qa['question'] += '?'
            if qa['answer'] and not qa['answer'].endswith(('.', '!', '?')):
                qa['answer'] += '.'
            qa['call_id'] = call_id
        
        return qa_pairs
    except Exception as e:
        st.error(f"Error generating QA from transcript: {str(e)}")
        return []

# Helper function to extract sections from markdown
def extract_md_sections(content):
    section_pattern = r'(^|\n)#{1,3}\s+(.*?)(?=\n)'
    section_matches = re.finditer(section_pattern, content)
    sections = []
    last_pos = 0
    
    for match in section_matches:
        section_title = match.group(2).strip()
        start_pos = match.start()
        if sections and last_pos < start_pos:
            sections[-1]['end_pos'] = start_pos
            sections[-1]['content'] = content[sections[-1]['start_pos']:sections[-1]['end_pos']]
        sections.append({'title': section_title, 'start_pos': start_pos, 'end_pos': len(content)})
        last_pos = start_pos
    
    if sections:
        sections[-1]['content'] = content[sections[-1]['start_pos']:sections[-1]['end_pos']]
    
    return sections

# Helper function to generate QA from markdown section
def generate_qa_from_md_section(section):
    prompt = f"""
    Below is content from a section titled "{section['title']}" about ESA (Emotional Support Animal) letters from Wellness Wag. 
    Generate 5-8 meaningful question-answer pairs that could be used to train a customer support chatbot.

    Focus on:
    1. Create a separate question for EACH specific piece of information in the content
    2. If there are multiple states mentioned, create a separate question for EACH state
    3. If there are specific laws or requirements mentioned, create questions about those specific details
    4. Use simple, direct language that customers would actually use
    5. Make sure answers are comprehensive and include all relevant details

    Important guidelines:
    - Include specific information like prices, timeframes, and requirements when mentioned
    - Include Wellness Wag's contact info (email: hello@wellnesswag.com, phone: (415) 570-7864) when relevant
    - Make the questions sound like real customer inquiries
    - Ensure answers are accurate based on the provided content

    Section Content:
    {section['content']}

    Format your response as a JSON array of objects, each with 'question' and 'answer' fields.
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        response_text = response.text.replace('```json', '').replace('```', '').strip()
        qa_pairs = json.loads(response_text)
        
        for qa in qa_pairs:
            if not qa['question'].endswith('?'):
                qa['question'] += '?'
            if qa['answer'] and not qa['answer'].endswith(('.', '!', '?')):
                qa['answer'] += '.'
            qa['section'] = section['title']
        
        return qa_pairs
    except Exception as e:
        st.error(f"Error generating QA from section '{section['title']}': {str(e)}")
        return []

# Helper function to check for duplicate QA pairs
def check_duplicate_qa(project_id, question, existing_qa_pairs=None):
    if existing_qa_pairs is None:
        existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
    
    # Define the normalization function
    def normalize_text(text):
        return re.sub(r'[^\w\s]', '', text.lower().strip())
    
    # Normalize the input question
    normalized_question = normalize_text(question)
    
    # Check for duplicates using the correct function name
    for qa in existing_qa_pairs:
        if normalize_text(qa['question']) == normalized_question:
            return qa
    
    return None

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Generate QA", "Import QA Pairs", "View QA Pairs", "Export QA"])

# Tab 1: Generate QA
with tab1:
    st.header("Generate QA Pairs")
    
    # Options for QA generation
    gen_options = st.radio("Generate QA from:", [
        "Manual Entry", 
        "Call Transcripts", 
        "Document Upload"
    ])
    
    # Manual QA entry
    if gen_options == "Manual Entry":
        st.subheader("Manual QA Entry")
        
        # Use a form to manage input clearing
        with st.form(key="manual_qa_form"):
            question = st.text_input("Question", key="manual_question")
            answer = st.text_area("Answer", key="manual_answer")
            call_id = st.text_input("Associated Call ID (optional)", key="manual_call_id")
            submit_button = st.form_submit_button(label="Save QA Pair")
            
        # Process form submission outside the form
        if submit_button:
            # Debug output
            st.write("DEBUG: Save QA Pair button clicked")
            
            # Validate inputs
            if not question or not answer:
                st.error("Question and Answer are required.")
            else:
                question = question.strip()
                answer = answer.strip()
                call_id = call_id.strip() if call_id else None
                # Empty string should be treated as None
                if call_id == "":
                    call_id = None
                # Ensure project_id is an integer
                try:
                    project_id = int(project_id)
                except ValueError:
                    st.error(f"Invalid project ID: {project_id}")
                    st.stop()
                
                st.write(f"DEBUG: Attempting to save - Q: {question[:30]}..., A: {answer[:30]}..., Call ID: {call_id}")
                
                # Check for duplicates
                duplicate = check_duplicate_qa(project_id, question)
                if duplicate:
                    st.warning(f"A similar question already exists: '{duplicate['question']}'")
                    duplicate_action = st.radio(
                        "What would you like to do?",
                        ["Skip (don't save)", "Override existing", "Save as new entry"],
                        key="duplicate_action_manual"
                    )
                    
                    if duplicate_action == "Override existing":
                        st.write("DEBUG: Overriding existing QA pair")
                        remove_success = AppDatabase.remove_qa_pair(project_id, duplicate['id'])
                        if remove_success:
                            store_success = AppDatabase.store_qa_pair(project_id, question, answer, call_id)
                            if store_success:
                                st.success("QA pair updated successfully!")
                                time.sleep(1)  # Give user time to see the success message
                                st.rerun()
                            else:
                                st.error("Failed to store updated QA pair.")
                        else:
                            st.error("Failed to remove existing QA pair.")
                    
                    elif duplicate_action == "Save as new entry":
                        st.write("DEBUG: Saving as new entry despite duplicate")
                        store_success = AppDatabase.store_qa_pair(project_id, question, answer, call_id)
                        if store_success:
                            st.success("New QA pair saved successfully!")
                            time.sleep(1)  # Give user time to see the success message
                            st.rerun()
                        else:
                            st.error("Failed to save new QA pair.")
                    
                    else: 
                        st.info("QA pair not saved (skipped due to duplicate).")
                
                else:
                    st.write("DEBUG: No duplicate found, saving new QA pair")
                    store_success = AppDatabase.store_qa_pair(project_id, question, answer, call_id)
                    if store_success:
                        st.success("QA pair saved successfully!")
                        time.sleep(1)  # Give user time to see the success message
                        st.rerun()
                    else:
                        st.error("Failed to save QA pair. Check database logs.")
                        st.write(f"DEBUG: Error details - Project ID: {project_id}, Question: {question[:30]}..., Answer: {answer[:30]}..., Call ID: {call_id}")
    
    # Generate from call transcripts
    elif gen_options == "Call Transcripts":
        st.subheader("Generate from Call Transcripts")
        
        # Get available calls
        calls = AppDatabase.get_project_calls(project_id)
        
        if not calls:
            st.warning("No calls available. Please add calls in the Call Management page first.")
        else:
            call_options = st.radio(
                "Select calls to process:", 
                ["Select specific call", "Process multiple calls", "Process all calls"]
            )
            
            if call_options == "Select specific call":
                call_id = st.selectbox("Select Call ID", [call["call_id"] for call in calls])
                
                if st.button("Generate QA from Selected Call"):
                    with st.spinner("Generating QA pairs..."):
                        call = AppDatabase.get_call(project_id, call_id)
                        if call and call["transcript"]:
                            qa_pairs = generate_qa_from_transcript(call["transcript"], call_id)
                            
                            if not qa_pairs:
                                st.warning(f"No QA pairs could be generated from call {call_id}.")
                            else:
                                # Preview generated QA pairs
                                st.success(f"Generated {len(qa_pairs)} QA pairs!")
                                
                                # Show preview with checkboxes
                                st.subheader("Review Generated QA Pairs")
                                
                                # Check for duplicates and allow selection
                                existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
                                selected_qa_pairs = []
                                
                                for i, qa in enumerate(qa_pairs):
                                    duplicate = check_duplicate_qa(project_id, qa['question'], existing_qa_pairs)
                                    
                                    with st.expander(f"QA Pair #{i+1}: {qa['question'][:50]}..."):
                                        st.write(f"**Question:** {qa['question']}")
                                        st.write(f"**Answer:** {qa['answer']}")
                                        
                                        if duplicate:
                                            st.warning(f"Similar question exists: '{duplicate['question']}'")
                                            action = st.radio(
                                                "Action for this pair:",
                                                ["Skip", "Override existing", "Save as new"],
                                                key=f"action_{i}"
                                            )
                                            qa['action'] = action
                                            qa['duplicate_id'] = duplicate['id']
                                        else:
                                            include = st.checkbox("Include this pair", value=True, key=f"include_{i}")
                                            qa['action'] = "Save as new" if include else "Skip"
                                        
                                        if qa['action'] != "Skip":
                                            selected_qa_pairs.append(qa)
                                
                                if selected_qa_pairs:
                                    if st.button("Save Selected QA Pairs"):
                                        saved_count = 0
                                        updated_count = 0
                                        
                                        for qa in selected_qa_pairs:
                                            if qa['action'] == "Override existing":
                                                AppDatabase.remove_qa_pair(project_id, qa['duplicate_id'])
                                                success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                                if success:
                                                    updated_count += 1
                                            elif qa['action'] == "Save as new":
                                                success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                                if success:
                                                    saved_count += 1
                                        
                                        if saved_count > 0 or updated_count > 0:
                                            result_msg = []
                                            if saved_count > 0:
                                                result_msg.append(f"{saved_count} new QA pairs saved")
                                            if updated_count > 0:
                                                result_msg.append(f"{updated_count} existing QA pairs updated")
                                            
                                            st.success(f"Operation completed successfully! {' and '.join(result_msg)}.")
                                            st.rerun()
                                else:
                                    st.warning("No QA pairs selected for saving.")
            
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
                                qa_pairs = generate_qa_from_transcript(call["transcript"], call_id, gemini_model)
                                if qa_pairs:
                                    all_qa_pairs.extend(qa_pairs)
                            
                            progress_bar.progress((i + 1) / len(selected_calls))
                            time.sleep(0.5)  # To avoid rate limiting
                        
                        progress_bar.empty()
                        
                        if not all_qa_pairs:
                            st.warning("No QA pairs could be generated from the selected calls.")
                        else:
                            st.success(f"Generated {len(all_qa_pairs)} QA pairs in total!")
                            
                            # Preview in expandable sections
                            st.subheader("Review Generated QA Pairs")
                            
                            # Group by call_id for better organization
                            qa_by_call = {}
                            for qa in all_qa_pairs:
                                if qa['call_id'] not in qa_by_call:
                                    qa_by_call[qa['call_id']] = []
                                qa_by_call[qa['call_id']].append(qa)
                            
                            # Button to save all without checking duplicates (for bulk operations)
                            if st.button("Save All Without Checking Duplicates"):
                                saved_count = 0
                                for qa in all_qa_pairs:
                                    # Validate data before saving
                                    if not qa.get('question') or not qa.get('answer'):
                                        st.error(f"Invalid QA pair data: missing question or answer")
                                        continue
                                        
                                    success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                    if success:
                                        saved_count += 1
                                    else:
                                        st.error(f"Failed to save QA pair: {qa['question'][:50]}...")
                                        
                                    # Add a small delay to prevent database locking
                                    time.sleep(0.1)
                                
                                st.success(f"Saved {saved_count} QA pairs successfully!")
                                st.rerun()
                            
                            # Or review each call's QA pairs
                            st.write("Or review QA pairs by call:")
                            
                            for call_id, qa_pairs in qa_by_call.items():
                                with st.expander(f"Call ID: {call_id} ({len(qa_pairs)} pairs)"):
                                    for i, qa in enumerate(qa_pairs):
                                        st.write(f"**Q{i+1}:** {qa['question']}")
                                        st.write(f"**A{i+1}:** {qa['answer']}")
                                        st.write("---")
                            
                                    call_selected = st.checkbox(f"Save all pairs from call {call_id}", value=True, key=f"save_call_{call_id}")
                                    
                                    if call_selected:
                                        duplicate_action = st.radio(
                                            "If duplicates are found:",
                                            ["Skip duplicates", "Override existing", "Save as new entries"],
                                            key=f"dup_action_{call_id}"
                                        )
                                        
                                        if st.button(f"Save QA Pairs for Call {call_id}"):
                                            existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
                                            saved_count = 0
                                            updated_count = 0
                                            skipped_count = 0
                                            
                                            for qa in qa_pairs:
                                                duplicate = check_duplicate_qa(project_id, qa['question'], existing_qa_pairs)
                                                
                                                if duplicate:
                                                    if duplicate_action == "Skip duplicates":
                                                        skipped_count += 1
                                                        continue
                                                    elif duplicate_action == "Override existing":
                                                        AppDatabase.remove_qa_pair(project_id, duplicate['id'])
                                                        success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                                        if success:
                                                            updated_count += 1
                                                    else:  # Save as new
                                                        success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                                        if success:
                                                            saved_count += 1
                                                else:
                                                    success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                                    if success:
                                                        saved_count += 1
                                            
                                            result_msg = []
                                            if saved_count > 0:
                                                result_msg.append(f"{saved_count} new QA pairs saved")
                                            if updated_count > 0:
                                                result_msg.append(f"{updated_count} existing QA pairs updated")
                                            if skipped_count > 0:
                                                result_msg.append(f"{skipped_count} duplicates skipped")
                                            
                                            st.success(f"Operation completed successfully! {' and '.join(result_msg)}.")
            
            elif call_options == "Process all calls":
                max_calls = st.slider("Maximum number of calls to process", 
                                    min_value=1, 
                                    max_value=len(calls), 
                                    value=min(20, len(calls)))
                
                if st.button("Generate QA from All Calls"):
                    calls_to_process = calls[:max_calls]
                    with st.spinner(f"Generating QA pairs from {len(calls_to_process)} calls..."):
                        all_qa_pairs = []
                        progress_bar = st.progress(0)
                        
                        for i, call in enumerate(calls_to_process):
                            if call and call["transcript"]:
                                qa_pairs = generate_qa_from_transcript(call["transcript"], call["call_id"], gemini_model)
                                if qa_pairs:
                                    all_qa_pairs.extend(qa_pairs)
                            
                            progress_bar.progress((i + 1) / len(calls_to_process))
                            time.sleep(0.5)  # To avoid rate limiting
                        
                        progress_bar.empty()
                        
                        if not all_qa_pairs:
                            st.warning("No QA pairs could be generated from the calls.")
                        else:
                            st.success(f"Generated {len(all_qa_pairs)} QA pairs in total!")
                            
                            duplicate_action = st.radio(
                                "If duplicates are found:",
                                ["Skip duplicates", "Override existing", "Save as new entries"],
                                key="bulk_dup_action"
                            )
                            
                            if st.button("Save All Generated QA Pairs"):
                                existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
                                saved_count = 0
                                updated_count = 0
                                skipped_count = 0
                                
                                for qa in all_qa_pairs:
                                    duplicate = check_duplicate_qa(project_id, qa['question'], existing_qa_pairs)
                                    
                                    if duplicate:
                                        if duplicate_action == "Skip duplicates":
                                            skipped_count += 1
                                            continue
                                        elif duplicate_action == "Override existing":
                                            AppDatabase.remove_qa_pair(project_id, duplicate['id'])
                                            success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                            if success:
                                                updated_count += 1
                                        else:  # Save as new
                                            success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                            if success:
                                                saved_count += 1
                                    else:
                                        success = AppDatabase.store_qa_pair(project_id, qa['question'], qa['answer'], qa['call_id'])
                                        if success:
                                            saved_count += 1
                                
                                result_msg = []
                                if saved_count > 0:
                                    result_msg.append(f"{saved_count} new QA pairs saved")
                                if updated_count > 0:
                                    result_msg.append(f"{updated_count} existing QA pairs updated")
                                if skipped_count > 0:
                                    result_msg.append(f"{skipped_count} duplicates skipped")
                                
                                st.success(f"Operation completed successfully! {' and '.join(result_msg)}.")
                                st.rerun()
    
    # Generate from document upload
    elif gen_options == "Document Upload":
        st.subheader("Generate from Document")
        uploaded_file = st.file_uploader("Upload .txt or .md file", type=["txt", "md"])
        
        if uploaded_file:
            file_type = uploaded_file.name.split(".")[-1].lower()
            text = uploaded_file.read().decode("utf-8")
            
            # Preprocess the text
            preprocessed_text = preprocess_text(text)
            
            # Show before/after preprocessing
            col1, col2 = st.columns(2)
            with col1:
                st.write("Original Text Sample (first 500 chars):")
                st.text_area("Original", text[:500], height=200, disabled=True)
            with col2:
                st.write("Preprocessed Text Sample (first 500 chars):")
                st.text_area("Preprocessed", preprocessed_text[:500], height=200, disabled=True)
            
            chunk_size = st.slider("Chunk Size", min_value=500, max_value=5000, value=1500, step=100,
                                 help="Larger chunks include more context but may result in less specific QA pairs")
            
            if st.button("Process Document"):
                with st.spinner("Processing document..."):
                    # Save the file for future reference
                    file_path = save_uploaded_file(project_id, uploaded_file)
                    AppDatabase.store_document(project_id, uploaded_file.name, file_path, file_type)
                    
                    if file_type == "md":
                        sections = extract_md_sections(preprocessed_text)
                        
                        if not sections:
                            # If no sections found, treat as plain text
                            text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=200)
                            chunks = text_splitter.split_text(preprocessed_text)
                            
                            all_qa_pairs = []
                            progress_bar = st.progress(0)
                            
                            for i, chunk in enumerate(chunks):
                                qa_chunk = generate_qa_from_transcript(chunk, None, gemini_model)
                                all_qa_pairs.extend(qa_chunk)
                                progress_bar.progress((i + 1) / len(chunks))
                                time.sleep(0.5)  # To avoid rate limiting
                            
                            progress_bar.empty()
                        else:
                            all_qa_pairs = []
                            progress_bar = st.progress(0)
                            
                            for i, section in enumerate(sections):
                                qa_pairs = generate_qa_from_md_section(section, gemini_model)
                                all_qa_pairs.extend(qa_pairs)
                                progress_bar.progress((i + 1) / len(sections))
                                time.sleep(0.5)  # To avoid rate limiting
                            
                            progress_bar.empty()
                    else:
                        # Plain text processing
                        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=200)
                        chunks = text_splitter.split_text(preprocessed_text)
                        
                        all_qa_pairs = []
                        progress_bar = st.progress(0)
                        
                        for i, chunk in enumerate(chunks):
                            qa_chunk = generate_qa_from_transcript(chunk, None)
                            all_qa_pairs.extend(qa_chunk)
                            progress_bar.progress((i + 1) / len(chunks))
                            time.sleep(0.5)  # To avoid rate limiting
                        
                        progress_bar.empty()
                    
                    if not all_qa_pairs:
                        st.warning("No QA pairs could be generated from the document.")
                    else:
                        st.success(f"Generated {len(all_qa_pairs)} QA pairs from the document!")
                        
                        # Show preview with ability to select pairs
                        st.subheader("Review Generated QA Pairs")
                        
                        # Create dataframe for better display and selection
                        qa_df = pd.DataFrame([{
                            "Select": True,
                            "Question": qa["question"],
                            "Answer": qa["answer"],
                            "Section": qa.get("section", "Main")
                        } for qa in all_qa_pairs])
                        
                        edited_df = st.data_editor(qa_df, hide_index=True, use_container_width=True)
                        
                        # Options for handling duplicates
                        duplicate_action = st.radio(
                            "If duplicates are found:",
                            ["Skip duplicates", "Override existing", "Save as new entries"],
                            key="doc_dup_action"
                        )
                        
                        if st.button("Save Selected QA Pairs"):
                            selected_rows = edited_df[edited_df["Select"]]
                            
                            if len(selected_rows) == 0:
                                st.error("Please select at least one QA pair to save.")
                            else:
                                existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
                                saved_count = 0
                                updated_count = 0
                                skipped_count = 0
                                
                                for _, row in selected_rows.iterrows():
                                    question = row["Question"]
                                    answer = row["Answer"]
                                    
                                    duplicate = check_duplicate_qa(project_id, question, existing_qa_pairs)
                                    
                                    if duplicate:
                                        if duplicate_action == "Skip duplicates":
                                            skipped_count += 1
                                            continue
                                        elif duplicate_action == "Override existing":
                                            AppDatabase.remove_qa_pair(project_id, duplicate['id'])
                                            success = AppDatabase.store_qa_pair(project_id, question, answer, None)
                                            if success:
                                                updated_count += 1
                                        else:  # Save as new
                                            success = AppDatabase.store_qa_pair(project_id, question, answer, None)
                                            if success:
                                                saved_count += 1
                                    else:
                                        success = AppDatabase.store_qa_pair(project_id, question, answer, None)
                                        if success:
                                            saved_count += 1
                                
                                result_msg = []
                                if saved_count > 0:
                                    result_msg = []
                                if saved_count > 0:
                                    result_msg.append(f"{saved_count} new QA pairs saved")
                                if updated_count > 0:
                                    result_msg.append(f"{updated_count} existing QA pairs updated")
                                if skipped_count > 0:
                                    result_msg.append(f"{skipped_count} duplicates skipped")
                                
                                st.success(f"Operation completed successfully! {' and '.join(result_msg)}.")
                                st.rerun()

# Tab 2: Import QA Pairs
with tab2:
    st.header("Import QA Pairs")
    uploaded_file = st.file_uploader("Upload CSV or Excel file with QA pairs", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success("File uploaded successfully!")
            
            # Column mapping
            st.subheader("Map Columns")
            columns = df.columns.tolist()
            question_col = st.selectbox("Select Question Column", columns, key="question_col")
            answer_col = st.selectbox("Select Answer Column", columns, key="answer_col")
            call_id_col = st.session_state.get("import_call_id_col")
            
            # Optional call_id column
            has_call_id = st.checkbox("File includes Call ID column", value=False)
            if has_call_id:
                call_id_col = st.selectbox("Select Call ID Column", columns, key="call_id_col")
            
            # Preview data
            st.subheader("Preview Data")
            preview_cols = [question_col, answer_col]
            if has_call_id:
                preview_cols.append(call_id_col)
            
            preview_df = df[preview_cols].copy()
            column_map = {
                question_col: "Question",
                answer_col: "Answer"
            }
            if has_call_id:
                column_map[call_id_col] = "Call ID"
            
            preview_df = preview_df.rename(columns=column_map)
            preview_df.insert(0, "Import", True)
            
            # Clean up the data
            preview_df["Question"] = preview_df["Question"].astype(str).apply(lambda x: x.strip())
            preview_df["Answer"] = preview_df["Answer"].astype(str).apply(lambda x: x.strip())
            if has_call_id:
                preview_df["Call ID"] = preview_df["Call ID"].astype(str).apply(lambda x: x.strip() if x and x.lower() != 'nan' else None)
            
            # Remove completely empty rows
            preview_df = preview_df.dropna(subset=["Question", "Answer"], how='all')
            
            # Data editor for review
            edited_df = st.data_editor(preview_df, hide_index=True, use_container_width=True)
            
            # Import selected QA pairs
            if st.button("Import Selected QA Pairs"):
                selected_rows = edited_df[edited_df["Import"]]
                if len(selected_rows) == 0:
                    st.error("Please select at least one QA pair to import.")
                else:
                    # Check for existing QA pairs
                    existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
                    duplicate_count = 0
                    
                    for _, row in selected_rows.iterrows():
                        question = row["Question"]
                        duplicate = check_duplicate_qa(project_id, question, existing_qa_pairs)
                        if duplicate:
                            duplicate_count += 1
                    
                    if duplicate_count > 0:
                        st.warning(f"Found {duplicate_count} potential duplicate question(s). How would you like to proceed?")
                        duplicate_action = st.radio(
                            "Choose action for duplicates:",
                            ["Skip duplicates", "Override existing", "Save as new entries"],
                            key="import_dup_action"
                        )
                    else:
                        duplicate_action = "Skip duplicates"  # Default, but won't matter
                    
                    confirm_import = st.button("Confirm Import")
                    if confirm_import:
                        with st.spinner("Importing QA pairs, please wait..."):
                            saved_count = 0
                            updated_count = 0
                            skipped_count = 0
                            error_count = 0
                            
                            for _, row in selected_rows.iterrows():
                                question = row["Question"]
                                answer = row["Answer"]
                                call_id = row.get("Call ID", None)
                                
                                # Skip empty questions or answers
                                if not question or not answer or pd.isna(question) or pd.isna(answer):
                                    error_count += 1
                                    continue
                                
                                # Clean up call_id
                                if call_id and (pd.isna(call_id) or call_id.lower() == 'nan' or call_id.strip() == ''):
                                    call_id = None
                                
                                # Check for duplicates
                                duplicate = check_duplicate_qa(project_id, question, existing_qa_pairs)
                                
                                try:
                                    if duplicate:
                                        if duplicate_action == "Skip duplicates":
                                            skipped_count += 1
                                            continue
                                        elif duplicate_action == "Override existing":
                                            remove_success = AppDatabase.remove_qa_pair(project_id, duplicate['id'])
                                            if not remove_success:
                                                st.error(f"Failed to remove existing QA pair: '{question[:50]}...'")
                                                error_count += 1
                                                continue
                                                
                                            success = AppDatabase.store_qa_pair(project_id, question, answer, call_id)
                                            if success:
                                                updated_count += 1
                                            else:
                                                st.error(f"Failed to update QA pair: '{question[:50]}...'")
                                                error_count += 1
                                        else:  # Save as new
                                            success = AppDatabase.store_qa_pair(project_id, question, answer, call_id)
                                            if success:
                                                saved_count += 1
                                            else:
                                                st.error(f"Failed to save new QA pair: '{question[:50]}...'")
                                                error_count += 1
                                    else:
                                        success = AppDatabase.store_qa_pair(project_id, question, answer, call_id)
                                        if success:
                                            saved_count += 1
                                        else:
                                            st.error(f"Failed to save QA pair: '{question[:50]}...'")
                                            error_count += 1
                                            
                                    # Add a small delay to prevent database locking
                                    time.sleep(0.1)
                                    
                                except Exception as e:
                                    st.error(f"Error processing QA pair: {str(e)}")
                                    error_count += 1
                        
                        # Show import results
                        result_msg = []
                        if saved_count > 0:
                            result_msg.append(f"{saved_count} new QA pairs saved")
                        if updated_count > 0:
                            result_msg.append(f"{updated_count} existing QA pairs updated")
                        if skipped_count > 0:
                            result_msg.append(f"{skipped_count} duplicates skipped")
                        if error_count > 0:
                            result_msg.append(f"{error_count} errors encountered")
                        
                        if saved_count > 0 or updated_count > 0:
                            st.success(f"Import completed successfully! {' and '.join(result_msg)}")
                            # Give user time to see the success message before refreshing
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"Import failed. {' and '.join(result_msg)}")
                            st.write("Please check the console logs for more details or try again.")
                
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

# Tab 3: View QA Pairs and Generate from Calls
with tab3:
    st.header("View QA Pairs")
    qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
    
    if not qa_pairs:
        st.write("No QA pairs stored in this project yet.")
    else:
        st.write(f"Total QA pairs: {len(qa_pairs)}")
        
        # Add search and filter functionality
        search_query = st.text_input("Search for questions containing:", key="qa_search")
        
        # Filter by call ID
        call_ids = list(set([qa["call_id"] for qa in qa_pairs if qa["call_id"]]))
        if call_ids:
            filter_call = st.checkbox("Filter by Call ID")
            if filter_call:
                selected_call_id = st.selectbox("Select Call ID", 
                                             ["All"] + call_ids,
                                             key="filter_call_id")
            else:
                selected_call_id = "All"
        else:
            selected_call_id = "All"
        
        # Apply filters
        filtered_qa_pairs = qa_pairs
        if search_query:
            filtered_qa_pairs = [qa for qa in filtered_qa_pairs if search_query.lower() in qa["question"].lower()]
        
        if selected_call_id != "All":
            filtered_qa_pairs = [qa for qa in filtered_qa_pairs if qa["call_id"] == selected_call_id]
        
        st.write(f"Showing {len(filtered_qa_pairs)} of {len(qa_pairs)} QA pairs")
        
        # Pagination
        items_per_page = st.slider("Items per page", 5, 50, 10)
        total_pages = max(1, (len(filtered_qa_pairs) + items_per_page - 1) // items_per_page)
        
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            page_number = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
        
        start_idx = (page_number - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(filtered_qa_pairs))
        
        page_items = filtered_qa_pairs[start_idx:end_idx]
        
        for i, qa in enumerate(page_items):
            with st.expander(f"#{qa['id']} - {qa['question'][:50]}..."):
                st.write(f"**Question:** {qa['question']}")
                st.write(f"**Answer:** {qa['answer']}")
                st.write(f"**Call ID:** {qa['call_id'] or 'None'}")
                st.write(f"**Created on:** {qa['created_at']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Edit", key=f"edit_{qa['id']}"):
                        st.session_state.editing_qa_id = qa['id']
                        st.session_state.editing_question = qa['question']
                        st.session_state.editing_answer = qa['answer']
                        st.session_state.editing_call_id = qa['call_id']
                        st.rerun()
                with col2:
                    if st.button("Delete", key=f"delete_{qa['id']}"):
                        if AppDatabase.remove_qa_pair(project_id, qa["id"]):
                            st.success("QA pair deleted successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to delete QA pair.")
        
        # Show editing form if needed
        if hasattr(st.session_state, 'editing_qa_id'):
            st.subheader(f"Edit QA Pair #{st.session_state.editing_qa_id}")
            edited_question = st.text_area("Question", st.session_state.editing_question, key="edit_question")
            edited_answer = st.text_area("Answer", st.session_state.editing_answer, key="edit_answer")
            edited_call_id = st.text_input("Call ID (optional)", 
                                        st.session_state.editing_call_id or "", 
                                        key="edit_call_id")
            
            if edited_call_id.strip() == "":
                edited_call_id = None
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Changes"):
                    # First remove the old entry
                    AppDatabase.remove_qa_pair(project_id, st.session_state.editing_qa_id)
                    # Then add the updated version
                    if AppDatabase.store_qa_pair(project_id, edited_question, edited_answer, edited_call_id):
                        st.success("QA pair updated successfully!")
                        # Clean up session state
                        del st.session_state.editing_qa_id
                        del st.session_state.editing_question
                        del st.session_state.editing_answer
                        del st.session_state.editing_call_id
                        st.rerun()
                    else:
                        st.error("Failed to update QA pair.")
            with col2:
                if st.button("Cancel"):
                    # Clean up session state
                    del st.session_state.editing_qa_id
                    del st.session_state.editing_question
                    del st.session_state.editing_answer
                    del st.session_state.editing_call_id
                    st.rerun()

# Tab 4: Export QA Pairs
with tab4:
    st.header("Export QA Pairs")
    qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
    
    if not qa_pairs:
        st.write("No QA pairs available to export.")
    else:
        # Filter options for export
        st.subheader("Export Options")
        export_opt = st.radio("Select what to export:", 
                           ["All QA Pairs", "Filter by Search", "Select Specific Pairs"])
        
        export_format = st.selectbox("Export Format", ["CSV", "Excel", "JSONL"], key="export_format")
        
        # Initialize empty filtered list
        filtered_export_pairs = []
        
        if export_opt == "All QA Pairs":
            filtered_export_pairs = qa_pairs
            st.write(f"Exporting all {len(qa_pairs)} QA pairs")
            
        elif export_opt == "Filter by Search":
            search_query = st.text_input("Search for questions containing:", key="export_search")
            
            # Filter by call ID
            call_ids = list(set([qa["call_id"] for qa in qa_pairs if qa["call_id"]]))
            if call_ids:
                filter_call = st.checkbox("Filter by Call ID", key="export_filter_call")
                if filter_call:
                    selected_call_id = st.selectbox("Select Call ID", 
                                               ["All"] + call_ids,
                                               key="export_filter_call_id")
                else:
                    selected_call_id = "All"
            else:
                selected_call_id = "All"
            
            # Apply filters
            filtered_export_pairs = qa_pairs
            if search_query:
                filtered_export_pairs = [qa for qa in filtered_export_pairs if search_query.lower() in qa["question"].lower()]
            
            if selected_call_id != "All":
                filtered_export_pairs = [qa for qa in filtered_export_pairs if qa["call_id"] == selected_call_id]
            
            st.write(f"Exporting {len(filtered_export_pairs)} of {len(qa_pairs)} QA pairs")
            
        elif export_opt == "Select Specific Pairs":
            selected_qa_ids = st.multiselect("Select QA Pairs to Export",
                                          [f"#{qa['id']} - {qa['question'][:50]}..." for qa in qa_pairs],
                                          key="export_selected_pairs")
            
            # Extract IDs from selection strings
            selected_ids = [int(item.split('-')[0][1:].strip()) for item in selected_qa_ids]
            
            filtered_export_pairs = [qa for qa in qa_pairs if qa["id"] in selected_ids]
            
            st.write(f"Exporting {len(filtered_export_pairs)} selected QA pairs")
        
        # Preview export data
        if filtered_export_pairs:
            st.subheader("Export Preview")
            
            preview_df = pd.DataFrame([{
                "ID": qa["id"],
                "Question": qa["question"],
                "Answer": qa["answer"],
                "Call ID": qa["call_id"] or "",
                "Created At": qa["created_at"]
            } for qa in filtered_export_pairs[:5]])  # Show only first 5 for preview
            
            st.dataframe(preview_df, use_container_width=True)
            
            if len(filtered_export_pairs) > 5:
                st.info(f"Showing preview of first 5 entries. Full export will include {len(filtered_export_pairs)} entries.")
            
            # Generate export file
            export_df = pd.DataFrame([{
                "ID": qa["id"],
                "Question": qa["question"],
                "Answer": qa["answer"],
                "Call ID": qa["call_id"] or "",
                "Created At": qa["created_at"]
            } for qa in filtered_export_pairs])
            
            if export_format == "CSV":
                csv_data = export_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"qa_pairs_project_{project_id}.csv",
                    mime="text/csv"
                )
            elif export_format == "Excel":
                buffer = io.BytesIO()
                export_df.to_excel(buffer, index=False)
                buffer.seek(0)
                st.download_button(
                    label="Download Excel",
                    data=buffer.getvalue(),
                    file_name=f"qa_pairs_project_{project_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:  # JSONL
                # Convert to JSONL format (one JSON object per line)
                jsonl_data = "" 
                for _, row in export_df.iterrows():
                    # Convert row to dict and then to JSON string
                    json_obj = {
                        "id": row["ID"],
                        "question": row["Question"],
                        "answer": row["Answer"],
                        "call_id": row["Call ID"] if row["Call ID"] else None,
                        "created_at": row["Created At"]
                    }
                    jsonl_data += json.dumps(json_obj) + "\n"
                
                st.download_button(
                    label="Download JSONL",
                    data=jsonl_data,
                    file_name=f"qa_pairs_project_{project_id}.jsonl",
                    mime="application/jsonl"
                )