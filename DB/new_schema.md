### **1. `users` Table**
**Purpose**: Stores information about registered users of the application, including their credentials and basic details.

| Column Name    | Data Type | Constraints                          | Description                                                                 |
|----------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `user_id`      | INTEGER   | PRIMARY KEY AUTOINCREMENT            | Unique identifier for each user, automatically incremented by SQLite.      |
| `username`     | TEXT      | UNIQUE NOT NULL                      | The username chosen by the user, must be unique and cannot be null.        |
| `password_hash`| TEXT      | NOT NULL                             | Hashed password for secure storage, cannot be null.                        |
| `email`        | TEXT      | (None)                               | Optional email address for the user; can be null.                          |
| `created_at`   | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP            | Date and time when the user account was created, defaults to current time. |

**Key Features**:
- `user_id` serves as the primary key, ensuring each user has a unique identifier.
- `username` has a `UNIQUE` constraint to prevent duplicate usernames.
- `password_hash` stores a hashed password (e.g., using a library like `pbkdf2_sha256`), enhancing security.
- `email` is optional, allowing flexibility for users who don’t provide it.
- `created_at` provides an audit trail for account creation.

**Relationships**: None (this is a root table).

---

### **2. `projects` Table**
**Purpose**: Represents projects created by users to organize their work (e.g., calls, documents, QA pairs).

| Column Name    | Data Type | Constraints                          | Description                                                                 |
|----------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `project_id`   | INTEGER   | PRIMARY KEY AUTOINCREMENT            | Unique identifier for each project, automatically incremented.             |
| `user_id`      | INTEGER   | NOT NULL FOREIGN KEY (users.user_id) | Links the project to a user; references `users(user_id)`.                  |
| `project_name` | TEXT      | NOT NULL                             | Name of the project, must be provided.                                     |
| `description`  | TEXT      | (None)                               | Optional description of the project; can be null.                          |
| `created_at`   | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP            | Date and time when the project was created, defaults to current time.      |

**Key Features**:
- `project_id` is the primary key.
- `user_id` is a foreign key linking to `users`, ensuring every project belongs to a user.
- `UNIQUE (user_id, project_name)` constraint prevents a user from creating multiple projects with the same name.
- `description` is optional for additional context.
- `created_at` tracks project creation time.

**Relationships**:
- One-to-many with `users`: A user can have multiple projects.

---

### **3. `documents` Table**
**Purpose**: Stores metadata about files uploaded to a project, such as transcripts or other supporting documents.

| Column Name    | Data Type | Constraints                          | Description                                                                 |
|----------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `document_id`  | INTEGER   | PRIMARY KEY AUTOINCREMENT            | Unique identifier for each document, automatically incremented.            |
| `project_id`   | INTEGER   | NOT NULL FOREIGN KEY (projects.project_id) | Links the document to a project; references `projects(project_id)`.  |
| `file_name`    | TEXT      | NOT NULL                             | Name of the uploaded file, cannot be null.                                 |
| `file_path`    | TEXT      | NOT NULL                             | File system path where the document is stored, cannot be null.             |
| `file_type`    | TEXT      | (None)                               | Type of file (e.g., "txt", "pdf"), optional and can be null.               |
| `uploaded_at`  | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP            | Date and time when the document was uploaded, defaults to current time.    |

**Key Features**:
- `document_id` is the primary key.
- `project_id` is a foreign key linking to `projects`, associating each document with a project.
- `file_name` and `file_path` are required for tracking uploaded files.
- `file_type` is optional, providing flexibility (e.g., for MIME types or extensions).
- `uploaded_at` records the upload timestamp.

**Relationships**:
- One-to-many with `projects`: A project can have multiple documents.

---

### **4. `calls` Table**
**Purpose**: Stores call data, including transcripts, associated with a project.

| Column Name    | Data Type | Constraints                          | Description                                                                 |
|----------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `call_id`      | TEXT      | PRIMARY KEY                          | Unique identifier for each call (e.g., from an external telephony system). |
| `project_id`   | INTEGER   | NOT NULL FOREIGN KEY (projects.project_id) | Links the call to a project; references `projects(project_id)`.      |
| `transcript`   | TEXT      | (None)                               | Transcript of the call; can be null if unavailable.                        |
| `timestamp`    | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP            | Date and time when the call was stored, defaults to current time.          |

**Key Features**:
- `call_id` is the primary key, using `TEXT` to accommodate external identifiers (e.g., UUIDs or strings).
- `project_id` is a foreign key linking to `projects`.
- `transcript` is optional, allowing calls to be stored without a transcript.
- `timestamp` tracks when the call data was added.

**Relationships**:
- One-to-many with `projects`: A project can have multiple calls.

