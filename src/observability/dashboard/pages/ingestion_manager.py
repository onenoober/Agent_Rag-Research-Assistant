"""Ingestion Manager page – upload files, trigger ingestion, delete documents.

Layout:
1. File uploader + collection selector + chunking config
2. Ingest button → progress bar (using on_progress callback)
3. Document list with delete buttons
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st
import yaml

from src.core.settings import resolve_path, DEFAULT_SETTINGS_PATH
from src.observability.dashboard.services.data_service import DataService

# Path to settings file
SETTINGS_PATH = resolve_path(DEFAULT_SETTINGS_PATH)


def _load_ingestion_config() -> dict:
    """Load current ingestion configuration from settings.yaml."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("ingestion", {}) or {}
    except Exception:
        return {}


def _save_ingestion_config(chunk_size: int, chunk_overlap: int, batch_size: int) -> bool:
    """Save ingestion configuration to settings.yaml."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if "ingestion" not in config:
            config["ingestion"] = {}

        config["ingestion"]["chunk_size"] = chunk_size
        config["ingestion"]["chunk_overlap"] = chunk_overlap
        config["ingestion"]["batch_size"] = batch_size

        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)

        return True
    except Exception as e:
        st.error(f"Failed to save settings: {e}")
        return False


def _run_ingestion(
    uploaded_file: "st.runtime.uploaded_file_manager.UploadedFile",
    collection: str,
    progress_bar: "st.delta_generator.DeltaGenerator",
    status_text: "st.delta_generator.DeltaGenerator",
) -> None:
    """Save the uploaded file to a temp location and run the pipeline."""
    from src.core.settings import load_settings
    from src.core.trace import TraceContext, TraceCollector
    from src.ingestion.pipeline import IngestionPipeline

    settings = load_settings()

    # Write uploaded file to a temp location
    suffix = Path(uploaded_file.name).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    _STAGE_LABELS = {
        "integrity": "🔍 Checking file integrity…",
        "load": "📄 Loading document…",
        "split": "✂️ Chunking document…",
        "transform": "🔄 Transforming chunks (LLM refine + enrich)…",
        "embed": "🔢 Encoding vectors…",
        "upsert": "💾 Storing to database…",
    }

    def on_progress(stage: str, current: int, total: int) -> None:
        frac = (current - 1) / total  # stage just started, show partial progress
        label = _STAGE_LABELS.get(stage, stage)
        progress_bar.progress(frac, text=f"[{current}/{total}] {label}")
        status_text.caption(label)

    trace = TraceContext(trace_type="ingestion")
    trace.metadata["source_path"] = uploaded_file.name
    trace.metadata["collection"] = collection
    trace.metadata["source"] = "dashboard"

    try:
        pipeline = IngestionPipeline(settings, collection=collection)
        pipeline.run(
            file_path=tmp_path,
            trace=trace,
            on_progress=on_progress,
        )
        progress_bar.progress(1.0, text="✅ Complete")
        status_text.success(f"Successfully ingested **{uploaded_file.name}** into collection **{collection}**.")
    except Exception as exc:
        status_text.error(f"Ingestion failed: {exc}")
    finally:
        TraceCollector().collect(trace)
        # Clean up temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def render() -> None:
    """Render the Ingestion Manager page."""
    st.header("📥 Ingestion Manager")

    # ── Chunking Configuration ─────────────────────────────────────
    st.subheader("⚙️ Chunking Configuration")

    # Load current config
    current_config = _load_ingestion_config()

    # Create config inputs
    col1, col2, col3 = st.columns(3)
    with col1:
        chunk_size = st.number_input(
            "Chunk Size (chars)",
            min_value=100,
            max_value=10000,
            value=current_config.get("chunk_size", 1000),
            step=100,
            help="Maximum number of characters per chunk",
        )
    with col2:
        chunk_overlap = st.number_input(
            "Chunk Overlap (chars)",
            min_value=0,
            max_value=1000,
            value=current_config.get("chunk_overlap", 200),
            step=50,
            help="Number of overlapping characters between adjacent chunks",
        )
    with col3:
        batch_size = st.number_input(
            "Embedding Batch Size",
            min_value=1,
            max_value=100,
            value=current_config.get("batch_size", 10),
            step=1,
            help="Number of chunks to embed per API call",
        )

    # Save button
    if st.button("💾 Save Configuration", key="btn_save_config"):
        if _save_ingestion_config(chunk_size, chunk_overlap, batch_size):
            st.success("Configuration saved! Changes will apply to new ingestions.")
            st.rerun()

    st.divider()

    # ── Upload section ─────────────────────────────────────────────
    st.subheader("📤 Upload & Ingest")

    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded = st.file_uploader(
            "Select a file to ingest",
            type=["pdf", "txt", "md", "docx"],
            key="ingest_uploader",
        )
    with col2:
        collection = st.text_input("Collection", value="default", key="ingest_collection")

    if uploaded is not None:
        if st.button("🚀 Start Ingestion", key="btn_ingest"):
            progress_bar = st.progress(0, text="Preparing…")
            status_text = st.empty()
            _run_ingestion(uploaded, collection.strip() or "default", progress_bar, status_text)

    st.divider()

    # ── Document management section ────────────────────────────────
    st.subheader("🗑️ Manage Documents")

    try:
        svc = DataService()
        docs = svc.list_documents()
    except Exception as exc:
        st.error(f"Failed to load documents: {exc}")
        return

    if not docs:
        st.info(
            "**No documents ingested yet.** "
            "Upload a PDF, TXT, MD, or DOCX file above and click \"Start Ingestion\" to begin."
        )
        return

    for idx, doc in enumerate(docs):
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(
                f"**{doc['source_path']}** — "
                f"collection: `{doc.get('collection', '—')}` | "
                f"chunks: {doc['chunk_count']} | "
                f"images: {doc['image_count']}"
            )
        with col_btn:
            if st.button("🗑️ Delete", key=f"del_{idx}"):
                try:
                    result = svc.delete_document(
                        source_path=doc["source_path"],
                        collection=doc.get("collection", "default"),
                        source_hash=doc.get("source_hash"),
                    )
                    if result.success:
                        st.success(
                            f"Deleted: {result.chunks_deleted} chunks, "
                            f"{result.images_deleted} images removed."
                        )
                        st.rerun()
                    else:
                        st.warning(f"Partial delete. Errors: {result.errors}")
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")
