import streamlit as st
from utils.db_manage import initialize_database
from utils.auth import signup, signin
from utils.db import AppDatabase, get_db_connection
from dotenv import load_dotenv
import os

# Load custom CSS
with open(os.path.join(os.path.dirname(__file__), 'style.css')) as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_dotenv()

query_params = st.query_params
clear_db = query_params.get("clear_db", "false").lower() == "true"
initialize_database(clear=clear_db)

if "form_submitted" not in st.session_state:
    st.session_state.form_submitted = False

if "user_id" not in st.session_state:
    st.markdown("<h1 style='text-align: center; margin-bottom: 2rem;'>Wellnesswag Admin Panel</h1>", unsafe_allow_html=True)
    
    # Create a container with card styling
    auth_container = st.container()
    with auth_container:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Sign In", "Sign Up"])
    
    with tab1:
        st.markdown("<h3 style='text-align: center; margin-bottom: 1.5rem;'>Sign In</h3>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            signin_username = st.text_input("Username", key="signin_username")
            signin_password = st.text_input("Password", type="password", key="signin_password")
            if st.button("Sign In", key="signin_button", use_container_width=True):
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
        st.markdown("<h3 style='text-align: center; margin-bottom: 1.5rem;'>Sign Up</h3>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.session_state.form_submitted:
                st.session_state.form_submitted = False
                signup_username = st.text_input("Username", key="signup_username", value="")
                signup_password = st.text_input("Password", type="password", key="signup_password", value="")
                signup_email = st.text_input("Email (optional)", key="signup_email", value="")
            else:
                signup_username = st.text_input("Username", key="signup_username")
                signup_password = st.text_input("Password", type="password", key="signup_password")
                signup_email = st.text_input("Email (optional)", key="signup_email")
            
            if st.button("Sign Up", key="signup_button", use_container_width=True):
            if not signup_username or not signup_password:
                st.error("Sign up failed: Username and password are required.")
            else:
                success = signup(signup_username, signup_password, signup_email)
                if success:
                    st.success(f"Sign up successful! Account created for {signup_username}. Please sign in.")
                    st.session_state.form_submitted = True
                else:
                    st.error("Sign up failed: Username already exists.")
    # Close the card div
    st.markdown("</div>", unsafe_allow_html=True)
else:
    # Dashboard for logged-in users
    username = st.session_state.username
    
    # Header with welcome message and user info
    st.markdown(f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;'>"
                f"<h1>Welcome, {username}</h1>"
                f"<div class='secondary-btn'>{st.button('Sign Out', key='signout_btn')}</div>"
                f"</div>", unsafe_allow_html=True)
    
    user_id = st.session_state.user_id
    projects = AppDatabase.get_user_projects(user_id)
    
    # Project Management Section in a card
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-header'>Project Management</div>", unsafe_allow_html=True)
    
    if not projects:
        st.markdown("<div class='info-box'>No projects found yet. Create your first project below!</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='margin-bottom: 1rem;'>You have access to <b>{len(projects)}</b> project(s).</div>", unsafe_allow_html=True)
        
        # Enhanced dataframe with better styling
        project_data = [{"Project Name": p["project_name"], "Project ID": p["project_id"], "Role": p["role"]} for p in projects]
        st.dataframe(project_data, use_container_width=True, height=150)

        # Select project for detailed management
        project_options = {p["project_name"]: p["project_id"] for p in projects}
        selected_project_name = st.selectbox("Select a Project to Manage", list(project_options.keys()), key="manage_project")
        selected_project_id = project_options[selected_project_name]

        # Project Actions with better layout and styling
        st.markdown("<div style='background-color: #f9f9f9; padding: 1rem; border-radius: 8px; margin: 1rem 0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-weight: 600; margin-bottom: 0.5rem;'>Project Actions</div>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Select Project", key="select_project", use_container_width=True):
                st.session_state.project_id = selected_project_id
                st.session_state.project_name = selected_project_name
                st.markdown(f"<div class='success-msg'>Project '{selected_project_name}' selected successfully!</div>", unsafe_allow_html=True)
                st.rerun()
        
        with col2:
            new_name = st.text_input("Rename Project", value=selected_project_name, key=f"rename_{selected_project_id}")
            if st.button("Rename", key=f"rename_btn_{selected_project_id}", use_container_width=True) and new_name != selected_project_name:
                if AppDatabase.rename_project(selected_project_id, new_name):
                    st.markdown(f"<div class='success-msg'>Project renamed to '{new_name}'!</div>", unsafe_allow_html=True)
                    if "project_id" in st.session_state and st.session_state.project_id == selected_project_id:
                        st.session_state.project_name = new_name
                    st.rerun()
                else:
                    st.markdown("<div class='error-msg'>Failed to rename project.</div>", unsafe_allow_html=True)
        
        with col3:
            st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
            if st.button("Delete Project", key=f"delete_{selected_project_id}", use_container_width=True):
                if AppDatabase.delete_project(selected_project_id):
                    st.markdown(f"<div class='success-msg'>Project '{selected_project_name}' deleted successfully!</div>", unsafe_allow_html=True)
                    if "project_id" in st.session_state and st.session_state.project_id == selected_project_id:
                        del st.session_state.project_id
                        del st.session_state.project_name
                    st.rerun()
                else:
                    st.markdown("<div class='error-msg'>Failed to delete project.</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Manage Project Users section with card styling
        st.markdown("<div class='section-divider'><span>User Management</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='card-header'>Manage Users for '{selected_project_name}'</div>", unsafe_allow_html=True)
        current_users = AppDatabase.get_project_users(selected_project_id)
        
        if not current_users:
            st.markdown("<div class='info-box'>No users assigned to this project yet.</div>", unsafe_allow_html=True)
        else:
            user_data = [{"Username": u["username"], "Role": u["role"]} for u in current_users]
            st.dataframe(user_data, use_container_width=True, height=150)

        # Assign User with better layout
        st.markdown("<div style='background-color: #f9f9f9; padding: 1rem; border-radius: 8px; margin: 1rem 0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-weight: 600; margin-bottom: 0.5rem;'>Add User to Project</div>", unsafe_allow_html=True)
        
        all_usernames = AppDatabase.get_all_usernames()
        available_usernames = [u for u in all_usernames if u not in [cu["username"] for cu in current_users]]
        if available_usernames:
            col1, col2 = st.columns(2)
            with col1:
                assign_username = st.selectbox("Select User", available_usernames, key=f"assign_{selected_project_id}")
            with col2:
                assign_role = st.selectbox("Assign Role", ["owner", "editor", "viewer"], key=f"role_{selected_project_id}")
            
            if st.button("Assign User", key=f"assign_btn_{selected_project_id}", use_container_width=True):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE username = ?", (assign_username,))
                assign_user_id = cursor.fetchone()["user_id"]
                conn.close()
                if AppDatabase.assign_user_to_project(selected_project_id, assign_user_id, assign_role):
                    st.markdown(f"<div class='success-msg'>User '{assign_username}' assigned as '{assign_role}' to '{selected_project_name}'!</div>", unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown("<div class='error-msg'>Failed to assign user.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='info-box'>No additional users available to assign.</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Remove User with better styling
        if len(current_users) > 1:  # Prevent removing the last user
            st.markdown("<div style='background-color: #f9f9f9; padding: 1rem; border-radius: 8px; margin: 1rem 0;'>", unsafe_allow_html=True)
            st.markdown("<div style='font-weight: 600; margin-bottom: 0.5rem;'>Remove User from Project</div>", unsafe_allow_html=True)
            
            remove_username = st.selectbox("Select User to Remove", [u["username"] for u in current_users if u["user_id"] != user_id], 
                                         key=f"remove_{selected_project_id}")
            
            st.markdown("<div class='danger-btn'>", unsafe_allow_html=True)
            if st.button("Remove User", key=f"remove_btn_{selected_project_id}", use_container_width=True):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE username = ?", (remove_username,))
                remove_user_id = cursor.fetchone()["user_id"]
                conn.close()
                if remove_user_id == user_id:
                    st.markdown("<div class='error-msg'>You cannot remove yourself from the project here.</div>", unsafe_allow_html=True)
                elif AppDatabase.remove_user_from_project(selected_project_id, remove_user_id):
                    st.markdown(f"<div class='success-msg'>User '{remove_username}' removed from '{selected_project_name}'!</div>", unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown("<div class='error-msg'>Failed to remove user.</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='info-box'>Cannot remove users: At least one user must remain assigned.</div>", unsafe_allow_html=True)

    # Close the project management card
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Create New Project Section with card styling
    st.markdown("<div class='section-divider'><span>Create New Project</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-header'>Create a New Project</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        new_project_name = st.text_input("Project Name", key="new_project_name", placeholder="Enter project name")
    
    new_project_desc = st.text_area("Project Description (optional)", key="new_project_desc", placeholder="Describe your project here...")
    
    if st.button("Create New Project", key="create_project_button", use_container_width=True):
        if not new_project_name:
            st.markdown("<div class='error-msg'>Unable to create project: Project name is required.</div>", unsafe_allow_html=True)
        else:
            project_id = AppDatabase.create_project(user_id, new_project_name, new_project_desc)
            if project_id:
                st.session_state.show_project_success = True
                st.session_state.created_project_name = new_project_name
                st.rerun()
            else:
                st.markdown("<div class='error-msg'>Unable to create project: An error occurred.</div>", unsafe_allow_html=True)
    
    if st.session_state.get("show_project_success", False):
        st.markdown(f"<div class='success-msg'>Project '{st.session_state.created_project_name}' created successfully!</div>", unsafe_allow_html=True)
        st.markdown("<div class='info-box'>Select your new project from the list above to manage it.</div>", unsafe_allow_html=True)
        st.session_state.show_project_success = False
    
    # Close the create project card
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Sign out button is moved to the top of the page in the header

# Handle sign out button click
if st.session_state.get('signout_btn', False):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.success("Signed out successfully!")
    st.rerun()

# Enhanced sidebar with better styling
if "project_id" in st.session_state:
    st.sidebar.markdown(f"<div style='background-color: rgba(76, 175, 80, 0.1); padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>"
                      f"<div style='font-weight: 600; margin-bottom: 0.5rem;'>Current Project</div>"
                      f"<div>{st.session_state.project_name}</div>"
                      f"<div style='font-size: 0.8rem; color: #666;'>ID: {st.session_state.project_id}</div>"
                      f"</div>", unsafe_allow_html=True)