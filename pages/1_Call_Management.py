import streamlit as st
from utils.db import AppDatabase
from dotenv import load_dotenv
import os
import json
from retell import Retell
import pandas as pd

load_dotenv()

# Initialize Retell SDK client
retell_api_key = os.getenv("RETELL_API_KEY")
if not retell_api_key:
    st.error("RETELL_API_KEY not found in environment variables. Please set it in your .env file.")
    st.stop()
retell_client = Retell(api_key=retell_api_key)

st.title("Call Management")

# Check if user is signed in and project is selected
if "user_id" not in st.session_state or "project_id" not in st.session_state:
    st.error("Please sign in and select a project from the Admin Panel first.")
    st.stop()

username = st.session_state.username
project_id = st.session_state.project_id
project_name = st.session_state.project_name
st.write(f"Working on Project: {project_name} (ID: {project_id})")

# Sidebar navigation
st.sidebar.write(f"Current Project: {project_name} (ID: {project_id})")

# Tabs for Fetching and Viewing Calls
tab1, tab2, tab3, tab4 = st.tabs(["Fetch New Calls", "View Stored Calls", "Import Calls", "Export Calls"])

# Tab 1: Fetch New Calls from Retell SDK
with tab1:
    st.header("Fetch Call Transcripts")
    
    # Option to fetch all calls or a specific call ID
    fetch_option = st.radio("Fetch Options", ["Fetch All Successful Calls", "Fetch Specific Call ID"])
    
    if fetch_option == "Fetch Specific Call ID":
        call_id_input = st.text_input("Enter Call ID", key="call_id_input")
        if st.button("Fetch Transcript", key="fetch_single_button"):
            if not call_id_input:
                st.error("Please enter a Call ID.")
            else:
                # Check if call exists in database
                existing_call = AppDatabase.get_call(project_id, call_id_input)
                if existing_call and existing_call["transcript"]:
                    st.warning(f"Call ID '{call_id_input}' already exists in this project. View it in 'View Stored Calls' tab.")
                else:
                    try:
                        call_response = retell_client.call.retrieve(call_id=call_id_input)
                        transcript = getattr(call_response, "transcript", "No transcript available")
                        st.session_state.fetched_call = {"call_id": call_id_input, "transcript": transcript}
                        st.success(f"Transcript fetched for Call ID '{call_id_input}'!")
                    except Exception as e:
                        st.error(f"Failed to fetch transcript for Call ID '{call_id_input}': {str(e)}")
    
    elif fetch_option == "Fetch All Successful Calls":
        limit = st.number_input("Limit (max calls to fetch)", min_value=1, max_value=500, value=200, step=1)
        if st.button("Fetch All Transcripts", key="fetch_all_button"):
            existing_call_ids = set(call["call_id"] for call in AppDatabase.get_project_calls(project_id))
            filter_criteria = {
                "call_successful": [True],
                "in_voicemail": [False]
            }
            try:
                calls = retell_client.call.list(filter_criteria=filter_criteria, limit=limit)
                if not calls:
                    st.warning("No successful calls found in Retell.")
                else:
                    fetched_calls = []
                    for call in calls:
                        call_id = getattr(call, "call_id", None)
                        transcript = getattr(call, "transcript", "No transcript available")
                        if not call_id:
                            continue
                        if call_id in existing_call_ids:
                            continue  # Skip already stored calls
                        fetched_calls.append({"call_id": call_id, "transcript": transcript})
                    st.session_state.fetched_calls = fetched_calls
                    st.success(f"Fetched {len(fetched_calls)} new successful calls!")
            except Exception as e:
                st.error(f"Failed to fetch calls: {str(e)}")
    
    # Display and store fetched call(s)
    if "fetched_call" in st.session_state:
        st.subheader(f"Fetched Call: {st.session_state.fetched_call['call_id']}")
        st.text_area("Transcript", st.session_state.fetched_call["transcript"], height=200, key="single_transcript")
        if st.button("Store This Call", key="store_single_button"):
            success = AppDatabase.store_call(project_id, st.session_state.fetched_call["call_id"], 
                                           st.session_state.fetched_call["transcript"])
            if success:
                st.success(f"Call '{st.session_state.fetched_call['call_id']}' stored successfully in project '{project_name}'!")
                del st.session_state.fetched_call
                st.rerun()
            else:
                st.error(f"Failed to store Call '{st.session_state.fetched_call['call_id']}'. It may already exist.")
    
    elif "fetched_calls" in st.session_state:
        st.subheader("Fetched Calls")
        selected_calls = st.multiselect("Select Calls to Store", 
                                      [call["call_id"] for call in st.session_state.fetched_calls],
                                      key="select_calls")
        if st.button("Store Selected Calls", key="store_selected_button"):
            if not selected_calls:
                st.error("Please select at least one call to store.")
            else:
                stored_count = 0
                for call_id in selected_calls:
                    call = next(c for c in st.session_state.fetched_calls if c["call_id"] == call_id)
                    success = AppDatabase.store_call(project_id, call["call_id"], call["transcript"])
                    if success:
                        st.success(f"Call '{call['call_id']}' stored successfully in project '{project_name}'!")
                        stored_count += 1
                    else:
                        st.error(f"Failed to store Call '{call['call_id']}'. It may already exist.")
                if stored_count > 0:
                    del st.session_state.fetched_calls
                    st.rerun()
    
    # Display fetched calls for review
    if "fetched_calls" in st.session_state:
        for call in st.session_state.fetched_calls:
            with st.expander(f"Call ID: {call['call_id']}"):
                st.text_area("Transcript", call["transcript"], height=150, key=f"transcript_{call['call_id']}")

