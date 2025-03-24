import os
from utils.db import AppDatabase

def initialize_database(clear=False):
    """Initialize the database if it doesn't exist, with an option to clear it."""
    db_path = "DB/retell.db"
    
    if clear:
        print("Clearing database...")
        AppDatabase.clear_database() # Use the clear_database method to properly remove the DB file
        AppDatabase.initialize(force_recreate=True) # Then initialize again

    elif not os.path.exists(db_path):
        print("Database not found. Initializing...")
        os.makedirs(os.path.dirname(db_path), exist_ok=True) # Make sure DB directory exists
        AppDatabase.initialize(force_recreate=True)

    else:
        print("Database found. No need to recreate tables.")
        os.makedirs(os.path.dirname(db_path), exist_ok=True) # Just ensure the directory exists, but don't recreate tables
        users = AppDatabase.list_users()
        print(f"Current users in database (username, email): {users}")

if __name__ == "__main__":
    initialize_database(clear=False)