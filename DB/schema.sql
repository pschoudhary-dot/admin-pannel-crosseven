-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    description TEXT,
    created_by INTEGER,  -- Nullable, tracks the user who created the project
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- Project members table
CREATE TABLE IF NOT EXISTS project_users (
    project_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer', -- owner, editor, viewer
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Calls table
CREATE TABLE IF NOT EXISTS calls (
    call_id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    transcript TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Utterances table
CREATE TABLE IF NOT EXISTS utterances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT,
    project_id INTEGER NOT NULL,
    role TEXT,
    content TEXT,
    utterance_index INTEGER,
    FOREIGN KEY (call_id) REFERENCES calls(call_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- QA Pairs table
CREATE TABLE IF NOT EXISTS qa_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    call_id TEXT,
    question TEXT,
    answer TEXT,
    is_trained BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (call_id) REFERENCES calls(call_id)
);

-- QA Temp table
CREATE TABLE IF NOT EXISTS qa_temp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    is_reviewed BOOLEAN DEFAULT 0,
    similarity_score REAL,
    similar_qa_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (similar_qa_id) REFERENCES qa_pairs(id)
);

-- Datasets table
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    dataset_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    source_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Models table
CREATE TABLE IF NOT EXISTS models (
    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    dataset_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    model_path TEXT NOT NULL,
    version TEXT,
    qa_pairs_id TEXT,  -- JSON array of qa_pair IDs used for training
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id)
);

-- Indices for faster lookups
CREATE INDEX IF NOT EXISTS idx_qa_temp_project ON qa_temp(project_id);
CREATE INDEX IF NOT EXISTS idx_qa_temp_source ON qa_temp(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_qa_temp_reviewed ON qa_temp(is_reviewed);
CREATE INDEX IF NOT EXISTS idx_models_project ON models(project_id);
CREATE INDEX IF NOT EXISTS idx_models_dataset ON models(dataset_id);