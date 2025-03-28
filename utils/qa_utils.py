import streamlit as st
import json
import re
import google.generativeai as genai
from openai import OpenAI, AuthenticationError
from dotenv import load_dotenv
import os

load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")
openai_api_key = "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"
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

GEMINI_MODELS = ['gemini-2.0-pro-exp-02-05', 'gemini-1.5-flash']
OPENAI_MODELS = ['gpt-4o', 'gpt-4.5-preview-2025-02-27', 'gpt-3.5-turbo-0125']

def preprocess_text(text):
    """Preprocess text to standardize formatting and remove inconsistencies."""
    text = text.lower()
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r'[^\w\s\.,;:?!\'"-]', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    lines = text.split('\n')
    formatted_lines = []
    for line in lines:
        line = line.strip()
        if re.match(r'^[a-z0-9\s]+:$', line):
            formatted_lines.append(f"## {line}")
        elif line.endswith(':') and ':' in line and len(line.split(':')[0].strip().split()) <= 5:
            formatted_lines.append(f"### {line}")
        else:
            formatted_lines.append(line)
    return '\n'.join(formatted_lines).strip()

def extract_md_sections(content):
    """Extract sections from markdown content."""
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

def generate_qa_from_transcript(transcript, call_id, ai_provider, selected_model):
    """Generate QA pairs from a transcript using the selected AI provider and model."""
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

    Format your response as a JSON array of objects, where each object has ONLY 'question' and 'answer' fields. 
    Do NOT nest the array inside another object like 'questions_and_answers'. 
    Example:
    [
        {{"question": "How much does an ESA letter cost?", "answer": "It's $129 for up to two pets!"}}
    ]
    If you cannot generate relevant questions from this transcript, return an empty array [].
    """

    if ai_provider == "Gemini":
        if not gemini_api_key:
            st.error("Gemini API key is not configured.")
            return []
        genai.configure(api_key=gemini_api_key)
        try:
            response = genai.GenerativeModel(selected_model).generate_content(prompt)
            response_text = response.text.replace('```json', '').replace('```', '').strip()
            qa_pairs = json.loads(response_text)
        except Exception as e:
            st.error(f"Error generating QA from transcript with Gemini: {str(e)}")
            return []
    else:  # OpenAI
        if not openai_api_key or not openai_client:
            st.error("OpenAI API key is not configured in the environment. Please check your .env file.")
            return []
        try:
            # Test API key validity
            openai_client.models.list()
            response = openai_client.chat.completions.create(
                model=selected_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            response_text = response.choices[0].message.content.strip()
            # Parse JSON and handle potential nesting
            qa_data = json.loads(response_text)
            if isinstance(qa_data, dict) and 'questions_and_answers' in qa_data:
                qa_pairs = qa_data['questions_and_answers']  # Flatten nested structure
            else:
                qa_pairs = qa_data if isinstance(qa_data, list) else [qa_data]
            # Ensure each item has 'question' and 'answer'
            valid_qa_pairs = []
            for qa in qa_pairs:
                if isinstance(qa, dict) and 'question' in qa and 'answer' in qa:
                    valid_qa_pairs.append(qa)
                else:
                    st.warning(f"Skipping invalid QA pair: {qa}")
            qa_pairs = valid_qa_pairs
        except AuthenticationError as e:
            st.error(f"OpenAI API authentication failed: {str(e)}. Please verify your API key in the .env file.")
            return []
        except json.JSONDecodeError:
            st.error("OpenAI failed to return structured JSON output. Response: " + response_text[:100] + "...")
            return []
        except Exception as e:
            st.error(f"Error generating QA from transcript with OpenAI: {str(e)}")
            return []

    # Post-process QA pairs
    processed_qa_pairs = []
    for qa in qa_pairs:
        if not isinstance(qa, dict) or 'question' not in qa or 'answer' not in qa:
            continue
        if not qa['question'].endswith('?'):
            qa['question'] += '?'
        if qa['answer'] and not qa['answer'].endswith(('.', '!', '?')):
            qa['answer'] += '.'
        qa['call_id'] = call_id
        processed_qa_pairs.append(qa)
    return processed_qa_pairs

def generate_qa_from_document_chunk(chunk, source_id, ai_provider, selected_model):
    """Generate QA pairs from a document chunk using the selected AI provider and model."""
    
    # Skip empty or very short chunks
    if not chunk or len(chunk.strip()) < 50:
        print(f"Skipping chunk: Too short or empty ({len(chunk) if chunk else 0} chars)")
        return []
    
    # Trim extremely long chunks to prevent API errors
    MAX_CHUNK_LENGTH = 15000
    if len(chunk) > MAX_CHUNK_LENGTH:
        chunk = chunk[:MAX_CHUNK_LENGTH]
        print(f"Trimmed chunk to {MAX_CHUNK_LENGTH} characters")
    
    prompt = f"""
    Below is a chunk of text from a document about ESA (Emotional Support Animal) letters from Wellness Wag.
    Generate 3-5 meaningful question-answer pairs that could be used to train a customer support chatbot.

    Focus on:
    1. Create a separate question for EACH specific piece of information in the content
    2. Use simple, direct language that customers would actually use
    3. Make sure answers are comprehensive and include all relevant details from the chunk

    Important guidelines:
    - Include specific information like prices, timeframes, and requirements when mentioned
    - Include Wellness Wag's contact info (email: hello@wellnesswag.com, phone: (415) 570-7864) when relevant
    - Make the questions sound like real customer inquiries
    - Ensure answers are accurate based on the provided content

    Document Chunk:
    {chunk}

    Format your response as a JSON array of objects, each with 'question' and 'answer' fields.
    Example:
    [
        {{"question": "How much does an ESA letter cost?", "answer": "It's $129 for up to two pets!"}}
    ]
    If you cannot generate relevant questions from this chunk, return an empty array [].
    """

    try:
        if ai_provider == "Gemini":
            if not gemini_api_key:
                st.error("Gemini API key is not configured.")
                return []
            
            genai.configure(api_key=gemini_api_key)
            try:
                model = genai.GenerativeModel(selected_model)
                response = model.generate_content(prompt)
                response_text = response.text.replace('```json', '').replace('```', '').strip()
                
                # Debug for the first response
                print(f"Gemini raw response (first 100 chars): {response_text[:100]}...")
                
                try:
                    qa_pairs = json.loads(response_text)
                    if not isinstance(qa_pairs, list):
                        print(f"Expected list, got {type(qa_pairs)}: {response_text[:100]}...")
                        return []
                except json.JSONDecodeError as je:
                    print(f"JSON decode error: {je}. Response: {response_text[:100]}...")
                    return []
            except Exception as e:
                print(f"Error generating QA from document chunk with Gemini: {str(e)}")
                return []
        else:  # OpenAI
            if not openai_api_key or not openai_client:
                st.error("OpenAI API key is not configured in the environment. Please check your .env file.")
                return []
            
            try:
                # Test API key validity
                openai_client.models.list()
                response = openai_client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2048,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                response_text = response.choices[0].message.content.strip()
                
                # Debug for the first response
                print(f"OpenAI raw response (first 100 chars): {response_text[:100]}...")
                
                try:
                    qa_data = json.loads(response_text)
                    
                    # Handle various response formats
                    if isinstance(qa_data, dict):
                        if 'questions_and_answers' in qa_data:
                            qa_pairs = qa_data['questions_and_answers']
                        elif any(key in qa_data for key in ["questions", "qa_pairs", "qa"]):
                            # Handle other possible key names
                            for key in ["questions", "qa_pairs", "qa"]:
                                if key in qa_data and isinstance(qa_data[key], list):
                                    qa_pairs = qa_data[key]
                                    break
                            else:
                                # If we didn't find a list in any of the keys
                                qa_pairs = [qa_data]
                        else:
                            # Try to use the whole dict as is if it has question/answer keys
                            if "question" in qa_data and "answer" in qa_data:
                                qa_pairs = [qa_data]
                            else:
                                print(f"Unexpected dict structure: {list(qa_data.keys())}")
                                qa_pairs = []
                    elif isinstance(qa_data, list):
                        qa_pairs = qa_data
                    else:
                        print(f"Unexpected response type: {type(qa_data)}")
                        qa_pairs = []
                except json.JSONDecodeError as je:
                    print(f"OpenAI JSON decode error: {je}. Response: {response_text[:100]}...")
                    return []
                
                # Ensure each item has 'question' and 'answer'
                valid_qa_pairs = []
                for qa in qa_pairs:
                    if isinstance(qa, dict) and 'question' in qa and 'answer' in qa:
                        valid_qa_pairs.append(qa)
                    else:
                        print(f"Skipping invalid QA pair: {qa}")
                qa_pairs = valid_qa_pairs
            except Exception as e:
                print(f"Error generating QA from document chunk with OpenAI: {str(e)}")
                return []
    except Exception as e:
        print(f"Unexpected error in generate_qa_from_document_chunk: {str(e)}")
        return []

    # Post-process QA pairs
    processed_qa_pairs = []
    for qa in qa_pairs:
        if not isinstance(qa, dict) or 'question' not in qa or 'answer' not in qa:
            continue
        
        # Clean up the question and answer
        question = qa['question'].strip()
        answer = qa['answer'].strip()
        
        # Skip if either is empty
        if not question or not answer:
            continue
            
        # Add question mark if missing
        if not question.endswith('?'):
            question += '?'
            
        # Add period if missing at end of answer
        if answer and not answer.endswith(('.', '!', '?')):
            answer += '.'
            
        processed_qa_pairs.append({
            'question': question,
            'answer': answer,
            'source_id': source_id
        })
        
    return processed_qa_pairs


def check_duplicate_qa(project_id, question, existing_qa_pairs=None):
    """Check if a question is a duplicate in the project."""
    from utils.db import AppDatabase
    if existing_qa_pairs is None:
        existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
    def normalize_text(text):
        return re.sub(r'[^\w\s]', '', text.lower().strip())
    normalized_question = normalize_text(question)
    for qa in existing_qa_pairs:
        if normalize_text(qa['question']) == normalized_question:
            return qa
    return None