"""Tool steps component for Streamlit."""

import streamlit as st
from typing import List, Dict, Any


def render_tool_step_card(step: Dict[str, Any]) -> None:
    """Render a single tool step as a card."""
    tool_name = step.get("tool", "Unknown")
    result = step.get("result", "")
    status = step.get("status", "success")
    duration = step.get("duration_ms", 0)

    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**🔧 {tool_name}**")
        with col2:
            if status == "success":
                st.success(f"✓ {duration:.0f}ms")
            elif status == "error":
                st.error("✗ Failed")
            else:
                st.warning("⏳ Running")

        if result:
            with st.expander("View Details"):
                st.markdown(result)


def render_tool_steps_panel(tool_steps: List[Dict[str, Any]]) -> None:
    """Render the tool steps panel."""
    if not tool_steps:
        st.info("No tool steps executed yet.")
        return

    st.subheader("🔧 Tool Execution Steps")

    for i, step in enumerate(tool_steps):
        with st.expander(f"Step {i+1}: {step.get('tool', 'Unknown')}", expanded=i == len(tool_steps) - 1):
            render_tool_step_card(step)


def render_tool_summary(tool_steps: List[Dict[str, Any]]) -> None:
    """Render a summary of tool executions."""
    if not tool_steps:
        return

    total_steps = len(tool_steps)
    success_count = sum(1 for s in tool_steps if s.get("status") == "success")
    error_count = sum(1 for s in tool_steps if s.get("status") == "error")
    total_time = sum(s.get("duration_ms", 0) for s in tool_steps)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Steps", total_steps)
    with col2:
        st.metric("Success", success_count)
    with col3:
        st.metric("Errors", error_count)
    with col4:
        st.metric("Total Time", f"{total_time:.0f}ms")


def render_citations_panel(citations: List[Dict[str, Any]]) -> None:
    """Render citations in a formatted panel."""
    if not citations:
        return

    st.subheader("📚 Citations")

    for i, citation in enumerate(citations):
        with st.expander(f"Source {i+1}: {citation.get('source', 'Unknown')}"):
            st.markdown(f"**Title:** {citation.get('title', 'N/A')}")
            st.markdown(f"**Score:** {citation.get('score', 0):.4f}")
            st.markdown("**Content:**")
            st.text(citation.get("text", ""))
            if citation.get("metadata"):
                with st.expander("Metadata"):
                    st.json(citation.get("metadata", {}))
