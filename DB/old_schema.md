### **1. `users` Table**
**Purpose**: Stores information about registered users of the application, such as their credentials and basic details.

| Column Name    | Data Type       | Constraints                          | Description                                                                 |
|----------------|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `user_id`      | INTEGER         | PRIMARY KEY AUTOINCREMENT            | A unique identifier for each user, automatically incremented by SQLite.    |
| `username`     | TEXT            | UNIQUE NOT NULL                      | The username chosen by the user, must be unique and cannot be null.        |
| `password_hash`| TEXT            | NOT NULL                             | The hashed password for secure storage, cannot be null.                    |
| `email`        | TEXT            | (None)                               | An optional email address for the user; can be null.                       |
| `created_at`   | TIMESTAMP       | DEFAULT CURRENT_TIMESTAMP            | The date and time when the user account was created, defaults to now.      |

**Key Features**:
- The `user_id` is the primary key, ensuring each user has a unique identifier.
- The `username` is unique to prevent duplicate accounts with the same name.
- The `password_hash` stores a hashed version of the password (using `pbkdf2_sha256` from the `auth.py` file) for security.
- The `email` field is optional, allowing users to sign up without providing it.

---

### **2. `projects` Table**
**Purpose**: Represents projects created by users, allowing them to organize their work (e.g., calls, documents, QA pairs).

| Column Name    | Data Type       | Constraints                          | Description                                                                 |
|----------------|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `project_id`   | INTEGER         | PRIMARY KEY AUTOINCREMENT            | A unique identifier for each project, automatically incremented.           |
| `user_id`      | INTEGER         | NOT NULL FOREIGN KEY (users.user_id) | Links the project to a specific user; references `users(user_id)`.         |
| `project_name` | TEXT            | NOT NULL                             | The name of the project, must be provided.                                 |
| `description`  | TEXT            | (None)                               | An optional description of the project; can be null.                       |
| `created_at`   | TIMESTAMP       | DEFAULT CURRENT_TIMESTAMP            | The date and time when the project was created, defaults to now.           |

**Key Features**:
- The `project_id` is the primary key.
- The `user_id` is a foreign key linking to the `users` table, ensuring every project belongs to a user.
- A unique constraint exists on the combination of `user_id` and `project_name`, preventing a user from creating multiple projects with the same name.

**Relationships**:
- One user (from `users`) can have many projects (one-to-many).

---

### **3. `documents` Table**
**Purpose**: Stores metadata about files uploaded to a project, such as transcripts or other supporting documents.

| Column Name    | Data Type       | Constraints                          | Description                                                                 |
|----------------|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `document_id`  | INTEGER         | PRIMARY KEY AUTOINCREMENT            | A unique identifier for each document, automatically incremented.          |
| `project_id`   | INTEGER         | NOT NULL FOREIGN KEY (projects.project_id) | Links the document to a specific project; references `projects(project_id)`. |
| `file_name`    | TEXT            | NOT NULL                             | The name of the uploaded file, cannot be null.                             |
| `file_path`    | TEXT            | NOT NULL                             | The file system path where the document is stored, cannot be null.         |
| `file_type`    | TEXT            | (None)                               | The type of file (e.g., "txt", "pdf"), optional and can be null.           |
| `uploaded_at`  | TIMESTAMP       | DEFAULT CURRENT_TIMESTAMP            | The date and time when the document was uploaded, defaults to now.         |

**Key Features**:
- The `document_id` is the primary key.
- The `project_id` is a foreign key linking to the `projects` table, associating each document with a project.
- Both `file_name` and `file_path` are required to ensure proper tracking of uploaded files.

**Relationships**:
- One project (from `projects`) can have many documents (one-to-many).

---

### **4. `calls` Table**
**Purpose**: Stores call data, including transcripts, associated with a project.

| Column Name    | Data Type       | Constraints                          | Description                                                                 |
|----------------|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `call_id`      | TEXT            | PRIMARY KEY                          | A unique identifier for each call (e.g., a call ID from an external system).|
| `project_id`   | INTEGER         | NOT NULL FOREIGN KEY (projects.project_id) | Links the call to a specific project; references `projects(project_id)`. |
| `transcript`   | TEXT            | (None)                               | The transcript of the call; can be null if no transcript is available.     |
| `timestamp`    | TIMESTAMP       | DEFAULT CURRENT_TIMESTAMP            | The date and time when the call was stored, defaults to now.               |

**Key Features**:
- The `call_id` is the primary key and uses `TEXT` instead of `INTEGER`, suggesting it might be an external identifier (e.g., a string ID from a telephony system).
- The `project_id` is a foreign key linking to the `projects` table.
- The `transcript` field is optional, allowing calls to be stored even if transcription is incomplete or unavailable.

**Relationships**:
- One project (from `projects`) can have many calls (one-to-many).

---

### **5. `utterances` Table**
**Purpose**: Breaks down call transcripts into individual utterances (e.g., spoken lines by different roles like "agent" or "customer").

