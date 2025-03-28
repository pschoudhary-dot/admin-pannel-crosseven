import pandas as pd
import json
import os
from utils.db import AppDatabase

def create_dataset_df(qa_pairs):
    """Create a DataFrame from QA pairs for dataset selection."""
    # Ensure qa_pairs is a list of dictionaries with required keys
    required_keys = ['id', 'question', 'answer']
    if not qa_pairs or not all(all(key in qa for key in required_keys) for qa in qa_pairs):
        raise ValueError("QA pairs must contain 'id', 'question', and 'answer' keys.")
    
    df = pd.DataFrame(qa_pairs)
    df['Include'] = False  # Add selection column
    # Select and reorder columns, ensuring only available columns are used
    available_columns = [col for col in ['Include', 'id', 'question', 'answer'] if col in df.columns]
    return df[available_columns]

def generate_jsonl_content(qa_pairs, selected_ids):
    """Generate JSONL content for selected QA pairs in OpenAI fine-tuning format."""
    jsonl_content = ""
    for qa_id in selected_ids:
        qa = next(qa for qa in qa_pairs if qa['id'] == qa_id)
        message = {
            "messages": [
                {"role": "user", "content": qa['question']},
                {"role": "assistant", "content": qa['answer']}
            ]
        }
        jsonl_content += json.dumps(message) + "\n"
    return jsonl_content

def save_dataset(project_id, dataset_name, file_path, jsonl_content, qa_pairs_ids):
    """Save the dataset file and store metadata in the database."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write JSONL file
        with open(file_path, "w") as f:
            f.write(jsonl_content)
        
        # Store in database
        dataset_id = AppDatabase.store_dataset(
            project_id=project_id,
            dataset_name=dataset_name,
            file_path=file_path,
            source_type="qa_pairs",
            qa_pairs_ids=qa_pairs_ids
        )
        
        if dataset_id:
            return True, "Dataset saved successfully."
        else:
            os.remove(file_path)  # Clean up if DB fails
            return False, "Failed to store dataset in database."
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)  # Clean up on error
        return False, f"Error saving dataset: {str(e)}"