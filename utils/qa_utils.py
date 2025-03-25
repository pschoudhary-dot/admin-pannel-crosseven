import re
import json
import google.generativeai as genai
import streamlit as st
from utils.db import AppDatabase

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

def generate_qa_from_transcript(transcript, call_id, gemini_model):
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

def generate_qa_from_md_section(section, gemini_model):
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

def check_duplicate_qa(project_id, question, existing_qa_pairs=None):
    if existing_qa_pairs is None:
        existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
    def normalize_text(text):
        return re.sub(r'[^\w\s]', '', text.lower().strip())
    normalized_question = normalize_text(question)
    for qa in existing_qa_pairs:
        if normalize_text(qa['question']) == normalized_question:
            return qa
    return None