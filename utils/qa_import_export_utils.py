import streamlit as st
import pandas as pd
import json
import io
from utils.db import AppDatabase
from utils.qa_utils import check_duplicate_qa

def handle_qa_import(project_id):
    """Handle importing QA pairs from a file."""
    uploaded_file = st.file_uploader("Upload CSV or Excel file with QA pairs", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.success("File uploaded successfully!")
            st.subheader("Map Columns")
            columns = df.columns.tolist()
            question_col = st.selectbox("Select Question Column", columns, key="question_col")
            answer_col = st.selectbox("Select Answer Column", columns, key="answer_col")
            has_call_id = st.checkbox("File includes Call ID column", value=False)
            call_id_col = None
            if has_call_id:
                call_id_col = st.selectbox("Select Call ID Column", columns, key="call_id_col")
            st.subheader("Preview Data")
            preview_cols = [question_col, answer_col]
            if has_call_id:
                preview_cols.append(call_id_col)
            preview_df = df[preview_cols].copy()
            column_map = {"question_col": "Question", "answer_col": "Answer"}
            if has_call_id:
                column_map[call_id_col] = "Call ID"
            preview_df = preview_df.rename(columns=column_map)
            preview_df.insert(0, "Import", True)
            preview_df["Question"] = preview_df["Question"].astype(str).apply(lambda x: x.strip())
            preview_df["Answer"] = preview_df["Answer"].astype(str).apply(lambda x: x.strip())
            if has_call_id:
                preview_df["Call ID"] = preview_df["Call ID"].astype(str).apply(lambda x: x.strip() if x and x.lower() != 'nan' else None)
            preview_df = preview_df.dropna(subset=["Question", "Answer"], how='all')
            edited_df = st.data_editor(preview_df, hide_index=True, use_container_width=True)
            if st.button("Import Selected QA Pairs"):
                selected_rows = edited_df[edited_df["Import"]]
                if len(selected_rows) == 0:
                    st.error("Please select at least one QA pair to import.")
                else:
                    existing_qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
                    duplicate_count = sum(1 for _, row in selected_rows.iterrows() if check_duplicate_qa(project_id, row["Question"], existing_qa_pairs))
                    duplicate_action = "Skip duplicates"
                    if duplicate_count > 0:
                        st.warning(f"Found {duplicate_count} potential duplicate question(s).")
                        duplicate_action = st.radio(
                            "Choose action for duplicates:",
                            ["Skip duplicates", "Override existing", "Save as new entries"],
                            key="import_dup_action"
                        )
                    if st.button("Confirm Import"):
                        with st.spinner("Importing QA pairs..."):
                            saved_count = updated_count = skipped_count = error_count = 0
                            for _, row in selected_rows.iterrows():
                                question = row["Question"]
                                answer = row["Answer"]
                                call_id = row.get("Call ID", None) if has_call_id else None
                                if not question or not answer or pd.isna(question) or pd.isna(answer):
                                    error_count += 1
                                    continue
                                duplicate = check_duplicate_qa(project_id, question, existing_qa_pairs)
                                try:
                                    if duplicate:
                                        if duplicate_action == "Skip duplicates":
                                            skipped_count += 1
                                            continue
                                        elif duplicate_action == "Override existing":
                                            if AppDatabase.remove_qa_pair(project_id, duplicate['id']) and AppDatabase.store_qa_pair(project_id, question, answer, call_id):
                                                updated_count += 1
                                            else:
                                                error_count += 1
                                        else:
                                            if AppDatabase.store_qa_pair(project_id, question, answer, call_id):
                                                saved_count += 1
                                            else:
                                                error_count += 1
                                    else:
                                        if AppDatabase.store_qa_pair(project_id, question, answer, call_id):
                                            saved_count += 1
                                        else:
                                            error_count += 1
                                except Exception as e:
                                    st.error(f"Error processing QA pair: {str(e)}")
                                    error_count += 1
                            result_msg = []
                            if saved_count > 0:
                                result_msg.append(f"{saved_count} new QA pairs saved")
                            if updated_count > 0:
                                result_msg.append(f"{updated_count} existing QA pairs updated")
                            if skipped_count > 0:
                                result_msg.append(f"{skipped_count} duplicates skipped")
                            if error_count > 0:
                                result_msg.append(f"{error_count} errors encountered")
                            if saved_count > 0 or updated_count > 0:
                                st.success(f"Import completed successfully! {' and '.join(result_msg)}")
                                st.rerun()
                            else:
                                st.error(f"Import failed. {' and '.join(result_msg)}")
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

def handle_qa_export(project_id):
    """Handle exporting QA pairs from main or temporary storage."""
    source = st.radio("Select QA Source", ["Main QA Storage", "Temporary QA Storage"], key="export_source")

    if source == "Main QA Storage":
        qa_pairs = AppDatabase.get_project_qa_pairs(project_id)
        if not qa_pairs:
            st.write("No QA pairs available in Main QA Storage to export.")
            return
    else:  # Temporary QA Storage
        qa_pairs = AppDatabase.get_project_qa_temp(project_id)
        if not qa_pairs:
            st.write("No QA pairs available in Temporary QA Storage to export.")
            return

    st.subheader("Export Options")
    export_opt = st.radio("Select what to export:", ["All QA Pairs", "Filter by Search", "Select Specific Pairs"], key="export_opt")
    export_format = st.selectbox("Export Format", ["CSV", "Excel", "JSONL"], key="export_format")
    filtered_export_pairs = []

    if source == "Main QA Storage":
        call_ids = list(set([qa["call_id"] for qa in qa_pairs if qa["call_id"]]))
        if export_opt == "All QA Pairs":
            filtered_export_pairs = qa_pairs
            st.write(f"Exporting all {len(qa_pairs)} QA pairs from Main QA Storage")
        elif export_opt == "Filter by Search":
            search_query = st.text_input("Search for questions containing:", key="export_search_main")
            selected_call_id = "All"
            if call_ids:
                filter_call = st.checkbox("Filter by Call ID", key="export_filter_call_main")
                if filter_call:
                    selected_call_id = st.selectbox("Select Call ID", ["All"] + call_ids, key="export_filter_call_id_main")
            filtered_export_pairs = [qa for qa in qa_pairs if 
                                    (not search_query or search_query.lower() in qa["question"].lower()) and
                                    (selected_call_id == "All" or qa["call_id"] == selected_call_id)]
            st.write(f"Exporting {len(filtered_export_pairs)} of {len(qa_pairs)} QA pairs from Main QA Storage")
        elif export_opt == "Select Specific Pairs":
            selected_qa_ids = st.multiselect("Select QA Pairs to Export",
                                            [f"#{qa['id']} - {qa['question'][:50]}..." for qa in qa_pairs],
                                            key="export_selected_pairs_main")
            selected_ids = [int(item.split('-')[0][1:].strip()) for item in selected_qa_ids]
            filtered_export_pairs = [qa for qa in qa_pairs if qa["id"] in selected_ids]
            st.write(f"Exporting {len(filtered_export_pairs)} selected QA pairs from Main QA Storage")
    else:  # Temporary QA Storage
        source_types = list(set([qa["source_type"] for qa in qa_pairs]))
        if export_opt == "All QA Pairs":
            filtered_export_pairs = qa_pairs
            st.write(f"Exporting all {len(qa_pairs)} QA pairs from Temporary QA Storage")
        elif export_opt == "Filter by Search":
            search_query = st.text_input("Search for questions containing:", key="export_search_temp")
            selected_source_type = st.selectbox("Filter by Source Type", ["All"] + source_types, key="filter_source_type")
            filtered_export_pairs = [qa for qa in qa_pairs if 
                                    (not search_query or search_query.lower() in qa["question"].lower()) and
                                    (selected_source_type == "All" or qa["source_type"] == selected_source_type)]
            st.write(f"Exporting {len(filtered_export_pairs)} of {len(qa_pairs)} QA pairs from Temporary QA Storage")
        elif export_opt == "Select Specific Pairs":
            selected_qa_ids = st.multiselect("Select QA Pairs to Export",
                                            [f"#{qa['id']} - {qa['question'][:50]}..." for qa in qa_pairs],
                                            key="export_selected_pairs_temp")
            selected_ids = [int(item.split('-')[0][1:].strip()) for item in selected_qa_ids]
            filtered_export_pairs = [qa for qa in qa_pairs if qa["id"] in selected_ids]
            st.write(f"Exporting {len(filtered_export_pairs)} selected QA pairs from Temporary QA Storage")

    if filtered_export_pairs:
        st.subheader("Export Preview")
        if source == "Main QA Storage":
            preview_df = pd.DataFrame([{"ID": qa["id"], "Question": qa["question"], "Answer": qa["answer"],
                                        "Call ID": qa["call_id"] or "", "Created At": qa["created_at"]}
                                      for qa in filtered_export_pairs[:5]])
        else:
            preview_df = pd.DataFrame([{"ID": qa["id"], "Question": qa["question"], "Answer": qa["answer"],
                                        "Source Type": qa["source_type"], "Source ID": qa["source_id"] or "",
                                        "Created At": qa["created_at"]}
                                      for qa in filtered_export_pairs[:5]])
        st.dataframe(preview_df, use_container_width=True)
        if len(filtered_export_pairs) > 5:
            st.info(f"Showing preview of first 5 entries. Full export will include {len(filtered_export_pairs)} entries.")

        if source == "Main QA Storage":
            export_df = pd.DataFrame([{"ID": qa["id"], "Question": qa["question"], "Answer": qa["answer"],
                                       "Call ID": qa["call_id"] or "", "Created At": qa["created_at"]}
                                     for qa in filtered_export_pairs])
        else:
            export_df = pd.DataFrame([{"ID": qa["id"], "Question": qa["question"], "Answer": qa["answer"],
                                       "Source Type": qa["source_type"], "Source ID": qa["source_id"] or "",
                                       "Created At": qa["created_at"]}
                                     for qa in filtered_export_pairs])

        if export_format == "CSV":
            csv_data = export_df.to_csv(index=False)
            st.download_button(label="Download CSV", data=csv_data, file_name=f"qa_pairs_project_{project_id}_{source.lower().replace(' ', '_')}.csv", mime="text/csv")
        elif export_format == "Excel":
            buffer = io.BytesIO()
            export_df.to_excel(buffer, index=False)
            st.download_button(label="Download Excel", data=buffer.getvalue(),
                              file_name=f"qa_pairs_project_{project_id}_{source.lower().replace(' ', '_')}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:  # JSONL
            if source == "Main QA Storage":
                jsonl_data = "".join([json.dumps({"id": qa["id"], "question": qa["question"], "answer": qa["answer"],
                                                 "call_id": qa["call_id"] or None, "created_at": qa["created_at"]}) + "\n"
                                     for qa in filtered_export_pairs])
            else:
                jsonl_data = "".join([json.dumps({"id": qa["id"], "question": qa["question"], "answer": qa["answer"],
                                                 "source_type": qa["source_type"], "source_id": qa["source_id"] or None,
                                                 "created_at": qa["created_at"]}) + "\n"
                                     for qa in filtered_export_pairs])
            st.download_button(label="Download JSONL", data=jsonl_data, 
                              file_name=f"qa_pairs_project_{project_id}_{source.lower().replace(' ', '_')}.jsonl",
                              mime="application/jsonl")