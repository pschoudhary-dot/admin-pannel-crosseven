from passlib.hash import pbkdf2_sha256
from utils.db import AppDatabase

def hash_password(password):
    return pbkdf2_sha256.hash(password)

def verify_password(password, password_hash):
    return pbkdf2_sha256.verify(password, password_hash)

def signup(username, password, email=None):
    if not username or not password:
        print("Signup failed: Username or password is empty")
        return False
    exists = AppDatabase.user_exists(username)
    if exists:
        print(f"Signup failed: Username '{username}' already exists")
        return False
    success = AppDatabase.signup(username, hash_password(password), email)
    if success:
        print(f"Signup succeeded for '{username}'")
    else:
        print(f"Signup unexpectedly failed for '{username}' after user_exists check")
    return success

def signin(username, password):
    if not username or not password:
        print("Signin failed: Username or password is empty")
        return None
    user = AppDatabase.signin(username)
    if user and verify_password(password, user["password_hash"]):
        print(f"Signin successful for '{username}'")
        return user["user_id"]
    print(f"Signin failed for '{username}'")
    return None