# Tab 2: View and Manage Stored Calls
with tab2:
    st.header("Stored Calls")
    stored_calls = AppDatabase.get_project_calls(project_id)
    
    if not stored_calls:
        st.write("No calls stored in this project yet.")
    else:
        st.write(f"Total stored calls: {len(stored_calls)}")
        call_id_to_view = st.selectbox("Select a Call ID to View", [call["call_id"] for call in stored_calls],
                                      key="view_call_select")
        if call_id_to_view:
            call = AppDatabase.get_call(project_id, call_id_to_view)
            if call:
                st.subheader(f"Call ID: {call['call_id']}")
                st.text_area("Stored Transcript", call["transcript"], height=200, key="stored_transcript")
                st.write(f"Stored on: {call['timestamp']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Remove Call", key=f"remove_{call['call_id']}"):
                        success = AppDatabase.remove_call(project_id, call["call_id"])
                        if success:
                            st.success(f"Call '{call['call_id']}' removed successfully!")
                            st.rerun()
                        else:
                            st.error(f"Failed to remove Call '{call['call_id']}'.")
                with col2:
                    if st.button("Update with New Fetch", key=f"update_{call['call_id']}"):
                        try:
                            call_response = retell_client.call.retrieve(call_id=call["call_id"])
                            new_transcript = getattr(call_response, "transcript", "No transcript available")
                            success = AppDatabase.store_call(project_id, call["call_id"], new_transcript)
                            if success:
                                st.success(f"Call '{call['call_id']}' updated successfully with new transcript!")
                                st.rerun()
                            else:
                                st.error(f"Failed to update Call '{call['call_id']}'.")
                        except Exception as e:
                            st.error(f"Failed to fetch new transcript for Call '{call['call_id']}': {str(e)}")

# Tab 3: Import Calls from File
with tab3:
    st.header("Import Calls from File")
    uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success("File uploaded successfully!")
            
            # Column mapping
            st.subheader("Map Columns")
            st.info("Please select the columns from your file that contain the Call ID and Transcript data. Make sure to map them correctly to ensure proper data import.")
            columns = df.columns.tolist()
            call_id_col = st.selectbox("Select Call ID Column", columns)
            transcript_col = st.selectbox("Select Transcript Column", columns)
            
            # Preview data
            st.subheader("Preview Data")
            st.info("Review the data below. You can uncheck the 'Import' checkbox for any calls you don't want to import.")
            preview_df = df[[call_id_col, transcript_col]].copy()
            preview_df.columns = ["Call ID", "Transcript"]
            
            # Add selection column
            preview_df.insert(0, "Import", True)
            edited_df = st.data_editor(preview_df, hide_index=True)
            
            # Import selected calls
            if st.button("Import Selected Calls"):
                selected_rows = edited_df[edited_df["Import"]]
                if len(selected_rows) == 0:
                    st.error("Please select at least one call to import.")
                else:
                    # Check for existing calls
                    existing_calls = []
                    for _, row in selected_rows.iterrows():
                        call_id = str(row["Call ID"])
                        if AppDatabase.get_call(project_id, call_id):
                            existing_calls.append(call_id)
                    
                    if existing_calls:
                        st.warning(f"Found {len(existing_calls)} existing call(s). What would you like to do?")
                        action = st.radio(
                            "Choose action for existing calls:",
                            ["Skip existing calls", "Override existing calls"],
                            key="duplicate_action"
                        )
                    
                    imported_count = 0
                    skipped_count = 0
                    updated_count = 0
                    
                    for _, row in selected_rows.iterrows():
                        call_id = str(row["Call ID"])
                        transcript = str(row["Transcript"])
                        
                        # Check if call exists
                        existing_call = AppDatabase.get_call(project_id, call_id)
                        if existing_call:
                            if action == "Skip existing calls":
                                skipped_count += 1
                                continue
                            else:  # Override
                                success = AppDatabase.store_call(project_id, call_id, transcript)
                                if success:
                                    updated_count += 1
                        else:
                            success = AppDatabase.store_call(project_id, call_id, transcript)
                            if success:
                                imported_count += 1
                    
                    # Show import results
                    if imported_count > 0:
                        st.success(f"Successfully imported {imported_count} new calls!")
                    if updated_count > 0:
                        st.success(f"Successfully updated {updated_count} existing calls!")
                    if skipped_count > 0:
                        st.info(f"Skipped {skipped_count} existing calls.")
                    
                    if imported_count > 0 or updated_count > 0:
                        # Clear the file uploader
                        st.session_state["file_uploader_key"] = None
                        st.rerun()
                    
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

