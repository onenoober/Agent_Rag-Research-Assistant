"""File uploader component for Streamlit."""

import streamlit as st
from typing import Optional, Dict, Any
import time

from src.agent.infra.logging import get_logger


logger = get_logger(__name__)


def render_uploader() -> Optional[Dict[str, Any]]:
    """Render the file uploader component.
    
    Returns:
        Upload result dict or None if no file uploaded.
    """
    st.subheader("📤 Upload & Ingest")

    col1, col2 = st.columns([3, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Choose a PDF file to upload",
            type=["pdf", "txt", "md", "docx"],
            help="Supported formats: PDF, TXT, MD, DOCX"
        )

    with col2:
        collection_name = st.text_input(
            "Collection",
            value="default",
            help="Target collection for ingestion"
        )

    if uploaded_file is not None:
        st.session_state["pending_upload"] = {
            "file": uploaded_file,
            "collection": collection_name
        }

        file_info = {
            "name": uploaded_file.name,
            "size": uploaded_file.size,
            "type": uploaded_file.type
        }

        with st.expander("📄 File Info", expanded=True):
            st.markdown(f"**Name:** {file_info['name']}")
            st.markdown(f"**Size:** {file_info['size'] / 1024:.1f} KB")
            st.markdown(f"**Type:** {file_info['type']}")

        if st.button("🚀 Start Ingestion", type="primary"):
            return process_upload(uploaded_file, collection_name)

    return None


def process_upload(uploaded_file, collection_name: str) -> Dict[str, Any]:
    """Process the uploaded file.
    
    Args:
        uploaded_file: The uploaded file object
        collection_name: Target collection name
        
    Returns:
        Result dict with status and details
    """
    from src.agent.adapters.ingestion_adapter import get_ingestion_adapter

    result = {
        "status": "processing",
        "file_name": uploaded_file.name,
        "collection": collection_name,
        "message": ""
    }

    try:
        with st.spinner("Ingesting file..."):
            start_time = time.time()

            adapter = get_ingestion_adapter()
            adapter.initialize()

            from io import BytesIO
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            try:
                ingest_result = adapter.ingest(
                    file_path=tmp_path,
                    collection_name=collection_name,
                    metadata={"source": "streamlit_upload", "file_name": uploaded_file.name}
                )

                duration = time.time() - start_time

                result["status"] = "success"
                result["message"] = f"Successfully ingested {uploaded_file.name}"
                result["doc_id"] = ingest_result.doc_id
                result["chunks"] = ingest_result.indexed_chunks
                result["duration"] = duration

                st.success(f"✅ {result['message']}")
                st.markdown(f"**Indexed Chunks:** {result['chunks']}")
                st.markdown(f"**Duration:** {result['duration']:.2f}s")

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        result["status"] = "error"
        result["message"] = str(e)
        st.error(f"❌ Upload failed: {e}")

    return result


def render_upload_history() -> None:
    """Render the upload history panel."""
    if "upload_history" not in st.session_state:
        st.session_state.upload_history = []

    history = st.session_state.upload_history

    if not history:
        st.info("No upload history yet.")
        return

    st.subheader("📋 Upload History")

    for item in reversed(history[-10:]):
        status_icon = "✅" if item["status"] == "success" else "❌"
        st.markdown(
            f"{status_icon} **{item['file_name']}** → "
            f"`{item['collection']}` ({item.get('chunks', 0)} chunks)"
        )
