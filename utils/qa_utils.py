import streamlit as st
import json
import re
import numpy as np
import google.generativeai as genai
from openai import OpenAI, AuthenticationError
from dotenv import load_dotenv
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY", "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")
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

GEMINI_MODELS = ['gemini-2.0-pro-exp-02-05', 'gemini-1.5-flash']
OPENAI_MODELS = ['gpt-4o', 'gpt-4.5-preview-2025-02-27', 'gpt-3.5-turbo-0125']

# Similarity threshold - adjust as needed
SIMILARITY_THRESHOLD = 0.85

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
    # Improved prompt with more specificity and examples
    prompt = f"""
    Below is a transcript from a customer service call about ESA (Emotional Support Animal) letters from Wellness Wag.
    Generate 5-8 question-answer pairs that simulate a NATURAL conversation between a customer and a Wellness Wag support agent.

    WHAT I NEED:
    - Create question-answer pairs that sound like they come from REAL HUMAN CONVERSATIONS
    - Questions should be in NATURAL, CASUAL language - not perfect or formal
    - Focus on how REAL CUSTOMERS actually speak (with hesitations, simple language, etc.)
    - The answers should be helpful but conversational, like a real support agent would speak
    - MAKE SURE to generate MULTIPLE DIFFERENT question-answer pairs (at least 5)

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

    MANDATORY: Generate 5-8 DIFFERENT question-answer pairs, NOT just one or two.

    Transcript:
    {transcript}

    Format your response as a JSON array of objects, where each object has ONLY 'question' and 'answer' fields. 
    Do NOT nest the array inside another object like 'questions_and_answers'. 
    Example:
    [
        {{"question": "How much does an ESA letter cost?", "answer": "It's $129 for up to two pets!"}},
        {{"question": "Um, so do I need to talk to a doctor?", "answer": "Not necessarily! If the provider needs more info, they'll contact you directly, but if everything looks good on your intake form, they'll just issue your letter."}},
        {{"question": "Hey, what's that verification thing you mentioned?", "answer": "Oh, that's the QR code on your letter! Your landlord can scan it to verify your letter is legitimate through PetVerify.org."}},
        {{"question": "I'm in California, why is it taking so long?", "answer": "California has a specific law, AB-468, that requires a 30-day relationship with a licensed provider before they can issue your ESA letter. We'll have a provider reach out for an intro call, then follow up after 30 days to issue your letter."}}
    ]
    If you cannot generate relevant questions from this transcript, return an empty array [].
    """

    # Add fallback mechanism to ensure proper output
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
                
                print(f"Gemini raw response (first 200 chars): {response_text[:200]}...")
                
                try:
                    qa_pairs = json.loads(response_text)
                    if not isinstance(qa_pairs, list) or len(qa_pairs) == 0:
                        print("Gemini response not a list or empty, trying fallback format...")
                        # Try alternative formatting that might be in the response
                        if isinstance(qa_pairs, dict) and any(k in qa_pairs for k in ['questions', 'qa_pairs', 'data']):
                            for key in ['questions', 'qa_pairs', 'data']:
                                if key in qa_pairs and isinstance(qa_pairs[key], list):
                                    qa_pairs = qa_pairs[key]
                                    break
                except json.JSONDecodeError:
                    print(f"JSON decode error for Gemini. Response: {response_text[:200]}...")
                    # Attempt to fix common JSON formatting issues
                    fixed_text = re.sub(r'(\w+):', r'"\1":', response_text)
                    fixed_text = re.sub(r'\'', r'"', fixed_text)
                    try:
                        qa_pairs = json.loads(fixed_text)
                    except:
                        print("Failed to fix JSON. Trying OpenAI as fallback.")
                        # Fall back to OpenAI if Gemini fails completely
                        return generate_qa_with_openai(transcript, call_id, selected_model)
            except Exception as e:
                print(f"Error generating QA from transcript with Gemini: {str(e)}")
                # Fall back to OpenAI
                return generate_qa_with_openai(transcript, call_id, selected_model)
        else:  # OpenAI
            return generate_qa_with_openai(transcript, call_id, selected_model)
    except Exception as e:
        print(f"Unexpected error in generate_qa_from_transcript: {str(e)}")
        return []

    # Debug output to check QA generation
    print(f"Generated {len(qa_pairs)} QA pairs from transcript")
    
    # Enhanced post-processing
    processed_qa_pairs = []
    for qa in qa_pairs:
        if not isinstance(qa, dict) or 'question' not in qa or 'answer' not in qa:
            continue
        
        # Clean and check question & answer
        question = qa['question'].strip()
        answer = qa['answer'].strip()
        
        # Skip if either is empty
        if not question or not answer:
            continue
            
        # Fix formatting
        if not question.endswith('?'):
            question += '?'
        if answer and not answer.endswith(('.', '!', '?')):
            answer += '.'
            
        # Add to processed pairs
        processed_qa_pairs.append({
            'question': question,
            'answer': answer,
            'call_id': call_id
        })
    
    # If we didn't get enough QA pairs, try again with OpenAI
    if len(processed_qa_pairs) < 3 and ai_provider == "Gemini":
        print("Not enough QA pairs generated with Gemini, falling back to OpenAI")
        return generate_qa_with_openai(transcript, call_id, 'gpt-4o')
        
    return processed_qa_pairs