# Tab 4: Export Calls
with tab4:
    st.header("Export Calls")
    stored_calls = AppDatabase.get_project_calls(project_id)
    
    if not stored_calls:
        st.write("No calls available to export.")
    else:
        st.write(f"Total calls available: {len(stored_calls)}")
        
        # Export options
        export_option = st.radio("Export Options", ["Export Single Call", "Export Selected Calls", "Export All Calls"])
        export_format = st.selectbox("Export Format", ["CSV", "Excel", "JSONL"])
        
        if export_option == "Export Single Call":
            call_id_to_export = st.selectbox("Select a Call ID to Export", 
                                           [call["call_id"] for call in stored_calls],
                                           key="export_single_call")
            if st.button("Export Call"):
                if call_id_to_export:
                    call = AppDatabase.get_call(project_id, call_id_to_export)
                    if call:
                        df = pd.DataFrame([{
                            "Call ID": call["call_id"],
                            "Transcript": call["transcript"],
                            "Timestamp": call["timestamp"]
                        }])
                        
                        if export_format == "CSV":
                            st.download_button(
                                label="Download CSV",
                                data=df.to_csv(index=False),
                                file_name=f"call_{call_id_to_export}.csv",
                                mime="text/csv"
                            )
                        elif export_format == "Excel":
                            buffer = io.BytesIO()
                            df.to_excel(buffer, index=False)
                            st.download_button(
                                label="Download Excel",
                                data=buffer.getvalue(),
                                file_name=f"call_{call_id_to_export}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:  # JSONL
                            jsonl_str = df.to_json(orient="records", lines=True)
                            st.download_button(
                                label="Download JSONL",
                                data=jsonl_str,
                                file_name=f"call_{call_id_to_export}.jsonl",
                                mime="application/jsonl"
                            )
                            
        elif export_option == "Export Selected Calls":
            selected_calls = st.multiselect("Select Calls to Export",
                                          [call["call_id"] for call in stored_calls],
                                          key="export_selected_calls")
            if st.button("Export Selected Calls") and selected_calls:
                export_data = []
                for call_id in selected_calls:
                    call = AppDatabase.get_call(project_id, call_id)
                    if call:
                        export_data.append({
                            "Call ID": call["call_id"],
                            "Transcript": call["transcript"],
                            "Timestamp": call["timestamp"]
                        })
                
                df = pd.DataFrame(export_data)
                if export_format == "CSV":
                    st.download_button(
                        label="Download CSV",
                        data=df.to_csv(index=False),
                        file_name="selected_calls.csv",
                        mime="text/csv"
                    )
                elif export_format == "Excel":
                    buffer = io.BytesIO()
                    df.to_excel(buffer, index=False)
                    st.download_button(
                        label="Download Excel",
                        data=buffer.getvalue(),
                        file_name="selected_calls.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:  # JSONL
                    jsonl_str = df.to_json(orient="records", lines=True)
                    st.download_button(
                        label="Download JSONL",
                        data=jsonl_str,
                        file_name="selected_calls.jsonl",
                        mime="application/jsonl"
                    )
                    
        else:  # Export All Calls
            if st.button("Export All Calls"):
                export_data = [{
                    "Call ID": call["call_id"],
                    "Transcript": call["transcript"],
                    "Timestamp": call["timestamp"]
                } for call in stored_calls]
                
                df = pd.DataFrame(export_data)
                if export_format == "CSV":
                    st.download_button(
                        label="Download CSV",
                        data=df.to_csv(index=False),
                        file_name="all_calls.csv",
                        mime="text/csv"
                    )
                elif export_format == "Excel":
                    buffer = io.BytesIO()
                    df.to_excel(buffer, index=False)
                    st.download_button(
                        label="Download Excel",
                        data=buffer.getvalue(),
                        file_name="all_calls.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:  # JSONL
                    jsonl_str = df.to_json(orient="records", lines=True)
                    st.download_button(
                        label="Download JSONL",
                        data=jsonl_str,
                        file_name="all_calls.jsonl",
                        mime="application/jsonl"
                    )