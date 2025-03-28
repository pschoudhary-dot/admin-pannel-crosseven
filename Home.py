import streamlit as st
from utils.db_manage import initialize_database
from utils.auth import signup, signin
from utils.db import AppDatabase, get_db_connection
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Wellnesswag Admin Panel", layout="wide", initial_sidebar_state="expanded")

query_params = st.query_params
clear_db = query_params.get("clear_db", "false").lower() == "true"
initialize_database(clear=clear_db)

if "form_submitted" not in st.session_state:
    st.session_state.form_submitted = False

if "user_id" not in st.session_state:
    
    auth_container = st.container()
    with auth_container:
        col_logo, col_title, col_space = st.columns([1, 2, 1])
        with col_title:
            st.markdown("<h1 class='main-header'>Wellnesswag Admin Panel</h1>", unsafe_allow_html=True)
        
        # Create a centered authentication form with improved styling
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container():
                st.markdown("<div class='auth-card'>", unsafe_allow_html=True)
                tab1, tab2 = st.tabs(["📝 Sign In", "✨ Sign Up"])
                
                with tab1:
                    with st.container():
                        st.markdown("### Welcome Back")
                        st.markdown("Please enter your credentials to continue")
                        signin_username = st.text_input("Username", key="signin_username", placeholder="Enter your username")
                        signin_password = st.text_input("Password", type="password", key="signin_password", placeholder="Enter your password")
                        signin_col1, signin_col2 = st.columns([3, 1])
                        with signin_col1:
                            if st.button("Sign In", key="signin_button", use_container_width=True, type="primary"):
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
                    with st.container():
                        st.markdown("### Create Account")
                        st.markdown("Join Wellnesswag Admin to manage your projects")
                        if st.session_state.form_submitted:
                            st.session_state.form_submitted = False
                            signup_username = st.text_input("Username", key="signup_username", value="", placeholder="Choose a username")
                            signup_password = st.text_input("Password", type="password", key="signup_password", value="", placeholder="Create a password")
                            signup_email = st.text_input("Email (optional)", key="signup_email", value="", placeholder="Enter your email")
                        else:
                            signup_username = st.text_input("Username", key="signup_username", placeholder="Choose a username")
                            signup_password = st.text_input("Password", type="password", key="signup_password", placeholder="Create a password")
                            signup_email = st.text_input("Email (optional)", key="signup_email", placeholder="Enter your email")
                        
                        signup_col1, signup_col2 = st.columns([3, 1])
                        with signup_col1:
                            if st.button("Sign Up", key="signup_button", use_container_width=True, type="primary"):
                                if not signup_username or not signup_password:
                                    st.error("Sign up failed: Username and password are required.")
                                else:
                                    success = signup(signup_username, signup_password, signup_email)
                                    if success:
                                        st.success(f"Sign up successful! Account created for {signup_username}. Please sign in.")
                                        st.session_state.form_submitted = True
                                    else:
                                        st.error("Sign up failed: Username already exists.")
                st.markdown("</div>", unsafe_allow_html=True)
        
        # Add footer with improved styling
        st.markdown("<div style='text-align: center; margin-top: 2rem;'>", unsafe_allow_html=True)
        # st.caption("© 2023 Wellnesswag. All rights reserved.")
        st.markdown("</div>", unsafe_allow_html=True)