def generate_qa_with_openai(transcript, call_id, selected_model='gpt-4o'):
    """Fallback function to generate QA pairs using OpenAI."""
    if not openai_api_key or not openai_client:
        print("OpenAI API key not configured for fallback")
        return []
        
    # Stronger prompt for OpenAI to encourage multiple QA pairs
    prompt = f"""
    Below is a transcript from a customer service call about ESA (Emotional Support Animal) letters.
    
    YOUR TASK: Generate 5-8 DIFFERENT question-answer pairs that sound like a natural conversation between a customer and Wellness Wag support agent.
    
    *** IMPORTANT: You MUST generate at least 5 DIFFERENT question-answer pairs. Not just 1 or 2! ***
    
    Make questions casual and natural:
    - Use words like "Um", "So", "Hey", etc.
    - Keep questions short and simple
    - Make them sound spoken, not written
    
    Make answers helpful but conversational:
    - Include contact info (email: hello@wellnesswag.com, phone: (415) 570-7864) when relevant
    - Include exact prices mentioned ($129 for up to two pets, $134 for three+ pets, $149 for PSD)
    - Address waiting periods (24 hours standard, 30 days for AR, CA, IA, LA, MT)
    
    Transcript:
    {transcript}
    
    RESPOND WITH:
    - A JSON array containing at least 5 objects, each with 'question' and 'answer' fields
    - DO NOT nest them inside another object
    - Example: [{{"question": "How much is it?", "answer": "It's $129 for up to two pets."}}]
    - NOTHING ELSE besides this JSON array
    """
    
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
        
        # Debug the response
        print(f"OpenAI raw response (first 200 chars): {response_text[:200]}...")
        
        # Parse JSON with better error handling
        try:
            qa_data = json.loads(response_text)
            
            # Handle different response structures
            if isinstance(qa_data, dict):
                if 'questions_and_answers' in qa_data:
                    qa_pairs = qa_data['questions_and_answers']
                elif 'qa_pairs' in qa_data:
                    qa_pairs = qa_data['qa_pairs']
                elif 'questions' in qa_data:
                    qa_pairs = qa_data['questions']
                elif 'data' in qa_data:
                    qa_pairs = qa_data['data']
                else:
                    # Try to extract array from any field
                    for key, value in qa_data.items():
                        if isinstance(value, list) and len(value) > 0:
                            qa_pairs = value
                            break
                    else:
                        print("Could not find array in response")
                        qa_pairs = []
            elif isinstance(qa_data, list):
                qa_pairs = qa_data
            else:
                print(f"Unexpected response type: {type(qa_data)}")
                qa_pairs = []
                
            # Validate QA pairs structure
            valid_qa_pairs = []
            for qa in qa_pairs:
                if isinstance(qa, dict) and 'question' in qa and 'answer' in qa:
                    valid_qa_pairs.append({
                        'question': qa['question'].strip(),
                        'answer': qa['answer'].strip(),
                        'call_id': call_id
                    })
                else:
                    print(f"Skipping invalid QA pair: {qa}")
            
            # If we got at least one valid pair, return them
            if valid_qa_pairs:
                print(f"Generated {len(valid_qa_pairs)} valid QA pairs with OpenAI")
                # Format the QA pairs
                for qa in valid_qa_pairs:
                    if not qa['question'].endswith('?'):
                        qa['question'] += '?'
                    if qa['answer'] and not qa['answer'].endswith(('.', '!', '?')):
                        qa['answer'] += '.'
                return valid_qa_pairs
            
            # If we reached here, we couldn't get valid QA pairs
            print("Failed to generate valid QA pairs with OpenAI")
            return []
            
        except json.JSONDecodeError as je:
            print(f"OpenAI JSON decode error: {je}. Response: {response_text[:200]}...")
            return []
    except Exception as e:
        print(f"Error generating QA with OpenAI: {str(e)}")
        return []


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
    
    # Enhanced prompt for better QA generation
    prompt = f"""
    Below is a chunk of text from a document about ESA (Emotional Support Animal) letters from Wellness Wag.
    
    YOUR TASK: Generate 3-5 meaningful question-answer pairs based on this content that would be useful for a customer support chatbot.
    
    *** IMPORTANT: You MUST generate at least 3 DIFFERENT question-answer pairs, not just 1! ***
    
    Focus on:
    1. Create separate questions for DIFFERENT pieces of information
    2. Use simple language that customers would actually use
    3. Make answers comprehensive while matching the content's tone
    
    Guidelines:
    - Include specific prices, timeframes, and requirements mentioned
    - Include Wellness Wag's contact info when relevant (email: hello@wellnesswag.com, phone: (415) 570-7864)
    - Ensure questions sound like what real customers would ask
    - Make answers accurate based on the provided content

    Document Chunk:
    {chunk}

    RESPOND WITH:
    - A JSON array containing 3-5 objects, each with 'question' and 'answer' fields
    - DO NOT nest them inside another object
    - Example: [{{"question": "How much does an ESA letter cost?", "answer": "It's $129 for up to two pets."}}]
    - NOTHING ELSE besides this JSON array
    """

    try:
        if ai_provider == "Gemini":
            if not gemini_api_key:
                print("Gemini API key not configured, using OpenAI fallback")
                return generate_document_qa_with_openai(chunk, source_id, selected_model)
            
            genai.configure(api_key=gemini_api_key)
            try:
                model = genai.GenerativeModel(selected_model)
                response = model.generate_content(prompt)
                response_text = response.text.replace('```json', '').replace('```', '').strip()
                
                # Debug logging
                print(f"Gemini document chunk response (first 200 chars): {response_text[:200]}...")
                
                try:
                    qa_pairs = json.loads(response_text)
                    if not isinstance(qa_pairs, list) or len(qa_pairs) == 0:
                        print("Gemini response not a valid list or empty, trying fallback...")
                        # Try alternative formats or fall back to OpenAI
                        return generate_document_qa_with_openai(chunk, source_id, 'gpt-4o')
                except json.JSONDecodeError:
                    print(f"Gemini JSON decode error. Falling back to OpenAI.")
                    return generate_document_qa_with_openai(chunk, source_id, 'gpt-4o')
            except Exception as e:
                print(f"Error with Gemini document QA: {str(e)}")
                return generate_document_qa_with_openai(chunk, source_id, 'gpt-4o')
        else:  # OpenAI
            return generate_document_qa_with_openai(chunk, source_id, selected_model)
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
    
    # If we didn't get enough QA pairs, try OpenAI
    if len(processed_qa_pairs) < 2 and ai_provider == "Gemini":
        print("Not enough document QA pairs generated with Gemini, falling back to OpenAI")
        return generate_document_qa_with_openai(chunk, source_id, 'gpt-4o')
        
    return processed_qa_pairs


