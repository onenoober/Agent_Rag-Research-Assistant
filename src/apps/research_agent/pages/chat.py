"""Chat page for Research Agent."""

import streamlit as st
from typing import List, Dict, Any, Optional
import time
import asyncio

from src.agent.infra.logging import get_logger
from src.agent.services.chat_service import ChatService


logger = get_logger(__name__)


def init_chat_session():
    """Initialize chat session state."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "current_response" not in st.session_state:
        st.session_state.current_response = None
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False


def render_chat_header():
    """Render chat page header."""
    st.title("🔬 Research Agent")
    st.markdown("Ask questions about your research documents")


def render_message(message: Dict[str, Any]):
    """Render a single chat message."""
    role = message.get("role", "assistant")
    content = message.get("content", "")
    tool_steps = message.get("tool_steps", [])
    citations = message.get("citations", [])

    with st.chat_message(role):
        st.markdown(content)

        if tool_steps:
            with st.expander("🔧 Tool Steps"):
                for step in tool_steps:
                    tool_name = step.get("tool", "Unknown")
                    result = step.get("result", "")
                    status = step.get("status", "success")
                    st.markdown(f"**{tool_name}** ({status})")
                    if result:
                        st.text(result[:500] + "..." if len(str(result)) > 500 else result)

        if citations:
            with st.expander(f"📚 Citations ({len(citations)})"):
                for i, cite in enumerate(citations):
                    source = cite.get("source", "Unknown")
                    text = cite.get("text", "")[:200]
                    page_no = cite.get("page_no")
                    section_title = cite.get("section_title")

                    # 构建来源信息
                    source_info = f"**{i+1}. {source}**"
                    if page_no is not None:
                        source_info += f" (Page {page_no})"
                    if section_title:
                        source_info += f" - {section_title}"

                    st.markdown(source_info)
                    st.text(text + "...")


def render_chat_history():
    """Render the chat history."""
    for message in st.session_state.chat_history:
        render_message(message)


def handle_user_message(prompt: str) -> Optional[Dict[str, Any]]:
    """Handle user message and get response.

    Args:
        prompt: User input prompt

    Returns:
        Response dict or None
    """
    if not prompt.strip():
        return None

    st.session_state.is_processing = True

    user_message = {
        "role": "user",
        "content": prompt,
        "timestamp": time.time()
    }
    st.session_state.chat_history.append(user_message)

    try:
        # 获取前端设置的反思配置
        settings = st.session_state.get("agent_settings", {})
        enable_reflection = settings.get("enable_reflection", True)

        # 根据设置创建 ChatService
        chat_service = ChatService(enable_reflection=enable_reflection)

        # 使用 asyncio.run() 调用异步方法
        response = asyncio.run(chat_service.chat(
            query=prompt,
            session_id=st.session_state.get("session_id", "default")
        ))

        assistant_message = {
            "role": "assistant",
            "content": response.answer,
            "tool_steps": response.tool_steps if hasattr(response, "tool_steps") else [],
            "citations": response.citations if hasattr(response, "citations") else [],
            "timestamp": time.time()
        }
        st.session_state.chat_history.append(assistant_message)
        st.session_state.current_response = response

        return assistant_message

    except Exception as e:
        logger.error(f"Chat error: {e}")
        error_message = {
            "role": "assistant",
            "content": f"❌ Error: {str(e)}",
            "timestamp": time.time()
        }
        st.session_state.chat_history.append(error_message)
        return error_message
    finally:
        st.session_state.is_processing = False


def render_input_area():
    """Render the chat input area."""
    if st.session_state.is_processing:
        st.info("🤔 Thinking...")
        return

    if prompt := st.chat_input("Ask a question about your research..."):
        handle_user_message(prompt)
        st.rerun()


def render_sidebar():
    """Render sidebar with additional options."""
    with st.sidebar:
        st.header("⚙️ Session")
        
        session_id = st.text_input(
            "Session ID",
            value=st.session_state.get("session_id", "default"),
            help="Unique session identifier for memory"
        )
        st.session_state.session_id = session_id

        st.divider()

        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.session_state.current_response = None
            st.rerun()

        st.divider()

        st.markdown("### 💡 Tips")
        st.markdown("""
        - Ask questions about your uploaded documents
        - Use **RAG Search** tool to find relevant content
        - Upload PDFs via the sidebar
        - Your chat history is saved in memory
        """)


def main():
    """Main chat page."""
    init_chat_session()
    render_chat_header()
    render_sidebar()
    render_chat_history()
    render_input_area()


if __name__ == "__main__":
    main()
