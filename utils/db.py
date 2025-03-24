import sqlite3
import os

DB_PATH = "DB/retell.db"

def get_db_connection():
    """Return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
        # Ensure DB directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tables already exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone() is not None
        
        # Only recreate tables if they don't exist or if forced
        if force_recreate or not table_exists:
            print("Creating database tables...")
            
            # Create tables without dropping existing ones
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
        # Fix: Make sure empty email is stored as NULL, not as empty string
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
            return project_id
        except sqlite3.IntegrityError:
            return None
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
        return [(user["username"], user["email"]) for user in users]