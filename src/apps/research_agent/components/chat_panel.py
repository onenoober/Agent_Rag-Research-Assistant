"""Chat panel component for Streamlit."""

import streamlit as st
from typing import List, Dict, Any


def render_message(message: Dict[str, Any]) -> None:
    """Render a single message."""
    role = message.get("role", "assistant")
    content = message.get("content", "")
    
    with st.chat_message(role):
        st.markdown(content)


def render_chat_history(messages: List[Dict[str, Any]]) -> None:
    """Render the chat history."""
    for message in messages:
        render_message(message)


def render_input() -> str:
    """Render chat input and return user input."""
    return st.chat_input("Ask me anything about your research documents...")


def render_citations(citations: Any) -> None:
    """Render citations if available."""
    if citations:
        with st.expander("📚 Citations"):
            st.markdown(citations)


def render_tool_steps(tool_steps: List[Dict[str, Any]]) -> None:
    """Render tool execution steps."""
    if tool_steps:
        with st.expander("🔧 Tool Steps"):
            for step in tool_steps:
                st.markdown(f"**{step.get('tool', 'Unknown')}:** {step.get('result', '')}")