else:
    
    username = st.session_state.username
    user_id = st.session_state.user_id
    projects = AppDatabase.get_user_projects(user_id)
    
    # Dashboard Header
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown(f"<div class='dashboard-header'><h1>Welcome, {username}</h1><p>Manage your projects and team members from this dashboard</p></div>", unsafe_allow_html=True)
    with header_col2:
        st.markdown("<div style='height: 3.5rem;'></div>", unsafe_allow_html=True)
        if st.button("Sign Out", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Signed out successfully!")
            st.rerun()
    
    # Project Management Section
    st.markdown("<h2>Project Management</h2>", unsafe_allow_html=True)
    
    # Projects Overview Card
    with st.container():
        st.markdown("<div class='card-container'>", unsafe_allow_html=True)
        if not projects:
            st.info("No projects found yet. Create your first project below.")
        else:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.metric("Total Projects", len(projects))
            with col2:
                st.markdown("<p>Your projects are listed below. Select one to manage its details and users.</p>", unsafe_allow_html=True)
            
            st.markdown("<div class='dataframe-container'>", unsafe_allow_html=True)
            project_data = [{"Project Name": p["project_name"], "Project ID": p["project_id"], "Role": p["role"]} for p in projects]
            st.dataframe(project_data, use_container_width=True, height=150)
            st.markdown("</div>", unsafe_allow_html=True)

            # Project Selection and Management
            project_options = {p["project_name"]: p["project_id"] for p in projects}
            selected_project_name = st.selectbox("Select a Project to Manage", list(project_options.keys()), key="manage_project")
            selected_project_id = project_options[selected_project_name]

            # Project Actions with improved layout
            action_col1, action_col2, action_col3 = st.columns(3)
            with action_col1:
                if st.button("Select Project", key="select_project", type="primary", use_container_width=True):
                    st.session_state.project_id = selected_project_id
                    st.session_state.project_name = selected_project_name
                    st.success(f"Project '{selected_project_name}' selected successfully!")
                    st.rerun()
            
            with action_col2:
                new_name = st.text_input("Rename Project", value=selected_project_name, key=f"rename_{selected_project_id}")
                if st.button("Rename", key=f"rename_btn_{selected_project_id}", use_container_width=True) and new_name != selected_project_name:
                    if AppDatabase.rename_project(selected_project_id, new_name):
                        st.success(f"Project renamed to '{new_name}'!")
                        if "project_id" in st.session_state and st.session_state.project_id == selected_project_id:
                            st.session_state.project_name = new_name
                        st.rerun()
                    else:
                        st.error("Failed to rename project.")
            
            with action_col3:
                st.text_input("Delete Confirmation", value="", key="delete_confirmation", label_visibility="collapsed", placeholder="Type 'delete' to confirm")
                delete_confirmation = st.session_state.get("delete_confirmation", "")
                delete_button = st.button("Delete Project", key=f"delete_{selected_project_id}", use_container_width=True, type="secondary")
                if delete_button:
                    if delete_confirmation.lower() == "delete":
                        if AppDatabase.delete_project(selected_project_id):
                            st.success(f"Project '{selected_project_name}' deleted successfully!")
                            if "project_id" in st.session_state and st.session_state.project_id == selected_project_id:
                                del st.session_state.project_id
                                del st.session_state.project_name
                            st.rerun()
                        else:
                            st.error("Failed to delete project.")
                    else:
                        st.warning("Type 'delete' in the field above to confirm deletion.")

            # User Management Card
            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            st.markdown(f"<h3>Manage Users for '{selected_project_name}'</h3>", unsafe_allow_html=True)
            
            with st.container():
                st.markdown("<div class='card-container'>", unsafe_allow_html=True)
                current_users = AppDatabase.get_project_users(selected_project_id)
                
                if not current_users:
                    st.info("No users assigned to this project yet.")
                else:
                    st.markdown("<p>Current team members and their roles:</p>", unsafe_allow_html=True)
                    st.markdown("<div class='dataframe-container'>", unsafe_allow_html=True)
                    user_data = [{"Username": u["username"], "Role": u["role"]} for u in current_users]
                    st.dataframe(user_data, use_container_width=True, height=150)
                    st.markdown("</div>", unsafe_allow_html=True)

                # User Management Actions
                user_col1, user_col2 = st.columns(2)
                
                with user_col1:
                    st.markdown("<p><strong>Add Team Member</strong></p>", unsafe_allow_html=True)
                    all_usernames = AppDatabase.get_all_usernames()
                    available_usernames = [u for u in all_usernames if u not in [cu["username"] for cu in current_users]]
                    if available_usernames:
                        assign_username = st.selectbox("Select User", available_usernames, key=f"assign_{selected_project_id}")
                        assign_role = st.selectbox("Assign Role", ["owner", "editor", "viewer"], key=f"role_{selected_project_id}")
                        if st.button("Add User", key=f"assign_btn_{selected_project_id}", use_container_width=True):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("SELECT user_id FROM users WHERE username = ?", (assign_username,))
                            assign_user_id = cursor.fetchone()["user_id"]
                            conn.close()
                            if AppDatabase.assign_user_to_project(selected_project_id, assign_user_id, assign_role):
                                st.success(f"User '{assign_username}' assigned as '{assign_role}' to '{selected_project_name}'!")
                                st.rerun()
                            else:
                                st.error("Failed to assign user.")
                    else:
                        st.info("No additional users available to assign.")
                
                with user_col2:
                    st.markdown("<p><strong>Remove Team Member</strong></p>", unsafe_allow_html=True)
                    if len(current_users) > 1:  # Prevent removing the last user
                        remove_username = st.selectbox("Select User", [u["username"] for u in current_users if u["user_id"] != user_id], 
                                                key=f"remove_{selected_project_id}")
                        if st.button("Remove User", key=f"remove_btn_{selected_project_id}", use_container_width=True):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("SELECT user_id FROM users WHERE username = ?", (remove_username,))
                            remove_user_id = cursor.fetchone()["user_id"]
                            conn.close()
                            if remove_user_id == user_id:
                                st.error("You cannot remove yourself from the project here.")
                            elif AppDatabase.remove_user_from_project(selected_project_id, remove_user_id):
                                st.success(f"User '{remove_username}' removed from '{selected_project_name}'!")
                                st.rerun()
                            else:
                                st.error("Failed to remove user.")
                    else:
                        st.info("Cannot remove users: At least one user must remain assigned.")
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Create New Project Section with card styling
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.markdown("<h2>Create a New Project</h2>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("<div class='card-container'>", unsafe_allow_html=True)
        create_col1, create_col2 = st.columns([3, 1])
        with create_col1:
            new_project_name = st.text_input("Project Name", key="new_project_name", placeholder="Enter project name")
            new_project_desc = st.text_area("Project Description (optional)", key="new_project_desc", placeholder="Describe your project")
        with create_col2:
            st.markdown("<div style='height: 4.7rem;'></div>", unsafe_allow_html=True)
            if st.button("Create Project", key="create_project_button", use_container_width=True, type="primary"):
                if not new_project_name:
                    st.error("Unable to create project: Project name is required.")
                else:
                    project_id = AppDatabase.create_project(user_id, new_project_name, new_project_desc)
                    if project_id:
                        st.session_state.show_project_success = True
                        st.session_state.created_project_name = new_project_name
                        st.rerun()
                    else:
                        st.error("Unable to create project: An error occurred.")
        st.markdown("</div>", unsafe_allow_html=True)
    
    if st.session_state.get("show_project_success", False):
        st.success(f"Project '{st.session_state.created_project_name}' created successfully!")
        st.info("Select your new project from the list above to manage it.")
        st.session_state.show_project_success = False
    
    if st.button("Sign Out", key="signout_button"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Signed out successfully!")
        st.rerun()

if "project_id" in st.session_state:
    st.sidebar.markdown("### Current Project")
    st.sidebar.markdown(f"**Name:** {st.session_state.project_name}")
    st.sidebar.markdown(f"**ID:** {st.session_state.project_id}")
    st.sidebar.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
    if st.sidebar.button("Change Project", use_container_width=True):
        # Keep user logged in but clear project selection
        if "project_id" in st.session_state:
            del st.session_state.project_id
        if "project_name" in st.session_state:
            del st.session_state.project_name
        st.rerun()
    st.sidebar.markdown("</div>", unsafe_allow_html=True)