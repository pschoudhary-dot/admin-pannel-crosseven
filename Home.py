import streamlit as st
from utils.db_manage import initialize_database
from utils.auth import signup, signin
from utils.db import AppDatabase, get_db_connection
from dotenv import load_dotenv

load_dotenv()

query_params = st.query_params
clear_db = query_params.get("clear_db", "false").lower() == "true"
initialize_database(clear=clear_db)

if "form_submitted" not in st.session_state:
    st.session_state.form_submitted = False

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
    
    # Project Management Section
    st.subheader("Project Management")
    
    if not projects:
        st.write("No projects found yet.")
    else:
        st.write(f"You have access to {len(projects)} project(s).")
        project_data = [{"Project Name": p["project_name"], "Project ID": p["project_id"], "Role": p["role"]} for p in projects]
        st.dataframe(project_data, use_container_width=True)

        # Select project for detailed management
        project_options = {p["project_name"]: p["project_id"] for p in projects}
        selected_project_name = st.selectbox("Select a Project to Manage", list(project_options.keys()), key="manage_project")
        selected_project_id = project_options[selected_project_name]

        # Project Actions
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Select Project", key="select_project"):
                st.session_state.project_id = selected_project_id
                st.session_state.project_name = selected_project_name
                st.success(f"Project '{selected_project_name}' selected successfully!")
                st.rerun()
        
        with col2:
            new_name = st.text_input("Rename Project", value=selected_project_name, key=f"rename_{selected_project_id}")
            if st.button("Rename", key=f"rename_btn_{selected_project_id}") and new_name != selected_project_name:
                if AppDatabase.rename_project(selected_project_id, new_name):
                    st.success(f"Project renamed to '{new_name}'!")
                    if "project_id" in st.session_state and st.session_state.project_id == selected_project_id:
                        st.session_state.project_name = new_name
                    st.rerun()
                else:
                    st.error("Failed to rename project.")
        
        with col3:
            if st.button("Delete Project", key=f"delete_{selected_project_id}"):
                if AppDatabase.delete_project(selected_project_id):
                    st.success(f"Project '{selected_project_name}' deleted successfully!")
                    if "project_id" in st.session_state and st.session_state.project_id == selected_project_id:
                        del st.session_state.project_id
                        del st.session_state.project_name
                    st.rerun()
                else:
                    st.error("Failed to delete project.")

        # Manage Project Users
        st.write("---")
        st.subheader(f"Manage Users for '{selected_project_name}'")
        current_users = AppDatabase.get_project_users(selected_project_id)
        
        if not current_users:
            st.write("No users assigned to this project yet.")
        else:
            user_data = [{"Username": u["username"], "Role": u["role"]} for u in current_users]
            st.dataframe(user_data, use_container_width=True)

        # Assign User
        all_usernames = AppDatabase.get_all_usernames()
        available_usernames = [u for u in all_usernames if u not in [cu["username"] for cu in current_users]]
        if available_usernames:
            assign_username = st.selectbox("Assign a User", available_usernames, key=f"assign_{selected_project_id}")
            assign_role = st.selectbox("Role", ["owner", "editor", "viewer"], key=f"role_{selected_project_id}")
            if st.button("Assign User", key=f"assign_btn_{selected_project_id}"):
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
            st.write("No additional users available to assign.")

        # Remove User
        if len(current_users) > 1:  # Prevent removing the last user
            remove_username = st.selectbox("Remove a User", [u["username"] for u in current_users if u["user_id"] != user_id], 
                                         key=f"remove_{selected_project_id}")
            if st.button("Remove User", key=f"remove_btn_{selected_project_id}"):
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
            st.write("Cannot remove users: At least one user must remain assigned.")

    # Create New Project Section
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
                st.error("Unable to create project: An error occurred.")
    
    if st.session_state.get("show_project_success", False):
        st.success(f"Project '{st.session_state.created_project_name}' created successfully!")
        st.info("Select your new project from the list above to manage it.")
        st.session_state.show_project_success = False
    
    if st.button("Sign Out"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Signed out successfully!")
        st.rerun()

if "project_id" in st.session_state:
    st.sidebar.write(f"Current Project: {st.session_state.project_name} (ID: {st.session_state.project_id})")