| Column Name      | Data Type       | Constraints                          | Description                                                                 |
|------------------|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `id`             | INTEGER         | PRIMARY KEY AUTOINCREMENT            | A unique identifier for each utterance, automatically incremented.         |
| `call_id`        | TEXT            | FOREIGN KEY (calls.call_id)          | Links the utterance to a specific call; references `calls(call_id)`.       |
| `project_id`     | INTEGER         | NOT NULL FOREIGN KEY (projects.project_id) | Links the utterance to a specific project; references `projects(project_id)`. |
| `role`           | TEXT            | (None)                               | The role of the speaker (e.g., "agent", "customer"); can be null.          |
| `content`        | TEXT            | (None)                               | The text of the utterance; can be null.                                    |
| `utterance_index`| INTEGER         | (None)                               | The order of the utterance within the call; can be null.                   |

**Key Features**:
- The `id` is the primary key.
- The `call_id` is a foreign key linking to the `calls` table, associating each utterance with a specific call.
- The `project_id` is a foreign key linking to the `projects` table, providing an additional layer of association (though it’s redundant with `call_id` due to the `calls` table already linking to `projects`).
- Fields like `role`, `content`, and `utterance_index` are optional, allowing flexibility in how utterances are stored.

**Relationships**:
- One call (from `calls`) can have many utterances (one-to-many).
- One project (from `projects`) can have many utterances (one-to-many).

---

### **6. `qa_pairs` Table**
**Purpose**: Stores question-answer pairs generated from calls or other sources, useful for training chatbots or documenting FAQs.

| Column Name    | Data Type       | Constraints                          | Description                                                                 |
|----------------|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `id`           | INTEGER         | PRIMARY KEY AUTOINCREMENT            | A unique identifier for each QA pair, automatically incremented.           |
| `project_id`   | INTEGER         | NOT NULL FOREIGN KEY (projects.project_id) | Links the QA pair to a specific project; references `projects(project_id)`. |
| `call_id`      | TEXT            | FOREIGN KEY (calls.call_id)          | Links the QA pair to a specific call; references `calls(call_id)`, can be null. |
| `question`     | TEXT            | (None)                               | The question text; can be null but typically required by application logic.|
| `answer`       | TEXT            | (None)                               | The answer text; can be null but typically required by application logic.  |
| `created_at`   | TIMESTAMP       | DEFAULT CURRENT_TIMESTAMP            | The date and time when the QA pair was created, defaults to now.           |

**Key Features**:
- The `id` is the primary key.
- The `project_id` is a foreign key linking to the `projects` table, ensuring each QA pair belongs to a project.
- The `call_id` is a foreign key linking to the `calls` table but is optional (can be null), allowing QA pairs to be stored independently of calls.
- `question` and `answer` are technically nullable in the schema, but application logic (e.g., in `store_qa_pair`) enforces that they are provided.

**Relationships**:
- One project (from `projects`) can have many QA pairs (one-to-many).
- One call (from `calls`) can have many QA pairs (one-to-many), but this link is optional.

---

### **7. `datasets` Table**
**Purpose**: Stores metadata about datasets associated with a project, possibly for machine learning or data analysis purposes.

| Column Name    | Data Type       | Constraints                          | Description                                                                 |
|----------------|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `dataset_id`   | INTEGER         | PRIMARY KEY AUTOINCREMENT            | A unique identifier for each dataset, automatically incremented.           |
| `project_id`   | INTEGER         | NOT NULL FOREIGN KEY (projects.project_id) | Links the dataset to a specific project; references `projects(project_id)`. |
| `dataset_name` | TEXT            | NOT NULL                             | The name of the dataset, must be provided.                                 |
| `file_path`    | TEXT            | NOT NULL                             | The file system path where the dataset is stored, cannot be null.          |
| `source_type`  | TEXT            | (None)                               | The type or source of the dataset (e.g., "call_transcripts"); can be null. |
| `created_at`   | TIMESTAMP       | DEFAULT CURRENT_TIMESTAMP            | The date and time when the dataset was created, defaults to now.           |

**Key Features**:
- The `dataset_id` is the primary key.
- The `project_id` is a foreign key linking to the `projects` table.
- Both `dataset_name` and `file_path` are required to ensure proper identification and access to the dataset.

**Relationships**:
- One project (from `projects`) can have many datasets (one-to-many).

---

### **Schema Overview and Relationships**
Here’s a summary of how the tables connect:
- **`users`** → **`projects`**: A user can create multiple projects (one-to-many via `user_id`).
- **`projects`** → **`documents`**, **`calls`**, **`utterances`**, **`qa_pairs`**, **`datasets`**: Each project can have multiple associated documents, calls, utterances, QA pairs, and datasets (one-to-many via `project_id`).
- **`calls`** → **`utterances`**, **`qa_pairs`**: A call can have multiple utterances and QA pairs (one-to-many via `call_id`), though the `call_id` in `qa_pairs` is optional.

**Foreign Key Enforcement**:
- The `get_db_connection()` function in `db.py` enables `PRAGMA foreign_keys = ON`, ensuring that SQLite enforces these relationships (e.g., you can’t delete a user if they have projects).

**Redundancy Note**:
- The `project_id` in the `utterances` table is somewhat redundant since `call_id` already links to `calls`, which links to `projects`. This might be intentional for query optimization or flexibility.

---