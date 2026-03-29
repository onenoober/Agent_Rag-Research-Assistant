"""Research Agent Streamlit App."""

import streamlit as st
from typing import Optional
import time
import asyncio

from src.agent.infra.logging import get_logger


logger = get_logger(__name__)


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = "default"
    if "agent_config" not in st.session_state:
        st.session_state.agent_config = {}
    if "upload_history" not in st.session_state:
        st.session_state.upload_history = []


def render_sidebar():
    """Render sidebar with navigation and upload."""
    with st.sidebar:
        st.title("🔬 Research Agent")

        page = st.radio(
            "Navigation",
            ["💬 Chat", "📤 Upload", "📊 Evaluation", "⚙️ Settings"],
            label_visibility="collapsed"
        )

        st.divider()

        if page == "📤 Upload":
            render_upload_section()

        st.divider()

        session_id = st.text_input(
            "Session ID",
            value=st.session_state.session_id,
            help="Unique session identifier"
        )
        st.session_state.session_id = session_id

        st.divider()

        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

        return page


def render_upload_section():
    """Render the upload section in sidebar."""
    from src.apps.research_agent.components.uploader import render_uploader, process_upload

    st.subheader("📤 Upload Document")

    col1, col2 = st.columns([3, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Choose file",
            type=["pdf", "txt", "md", "docx"],
            label_visibility="collapsed"
        )

    with col2:
        collection_name = st.text_input(
            "Collection",
            value="default",
            label_visibility="collapsed"
        )

    if uploaded_file is not None:
        st.markdown(f"**File:** {uploaded_file.name}")
        st.markdown(f"**Size:** {uploaded_file.size / 1024:.1f} KB")

        if st.button("🚀 Ingest", type="primary", key="ingest_btn"):
            result = process_upload(uploaded_file, collection_name)
            if result.get("status") == "success":
                st.session_state.upload_history.append(result)
                st.success(f"✅ Indexed {result.get('chunks', 0)} chunks")
            else:
                st.error(f"❌ {result.get('message', 'Error')}")


def render_chat_panel():
    """Render the main chat panel."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message.get("tool_steps"):
                with st.expander(f"🔧 Tools ({len(message['tool_steps'])})"):
                    for step in message["tool_steps"]:
                        # Handle both dict and object formats
                        if hasattr(step, 'to_dict'):
                            step = step.to_dict()
                        st.markdown(f"**{step.get('tool', 'Unknown')}**: {step.get('status', 'done')}")

            if message.get("citations"):
                with st.expander(f"📚 Citations ({len(message['citations'])})"):
                    for cite in message["citations"]:
                        # Handle both dict and object formats
                        if hasattr(cite, 'to_dict'):
                            cite = cite.to_dict()
                        source = cite.get("source", "Unknown")
                        text = cite.get("text", "")[:200]
                        page_no = cite.get("page_no")
                        section_title = cite.get("section_title")

                        # 构建来源信息
                        source_info = f"**{source}**"
                        if page_no is not None:
                            source_info += f" (Page {page_no})"
                        if section_title:
                            source_info += f" - {section_title}"

                        st.markdown(source_info)
                        st.text(text + "...")


def handle_user_input(prompt: str) -> Optional[str]:
    """Handle user input and get response."""
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                from src.agent.services.chat_service import ChatService
                chat_service = ChatService()
                # 使用 asyncio.run() 调用异步方法
                response = asyncio.run(chat_service.chat(
                    query=prompt,
                    session_id=st.session_state.session_id
                ))

                st.markdown(response.answer)

                assistant_msg = {"role": "assistant", "content": response.answer}

                if hasattr(response, "tool_steps") and response.tool_steps:
                    assistant_msg["tool_steps"] = response.tool_steps

                if hasattr(response, "citations") and response.citations:
                    assistant_msg["citations"] = response.citations

                st.session_state.messages.append(assistant_msg)

                return response.answer

            except Exception as e:
                logger.error(f"Chat error: {e}")
                error_msg = f"❌ Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                return None

    return None


def main():
    """Main app entry point."""
    st.set_page_config(
        page_title="Research Agent",
        page_icon="🔬",
        layout="wide"
    )

    init_session_state()

    page = render_sidebar()

    if page == "💬 Chat":
        st.title("💬 Chat")
        render_chat_panel()

        if prompt := st.chat_input("Ask about your research documents..."):
            handle_user_input(prompt)
            st.rerun()

    elif page == "📊 Evaluation":
        from src.apps.research_agent.pages.eval import main as eval_main
        eval_main()

    elif page == "⚙️ Settings":
        from src.apps.research_agent.pages.settings import main as settings_main
        settings_main()


if __name__ == "__main__":
    main()