---

### **5. `utterances` Table**
**Purpose**: Breaks down call transcripts into individual utterances (e.g., spoken lines by different roles).

| Column Name      | Data Type | Constraints                          | Description                                                                 |
|------------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `id`             | INTEGER   | PRIMARY KEY AUTOINCREMENT            | Unique identifier for each utterance, automatically incremented.           |
| `call_id`        | TEXT      | FOREIGN KEY (calls.call_id)          | Links the utterance to a call; references `calls(call_id)`.                |
| `project_id`     | INTEGER   | NOT NULL FOREIGN KEY (projects.project_id) | Links the utterance to a project; references `projects(project_id)`. |
| `role`           | TEXT      | (None)                               | Role of the speaker (e.g., "agent", "customer"); can be null.              |
| `content`        | TEXT      | (None)                               | Text of the utterance; can be null.                                        |
| `utterance_index`| INTEGER   | (None)                               | Order of the utterance within the call; can be null.                       |

**Key Features**:
- `id` is the primary key.
- `call_id` is a foreign key linking to `calls`, associating utterances with a specific call.
- `project_id` is a foreign key linking to `projects`, redundant but useful for direct project-level queries.
- `role`, `content`, and `utterance_index` are optional, providing flexibility in utterance data.

**Relationships**:
- One-to-many with `calls`: A call can have multiple utterances.
- One-to-many with `projects`: A project can have multiple utterances (though typically via `calls`).

---

### **6. `qa_pairs` Table**
**Purpose**: Stores finalized question-answer pairs, often derived from calls or other sources, for use in applications like chatbots.

| Column Name    | Data Type | Constraints                          | Description                                                                 |
|----------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `id`           | INTEGER   | PRIMARY KEY AUTOINCREMENT            | Unique identifier for each QA pair, automatically incremented.             |
| `project_id`   | INTEGER   | NOT NULL FOREIGN KEY (projects.project_id) | Links the QA pair to a project; references `projects(project_id)`.   |
| `call_id`      | TEXT      | FOREIGN KEY (calls.call_id)          | Links the QA pair to a call; references `calls(call_id)`, can be null.     |
| `question`     | TEXT      | (None)                               | The question text; can be null but typically required by app logic.        |
| `answer`       | TEXT      | (None)                               | The answer text; can be null but typically required by app logic.          |
| `created_at`   | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP            | Date and time when the QA pair was created, defaults to current time.      |

**Key Features**:
- `id` is the primary key.
- `project_id` is a foreign key linking to `projects`, ensuring each QA pair belongs to a project.
- `call_id` is an optional foreign key linking to `calls`, allowing QA pairs to be call-specific or independent.
- `question` and `answer` are nullable in the schema but likely enforced as non-null by application logic.
- `created_at` tracks creation time.

**Relationships**:
- One-to-many with `projects`: A project can have multiple QA pairs.
- One-to-many with `calls`: A call can have multiple QA pairs (optional link).

---

### **7. `qa_temp` Table**
**Purpose**: Temporarily stores generated QA pairs before review and potential transfer to `qa_pairs`.

| Column Name       | Data Type | Constraints                          | Description                                                                 |
|-------------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `id`              | INTEGER   | PRIMARY KEY AUTOINCREMENT            | Unique identifier for each temp QA pair, automatically incremented.        |
| `project_id`      | INTEGER   | NOT NULL FOREIGN KEY (projects.project_id) | Links to a project; references `projects(project_id)`.               |
| `question`        | TEXT      | NOT NULL                             | The generated question, must be provided.                                  |
| `answer`          | TEXT      | NOT NULL                             | The generated answer, must be provided.                                    |
| `source_type`     | TEXT      | NOT NULL                             | Source of the QA pair (e.g., "call", "document", "manual"), required.      |
| `source_id`       | TEXT      | (None)                               | Identifier of the source (e.g., `call_id`), optional.                      |
| `is_trained`      | BOOLEAN   | DEFAULT 0                            | Flag: 0 (not used in training), 1 (used in training), defaults to 0.       |
| `is_reviewed`     | BOOLEAN   | DEFAULT 0                            | Flag: 0 (not reviewed), 1 (reviewed), defaults to 0.                       |
| `similarity_score`| REAL      | (None)                               | Score indicating similarity to an existing QA pair; can be null.           |
| `similar_qa_id`   | INTEGER   | FOREIGN KEY (qa_pairs.id)            | Links to a similar QA pair in `qa_pairs`; can be null.                     |
| `metadata`        | TEXT      | (None)                               | Additional metadata (e.g., JSON); can be null.                             |
| `created_at`      | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP            | Date and time of creation, defaults to current time.                       |

