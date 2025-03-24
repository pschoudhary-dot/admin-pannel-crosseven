import streamlit as st
from utils.db_manage import initialize_database
from utils.auth import signup, signin
from utils.db import AppDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize database (with option to clear via query param)
query_params = st.query_params
clear_db = query_params.get("clear_db", "false").lower() == "true"
initialize_database(clear=clear_db)

# Initialize session state variables if they don't exist
if "form_submitted" not in st.session_state:
    st.session_state.form_submitted = False

# Streamlit app
if "user_id" not in st.session_state:
    st.title("Admin Panel")
    tab1, tab2 = st.tabs(["Sign In", "Sign Up"])
    
    with tab1:
        st.header("Sign In")
        signin_username = st.text_input("Username", key="signin_username")
        signin_password = st.text_input("Password", type="password", key="signin_password")
        if st.button("Sign In", key="signin_button"):
            user_id = signin(signin_username, signin_password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.username = signin_username
                st.success(f"Sign in successful! Welcome, {signin_username}")
                st.rerun()
            else:
                if not AppDatabase.user_exists(signin_username):
                    st.error("Sign in failed: Account does not exist. Please sign up first.")
                else:
                    st.error("Sign in failed: Invalid password")
    
    with tab2:
        st.header("Sign Up")
        if st.session_state.form_submitted:
            st.session_state.form_submitted = False
            signup_username = st.text_input("Username", key="signup_username", value="")
            signup_password = st.text_input("Password", type="password", key="signup_password", value="")
            signup_email = st.text_input("Email (optional)", key="signup_email", value="")
        else:
            signup_username = st.text_input("Username", key="signup_username")
            signup_password = st.text_input("Password", type="password", key="signup_password")
            signup_email = st.text_input("Email (optional)", key="signup_email")
        
        if st.button("Sign Up", key="signup_button"):
            if not signup_username or not signup_password:
                st.error("Sign up failed: Username and password are required.")
            else:
                success = signup(signup_username, signup_password, signup_email)
                if success:
                    st.success(f"Sign up successful! Account created for {signup_username}. Please sign in.")
                    st.session_state.form_submitted = True
                    st.rerun()
                else:
                    st.error("Sign up failed: Username already exists.")
else:
    username = st.session_state.username
    st.title(f"Welcome, {username}")
    
    user_id = st.session_state.user_id
    projects = AppDatabase.get_user_projects(user_id)
    
    # Always show project management options
    st.subheader("Your Projects")
    
    if not projects:
        st.write("No projects found yet.")
    else:
        project_options = {p["project_name"]: p["project_id"] for p in projects}
        selected_project = st.selectbox("Select a Project", list(project_options.keys()))
        if st.button("Select Project"):
            st.session_state.project_id = project_options[selected_project]
            st.session_state.project_name = selected_project
            st.success(f"Project '{selected_project}' selected successfully!")
            st.rerun()
    
    # Create New Project section
    st.write("---")
    st.subheader("Create a New Project")
    new_project_name = st.text_input("Project Name", key="new_project_name")
    new_project_desc = st.text_area("Project Description (optional)", key="new_project_desc")
    if st.button("Create New Project", key="create_project_button"):
        if not new_project_name:
            st.error("Unable to create project: Project name is required.")
        else:
            project_id = AppDatabase.create_project(user_id, new_project_name, new_project_desc)
            if project_id:
                st.session_state.show_project_success = True
                st.session_state.created_project_name = new_project_name
                st.rerun()
            else:
                st.error(f"Unable to create project: '{new_project_name}' already exists for this user. Please choose a different name.")
    
    # Display success message and guide user to select the newly created project
    if st.session_state.get("show_project_success", False):
        st.success(f"Project '{st.session_state.created_project_name}' created successfully!")
        st.info("Please select your new project from the dropdown above and click 'Select Project' to start working with it.")
        # Clear the flag after showing the message
        st.session_state.show_project_success = False
    
    if st.button("Sign Out"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Signed out successfully!")
        st.rerun()

# Sidebar navigation when a project is selected
if "project_id" in st.session_state:
    st.sidebar.write(f"Current Project: {st.session_state.project_name} (ID: {st.session_state.project_id})")
    st.sidebar.write("Navigate to other pages:")