def generate_document_qa_with_openai(chunk, source_id, selected_model='gpt-4o'):
    """Generate QA pairs from document chunks using OpenAI."""
    if not openai_api_key or not openai_client:
        print("OpenAI API key not configured for document QA")
        return []
        
    # Enhanced prompt for document QA
    prompt = f"""
    Below is a chunk of text from a document about ESA (Emotional Support Animal) letters.
    
    YOUR TASK: Generate 3-5 DIFFERENT question-answer pairs based on this content for a customer support chatbot.
    
    *** IMPORTANT: You MUST generate at least 3 DIFFERENT question-answer pairs. Not just 1 or 2! ***
    
    Focus on:
    - Creating questions for DIFFERENT aspects of the information
    - Using simple language customers would actually use
    - Making answers accurate but conversational
    
    Include:
    - Specific prices, timeframes, and requirements when mentioned
    - Wellness Wag contact info when relevant (email: hello@wellnesswag.com, phone: (415) 570-7864)
    
    Document Chunk:
    {chunk}
    
    RESPOND WITH:
    - A JSON array containing 3-5 objects with 'question' and 'answer' fields
    - DO NOT nest them inside another object
    - Example: [{{"question": "How much does an ESA letter cost?", "answer": "It's $129 for up to two pets."}}]
    - NOTHING ELSE besides this JSON array
    """
    
    try:
        response = openai_client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        response_text = response.choices[0].message.content.strip()
        
        # Debug the response
        print(f"OpenAI document QA response (first 200 chars): {response_text[:200]}...")
        
        try:
            qa_data = json.loads(response_text)
            
            # Handle different response structures
            if isinstance(qa_data, dict):
                if any(key in qa_data for key in ["questions_and_answers", "qa_pairs", "questions", "data"]):
                    for key in ["questions_and_answers", "qa_pairs", "questions", "data"]:
                        if key in qa_data:
                            qa_pairs = qa_data[key]
                            break
                else:
                    # Check if the dict itself has question/answer keys
                    if "question" in qa_data and "answer" in qa_data:
                        qa_pairs = [qa_data]
                    else:
                        # Try to find any list in the response
                        for key, value in qa_data.items():
                            if isinstance(value, list):
                                qa_pairs = value
                                break
                        else:
                            print("Could not find QA list in response")
                            qa_pairs = []
            elif isinstance(qa_data, list):
                qa_pairs = qa_data
            else:
                print(f"Unexpected response type: {type(qa_data)}")
                qa_pairs = []
                
            # Process and validate QA pairs
            valid_qa_pairs = []
            for qa in qa_pairs:
                if isinstance(qa, dict) and 'question' in qa and 'answer' in qa:
                    # Clean and format
                    question = qa['question'].strip()
                    answer = qa['answer'].strip()
                    
                    if not question or not answer:
                        continue
                        
                    if not question.endswith('?'):
                        question += '?'
                        
                    if answer and not answer.endswith(('.', '!', '?')):
                        answer += '.'
                        
                    valid_qa_pairs.append({
                        'question': question,
                        'answer': answer,
                        'source_id': source_id
                    })
                else:
                    print(f"Skipping invalid QA pair: {qa}")
            
            # Return the valid pairs if we have any
            if valid_qa_pairs:
                print(f"Generated {len(valid_qa_pairs)} valid document QA pairs with OpenAI")
                return valid_qa_pairs
            
            # If we reached here, we couldn't get valid QA pairs
            print("Failed to generate valid document QA pairs with OpenAI")
            return []
            
        except json.JSONDecodeError as je:
            print(f"OpenAI JSON decode error for document QA: {je}. Response: {response_text[:200]}...")
            return []
    except Exception as e:
        print(f"Error generating document QA with OpenAI: {str(e)}")
        return []


