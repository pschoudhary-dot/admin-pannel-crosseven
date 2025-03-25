import sqlite3
import os

DB_PATH = "DB/retell.db"

def get_db_connection():
    """Return a database connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

class AppDatabase:
    """Extended database manager for the app."""
    
    @staticmethod
    def clear_database():
        """Clear the database by removing the file."""
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
                print(f"Database file '{DB_PATH}' removed successfully")
                return True
            except Exception as e:
                print(f"Error removing database file: {e}")
                return False
        else:
            print(f"Database file '{DB_PATH}' doesn't exist")
            return True
    
    @staticmethod
    def initialize(force_recreate=False):
        """Initialize all database tables."""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone() is not None
        
        if force_recreate or not table_exists:
            print("Creating database tables...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, project_name)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (project_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS calls (
                call_id TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL,
                transcript TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (project_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS utterances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT,
                project_id INTEGER NOT NULL,
                role TEXT,
                content TEXT,
                utterance_index INTEGER,
                FOREIGN KEY (call_id) REFERENCES calls (call_id),
                FOREIGN KEY (project_id) REFERENCES projects (project_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS qa_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                call_id TEXT,
                question TEXT,
                answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (call_id) REFERENCES calls (call_id),
                FOREIGN KEY (project_id) REFERENCES projects (project_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                dataset_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                source_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (project_id)
            )
            ''')
            
            print("All database tables initialized successfully")
        else:
            print("Tables already exist, skipping initialization")
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def user_exists(username):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        print(f"Checking if user '{username}' exists: {'True' if user else 'False'}")
        return user is not None
    
    @staticmethod
    def signup(username, password_hash, email=None):
        if email == "":
            email = None
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                          (username, password_hash, email))
            conn.commit()
            print(f"User '{username}' signed up successfully")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Signup failed for '{username}': {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def signin(username):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, password_hash FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    @staticmethod
    def get_user_projects(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT project_id, project_name FROM projects WHERE user_id = ?", (user_id,))
        projects = cursor.fetchall()
        conn.close()
        return projects
    
    @staticmethod
    def create_project(user_id, project_name, description=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO projects (user_id, project_name, description) VALUES (?, ?, ?)",
                          (user_id, project_name, description))
            project_id = cursor.lastrowid
            conn.commit()
            print(f"Project '{project_name}' created successfully for user_id {user_id}")
            return project_id
        except sqlite3.IntegrityError as e:
            print(f"Project creation failed for '{project_name}': {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def check_database_connection():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            fk_status = cursor.fetchone()[0]
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            cursor.execute("PRAGMA database_list")
            db_info = cursor.fetchall()
            conn.close()
            return True, {
                "SQLite Version": version,
                "Foreign Keys Enabled": bool(fk_status),
                "Database Path": db_info[0]['file'] if db_info else "Unknown"
            }
        except Exception as e:
            return False, f"Database connection error: {str(e)}"

    @staticmethod
    def store_qa_pair(project_id, question, answer, call_id=None):
        print(f"Attempting to store QA pair - Project ID: {project_id}, Call ID: {call_id}")
        print(f"Question: {question[:50]}...")
        print(f"Answer: {answer[:50]}...")
        
        if not question or not answer or not project_id:
            print("Missing required data for QA pair")
            return False

        # Normalize data
        try:
            project_id = int(project_id)
        except (ValueError, TypeError):
            print(f"Invalid project_id format: {project_id}")
            return False
            
        # Empty string call_id should be converted to None
        if call_id == "":
            call_id = None

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check foreign keys status
        cursor.execute("PRAGMA foreign_keys")
        fk_status = cursor.fetchone()[0]
        print(f"Foreign keys status: {'ON' if fk_status else 'OFF'}")
        
        try:
            # Validate project_id exists
            cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (project_id,))
            project = cursor.fetchone()
            if not project:
                print(f"Project ID {project_id} does not exist")
                conn.close()
                return False
            else:
                print(f"Project ID {project_id} validated successfully")

            # Validate call_id if provided - if not found, set to NULL to avoid FK constraint
            if call_id:
                cursor.execute("SELECT call_id FROM calls WHERE call_id = ? AND project_id = ?", (call_id, project_id))
                call = cursor.fetchone()
                if not call:
                    print(f"Warning: Call ID {call_id} does not exist for project {project_id}")
                    print("Setting call_id to NULL to avoid foreign key constraint failure")
                    call_id = None

            # Try without call_id first if provided and fails FK check
            try:
                print("About to execute INSERT statement")
                if call_id is None:
                    print("Executing with NULL call_id")
                    cursor.execute("""
                    INSERT INTO qa_pairs (project_id, call_id, question, answer) 
                    VALUES (?, NULL, ?, ?)
                    """, (project_id, question.strip(), answer.strip()))
                else:
                    print(f"Executing with call_id: {call_id}")
                    cursor.execute("""
                    INSERT INTO qa_pairs (project_id, call_id, question, answer) 
                    VALUES (?, ?, ?, ?)
                    """, (project_id, call_id, question.strip(), answer.strip()))
                
                print("About to commit transaction")
                conn.commit()
                print(f"QA pair stored successfully for project_id {project_id}, call_id {call_id}")
                return True
            except sqlite3.IntegrityError as e:
                # If fails with call_id, try without it
                if call_id is not None:
                    print(f"Insert failed with call_id, trying without: {str(e)}")
                    cursor.execute("""
                    INSERT INTO qa_pairs (project_id, call_id, question, answer) 
                    VALUES (?, NULL, ?, ?)
                    """, (project_id, question.strip(), answer.strip()))
                    conn.commit()
                    print("QA pair stored successfully without call_id reference")
                    return True
                else:
                    raise e
                    
        except sqlite3.IntegrityError as e:
            print(f"Failed to store QA pair due to IntegrityError: {e}")
            conn.rollback()
            return False
        except Exception as e:
            print(f"Unexpected error storing QA pair: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def get_username(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user["username"] if user else None
    
    @staticmethod
    def list_users():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, email FROM users")
        users = cursor.fetchall()
        conn.close()
        print(f"Listing users: {[(user['username'], user['email']) for user in users]}")
        return [(user["username"], user["email"]) for user in users]
    
    @staticmethod
    def store_call(project_id, call_id, transcript):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR REPLACE INTO calls (call_id, project_id, transcript) VALUES (?, ?, ?)",
                          (call_id, project_id, transcript))
            conn.commit()
            print(f"Call '{call_id}' stored successfully for project_id {project_id}")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Failed to store call '{call_id}': {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_call(project_id, call_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT call_id, transcript, timestamp FROM calls WHERE project_id = ? AND call_id = ?",
                      (project_id, call_id))
        call = cursor.fetchone()
        conn.close()
        return call
    
    @staticmethod
    def get_project_calls(project_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT call_id, transcript, timestamp FROM calls WHERE project_id = ?", (project_id,))
        calls = cursor.fetchall()
        conn.close()
        return calls
    
    @staticmethod
    def remove_call(project_id, call_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM calls WHERE project_id = ? AND call_id = ?", (project_id, call_id))
            if cursor.rowcount > 0:
                conn.commit()
                print(f"Call '{call_id}' removed successfully from project_id {project_id}")
                return True
            else:
                print(f"Call '{call_id}' not found in project_id {project_id}")
                return False
        except Exception as e:
            print(f"Failed to remove call '{call_id}': {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def store_document(project_id, file_name, file_path, file_type):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO documents (project_id, file_name, file_path, file_type) VALUES (?, ?, ?, ?)",
                          (project_id, file_name, file_path, file_type))
            conn.commit()
            print(f"Document '{file_name}' stored for project_id {project_id}")
            return True
        except sqlite3.IntegrityError as e:
            print(f"Failed to store document '{file_name}': {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_project_qa_pairs(project_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, call_id, question, answer, created_at FROM qa_pairs WHERE project_id = ?",
                      (project_id,))
        qa_pairs = cursor.fetchall()
        conn.close()
        return qa_pairs
    
    @staticmethod
    def remove_qa_pair(project_id, qa_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM qa_pairs WHERE project_id = ? AND id = ?", (project_id, qa_id))
            if cursor.rowcount > 0:
                conn.commit()
                print(f"QA pair {qa_id} removed from project_id {project_id}")
                return True
            else:
                print(f"QA pair {qa_id} not found in project_id {project_id}")
                return False
        except Exception as e:
            print(f"Failed to remove QA pair {qa_id}: {e}")
            return False
        finally:
            conn.close()