**Key Features**:
- `id` is the primary key.
- `project_id` is a foreign key linking to `projects`.
- `question`, `answer`, and `source_type` are required for basic QA data and origin tracking.
- `source_id` is optional, linking to specific sources like a `call_id`.
- `is_trained` and `is_reviewed` track the QA pair’s lifecycle.
- `similarity_score` and `similar_qa_id` support duplicate detection with `qa_pairs`.
- `metadata` allows flexible additional data storage.
- Indices on `project_id`, `(source_type, source_id)`, and `is_trained` improve query performance.

**Relationships**:
- One-to-many with `projects`: A project can have multiple temp QA pairs.
- One-to-one with `qa_pairs` (via `similar_qa_id`): Optional link to a similar finalized QA pair.

---

### **8. `datasets` Table**
**Purpose**: Stores metadata about datasets associated with a project, likely for machine learning purposes.

| Column Name    | Data Type | Constraints                          | Description                                                                 |
|----------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `dataset_id`   | INTEGER   | PRIMARY KEY AUTOINCREMENT            | Unique identifier for each dataset, automatically incremented.             |
| `project_id`   | INTEGER   | NOT NULL FOREIGN KEY (projects.project_id) | Links to a project; references `projects(project_id)`.               |
| `dataset_name` | TEXT      | NOT NULL                             | Name of the dataset, must be provided.                                     |
| `file_path`    | TEXT      | NOT NULL                             | File system path where the dataset is stored, cannot be null.              |
| `source_type`  | TEXT      | (None)                               | Type or source of the dataset (e.g., "call_transcripts"); can be null.     |
| `created_at`   | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP            | Date and time of creation, defaults to current time.                       |

**Key Features**:
- `dataset_id` is the primary key.
- `project_id` is a foreign key linking to `projects`.
- `dataset_name` and `file_path` are required for identification and access.
- `source_type` is optional, indicating the dataset’s origin.
- `created_at` tracks creation time.

**Relationships**:
- One-to-many with `projects`: A project can have multiple datasets.

---

### **9. `models` Table**
**Purpose**: Tracks models trained on datasets within a project, including links to temporary QA pairs used.

| Column Name    | Data Type | Constraints                          | Description                                                                 |
|----------------|-----------|--------------------------------------|-----------------------------------------------------------------------------|
| `model_id`     | INTEGER   | PRIMARY KEY AUTOINCREMENT            | Unique identifier for each model, automatically incremented.               |
| `project_id`   | INTEGER   | NOT NULL FOREIGN KEY (projects.project_id) | Links to a project; references `projects(project_id)`.               |
| `dataset_id`   | INTEGER   | NOT NULL FOREIGN KEY (datasets.dataset_id) | Links to a dataset; references `datasets(dataset_id)`.               |
| `model_name`   | TEXT      | NOT NULL                             | Name of the model, must be provided.                                       |
| `model_path`   | TEXT      | NOT NULL                             | File system path to the model file, cannot be null.                        |
| `model_type`   | TEXT      | NOT NULL                             | Type of model (e.g., "embedding", "qa"), must be provided.                 |
| `version`      | TEXT      | (None)                               | Version of the model (e.g., "v1.0"), optional.                             |
| `qa_temp_ids`  | TEXT      | (None)                               | JSON array of `qa_temp` IDs used in training; can be null.                 |
| `trained_at`   | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP            | Date and time when the model was trained, defaults to current time.        |

**Key Features**:
- `model_id` is the primary key.
- `project_id` and `dataset_id` are foreign keys linking to `projects` and `datasets`, respectively.
- `model_name`, `model_path`, and `model_type` are required for model identification and access.
- `version` is optional for tracking model iterations.
- `qa_temp_ids` stores a JSON string of `qa_temp` IDs, linking to training data.
- Indices on `project_id` and `dataset_id` enhance query performance.
- `trained_at` records training time.

**Relationships**:
- One-to-many with `projects`: A project can have multiple models.
- One-to-one with `datasets`: Each model is trained on one dataset.
- Indirect many-to-many with `qa_temp` (via `qa_temp_ids`).

---

### **Schema Overview and Relationships**
- **Root Table**: `users` is the entry point, linking to `projects`.
- **Central Hub**: `projects` connects to `documents`, `calls`, `utterances`, `qa_pairs`, `qa_temp`, `datasets`, and `models` via `project_id`.
- **Call Hierarchy**: `calls` → `utterances` and optionally `qa_pairs` via `call_id`.
- **QA Workflow**: `qa_temp` → `qa_pairs` (via `similar_qa_id` for similarity checks).
- **Model Training**: `datasets` → `models` via `dataset_id`, with `models` linking back to `qa_temp` via `qa_temp_ids`.