def check_duplicate_qa(project_id, question, existing_qa_pairs=None):
    """Check if a question is a duplicate in the project."""
    from utils.db import AppDatabase
    if existing_qa_pairs is None:
        existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
    
    # Normalize the input question
    normalized_question = normalize_text(question)
    
    # Check exact match first (faster)
    for qa in existing_qa_pairs:
        if normalize_text(qa['question']) == normalized_question:
            return qa
            
    # If no exact match, calculate similarity
    similar_qa = find_similar_question(normalized_question, existing_qa_pairs)
    if similar_qa:
        return similar_qa
        
    return None

def normalize_text(text):
    """Normalize text for similarity comparison."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def find_similar_question(question, existing_qa_pairs):
    """Find questions that are semantically similar to the input question."""
    if not existing_qa_pairs:
        return None
    
    # Extract all existing questions
    existing_questions = [normalize_text(qa['question']) for qa in existing_qa_pairs]
    
    # If we only have a few questions, use TF-IDF for similarity
    if len(existing_questions) > 0:
        try:
            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform(existing_questions + [question])
            
            # Calculate similarity between input question and all existing questions
            # The input question is the last element in the matrix
            similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
            
            # Find the most similar question above threshold
            max_similarity = max(similarities)
            if max_similarity >= SIMILARITY_THRESHOLD:
                most_similar_idx = np.argmax(similarities)
                similar_qa = existing_qa_pairs[most_similar_idx]
                # Add similarity score to the returned QA
                similar_qa['similarity_score'] = float(max_similarity)
                return similar_qa
        except Exception as e:
            print(f"Error calculating similarity: {str(e)}")
    
    return None

def calculate_qa_similarities(project_id, new_qa_pairs):
    """Calculate similarity scores for new QA pairs against existing ones."""
    from utils.db import AppDatabase
    
    # Get existing QA pairs from the project
    existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
    
    if not existing_qa_pairs:
        print("No existing QA pairs to compare against")
        return new_qa_pairs
    
    # Convert sqlite3.Row objects to dictionaries if needed
    if not isinstance(existing_qa_pairs[0], dict):
        existing_qa_pairs = [dict(qa) for qa in existing_qa_pairs]
    
    # Process each new QA pair
    for qa in new_qa_pairs:
        # Skip if no question to compare
        if not qa.get('question'):
            qa['similarity_score'] = 0.0
            qa['similar_qa_id'] = None
            continue
            
        # Find similar existing questions
        max_similarity = 0.0
        most_similar_qa = None
        
        for existing_qa in existing_qa_pairs:
            # Calculate similarity between questions
            from utils.qa_utils import calculate_text_similarity
            similarity = calculate_text_similarity(qa['question'], existing_qa['question'])
            
            # Update if this is the most similar so far
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_qa = existing_qa
        
        # Add similarity information to the QA pair
        qa['similarity_score'] = max_similarity if max_similarity >= 0.3 else 0.0
        qa['similar_qa_id'] = most_similar_qa['id'] if max_similarity >= 0.3 and most_similar_qa else None
        
        print(f"Question: {qa['question'][:30]}... | Similarity: {qa['similarity_score']:.2f} | Similar ID: {qa['similar_qa_id']}")
    
    return new_qa_pairs

def calculate_text_similarity(text1, text2):
    """Calculate cosine similarity between two texts using TF-IDF."""
    if not text1 or not text2:
        return 0.0
        
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Normalize texts
        text1 = normalize_text(text1)
        text2 = normalize_text(text2)
        
        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(similarity)
    except Exception as e:
        print(f"Error calculating text similarity: {str(e)}")
        return 0.0

def deduplicate_qa_pairs(qa_pairs, similarity_threshold=0.9):
    """Remove duplicate QA pairs based on question similarity."""
    if not qa_pairs:
        return []
        
    unique_pairs = []
    seen_questions = set()
    
    # First pass - remove exact duplicates
    for qa in qa_pairs:
        question = normalize_text(qa['question'])
        if question in seen_questions:
            continue
        seen_questions.add(question)
        unique_pairs.append(qa)
    
    # Second pass - check for semantic similarity
    if len(unique_pairs) > 1:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            
            # Extract questions for vectorization
            questions = [normalize_text(qa['question']) for qa in unique_pairs]
            
            # Create vectors
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform(questions)
            
            # Calculate pairwise similarities
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # Set diagonal to 0 to ignore self-similarity
            np.fill_diagonal(similarity_matrix, 0)
            
            # Find duplicates
            to_remove = set()
            for i in range(len(unique_pairs)):
                if i in to_remove:
                    continue
                    
                for j in range(i+1, len(unique_pairs)):
                    if j in to_remove:
                        continue
                        
                    if similarity_matrix[i, j] >= similarity_threshold:
                        # Keep the more detailed answer
                        if len(unique_pairs[i]['answer']) >= len(unique_pairs[j]['answer']):
                            to_remove.add(j)
                        else:
                            to_remove.add(i)
                            break  # Stop checking i if we're removing it
            
            # Create final list excluding duplicates
            deduped_pairs = [qa for i, qa in enumerate(unique_pairs) if i not in to_remove]
            return deduped_pairs
        except Exception as e:
            print(f"Error deduplicating QA pairs: {str(e)}")
            return unique_pairs
    
    return unique_pairs

def group_similar_qa_pairs(project_id):
    """Group similar QA pairs for review."""
    from utils.db import AppDatabase
    
    # Get all QA pairs from both storages
    qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
    qa_temp = AppDatabase.get_project_qa_temp(project_id)
    
    if not qa_pairs and not qa_temp:
        return []
    
    # Combine all pairs for grouping
    all_pairs = []
    for qa in qa_pairs:
        all_pairs.append({
            'id': qa['id'],
            'question': qa['question'],
            'answer': qa['answer'],
            'source': 'main',
            'call_id': qa.get('call_id')
        })
    
    for qa in qa_temp:
        all_pairs.append({
            'id': qa['id'],
            'question': qa['question'],
            'answer': qa['answer'],
            'source': 'temp',
            'call_id': qa.get('source_id')
        })
    
    # Find groups
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        # Normalize questions
        questions = [normalize_text(qa['question']) for qa in all_pairs]
        
        # Vectorize
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(questions)
        
        # Calculate pairwise similarities
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        # Set diagonal to 0
        np.fill_diagonal(similarity_matrix, 0)
        
        # Find groups with similarity above threshold
        groups = []
        processed = set()
        
        for i in range(len(all_pairs)):
            if i in processed:
                continue
                
            group = [all_pairs[i]]
            processed.add(i)
            
            for j in range(len(all_pairs)):
                if j in processed or i == j:
                    continue
                    
                if similarity_matrix[i, j] >= 0.85:  # Threshold
                    group.append(all_pairs[j])
                    processed.add(j)
            
            if len(group) > 1:
                groups.append({
                    'items': group,
                    'size': len(group)
                })
        
        return groups
    except Exception as e:
        print(f"Error grouping similar QA pairs: {str(e)}")
        return []