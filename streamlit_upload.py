import streamlit as st
import os
from pathlib import Path
import pandas as pd

from config_data import QA_OUTPUT_CSV, QA_PAIR_COUNT, UPLOAD_TEMP_DIR
from utils_data import ensure_dir
from document_ingest import extract_document
from summarizer_data import summarize_text
from qa_generator_data import generate_qa_pairs
from postprocess_and_save import finalize_and_write

st.set_page_config(page_title="Hotel Doc → Summary → QA", layout="wide")

# Ensure directories exist
os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)

st.title("📄 Single-Doc Processing: Summary + 150 QA Pairs per Document")
st.markdown(
    """
**Workflow:**
1. Summarize each uploaded document.
2. Generate exactly 150 Q&A pairs for that document.
3. Append results to a growing CSV file.
"""
)

# Ask user for hotel name
hotel_name_input = st.text_input(
    "Enter the Hotel Name",
    placeholder="e.g., LUXORIA SUITES"
)

uploaded_files = st.file_uploader(
    "Upload hotel documents",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True
)

if st.button("Run Pipeline", disabled=not uploaded_files or not hotel_name_input.strip()):
    if not hotel_name_input.strip():
        st.warning("Please enter the hotel name before proceeding.")
        st.stop()
    if not uploaded_files:
        st.warning("Please upload at least one document.")
        st.stop()

    hotel_context = hotel_name_input.strip()
    st.markdown(f"**Hotel context for QA generation:** {hotel_context}")

    failed = []
    all_pairs = []

    ensure_dir(QA_OUTPUT_CSV)

    with st.spinner("Processing documents..."):
        for uploaded in uploaded_files:
            st.markdown(f"## 📄 Processing: **{uploaded.name}**")

            temp_path = Path(UPLOAD_TEMP_DIR) / uploaded.name
            try:
                with open(temp_path, "wb") as f:
                    f.write(uploaded.getbuffer())
            except Exception as e:
                st.error(f"Failed to save uploaded file {uploaded.name}: {e}")
                failed.append(uploaded.name)
                continue

            # Extract text
            try:
                text = extract_document(str(temp_path))
                st.success(f"Extracted text from {uploaded.name}")
            except Exception as e:
                st.error(f"Failed to extract {uploaded.name}: {e}")
                failed.append(uploaded.name)
                continue

            # Summarize
            try:
                summary, _ = summarize_text(uploaded.name, text)
                st.markdown("### Summary")
                st.text_area(f"summary_{uploaded.name}", value=summary, height=150)
            except Exception as e:
                st.error(f"Summarization failed for {uploaded.name}: {e}")
                failed.append(uploaded.name)
                continue

            # Generate QA pairs for this document only
            try:
                raw_response, parsed_pairs = generate_qa_pairs(hotel_context, summary, QA_PAIR_COUNT)
            except Exception as e:
                st.error(f"QA generation failed for {uploaded.name}: {e}")
                failed.append(uploaded.name)
                continue

            # Show raw output
            st.subheader("Raw QA Model Output")
            st.text_area(f"raw_qa_output_{uploaded.name}", value=raw_response, height=200)

            # Show parsed pairs
            if parsed_pairs:
                st.subheader("Parsed QA Pairs Preview")
                st.dataframe(pd.DataFrame(parsed_pairs, columns=["question", "answer"]).head(15))
            else:
                st.warning("No QA pairs parsed for this document.")
                continue

            # Append to CSV immediately
            if os.path.exists(QA_OUTPUT_CSV):
                existing_df = pd.read_csv(QA_OUTPUT_CSV, header=None, names=["question", "answer"])
                new_df = pd.DataFrame(parsed_pairs, columns=["question", "answer"])
                final_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                final_df = pd.DataFrame(parsed_pairs, columns=["question", "answer"])

            final_df.to_csv(QA_OUTPUT_CSV, index=False, header=False)
            st.success(f"Appended {len(parsed_pairs)} QA pairs for {uploaded.name} to {QA_OUTPUT_CSV}")

            all_pairs.extend(parsed_pairs)

    # Downloads
    st.markdown("## Downloads")
    if os.path.exists(QA_OUTPUT_CSV):
        with open(QA_OUTPUT_CSV, "rb") as f:
            st.download_button(
                "Download Combined QA CSV",
                data=f,
                file_name=f"qa_pairs_{hotel_context.replace(' ', '_')}.csv",
                mime="text/csv"
            )

    # Show all combined pairs in UI
    if all_pairs:
        st.markdown("### All QA Pairs from this Run")
        st.dataframe(pd.DataFrame(all_pairs, columns=["question", "answer"]))

    if failed:
        st.warning(f"Failed to process: {', '.join(failed)}")
