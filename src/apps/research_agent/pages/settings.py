"""Settings page for Research Agent."""

import streamlit as st
from typing import Dict, Any, Optional

from src.agent.infra.logging import get_logger
from src.agent.adapters.settings_adapter import get_agent_config


logger = get_logger(__name__)


def init_settings_session():
    """Initialize settings session state."""
    if "agent_settings" not in st.session_state:
        st.session_state.agent_settings = get_default_settings()


def get_default_settings() -> Dict[str, Any]:
    """Get default agent settings."""
    return {
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 0.9,
        "retrieval_top_k": 5,
        "enable_citations": True,
        "show_tool_steps": True,
        "max_tool_iterations": 3,
        # Phase 2 retrieval enhancements
        "enable_hybrid": True,
        "enable_rerank": False,
        "enable_query_rewrite": False,
        # Phase 3 reflection mechanism
        "enable_reflection": True,
        "max_iterations": 3,
        "reflection_timeout": 30,
    }


def load_settings_from_config() -> Dict[str, Any]:
    """Load settings from config adapter."""
    try:
        config = get_agent_config()
        return {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "retrieval_top_k": config.retrieval_top_k,
            "enable_citations": True,
            "show_tool_steps": True,
            "max_tool_iterations": config.max_tool_iterations,
            # Phase 2 retrieval enhancements
            "enable_hybrid": getattr(config, 'enable_hybrid', True),
            "enable_rerank": getattr(config, 'enable_rerank', False),
            "enable_query_rewrite": getattr(config, 'enable_query_rewrite', False),
            # Phase 3 reflection mechanism
            "enable_reflection": getattr(config, 'enable_reflection', True),
            "max_iterations": getattr(config, 'max_iterations', 3),
            "reflection_timeout": getattr(config, 'reflection_timeout', 30),
        }
    except Exception as e:
        logger.warning(f"Failed to load settings from config: {e}")
        return get_default_settings()


def render_settings_header():
    """Render settings page header."""
    st.title("⚙️ Settings")
    st.markdown("Configure your Research Agent preferences")


def render_model_settings():
    """Render model configuration section."""
    st.subheader("🤖 Model Configuration")

    settings = st.session_state.agent_settings

    col1, col2 = st.columns(2)

    with col1:
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=settings.get("temperature", 0.7),
            step=0.1,
            help="Controls randomness. Lower = more deterministic"
        )

        max_tokens = st.number_input(
            "Max Tokens",
            min_value=256,
            max_value=8192,
            value=settings.get("max_tokens", 2048),
            step=256,
            help="Maximum tokens to generate"
        )

    with col2:
        top_p = st.slider(
            "Top P",
            min_value=0.1,
            max_value=1.0,
            value=settings.get("top_p", 0.9),
            step=0.1,
            help="Nucleus sampling threshold"
        )

        max_tool_iterations = st.number_input(
            "Max Tool Iterations",
            min_value=1,
            max_value=10,
            value=settings.get("max_tool_iterations", 3),
            step=1,
            help="Maximum number of tool calls per query"
        )

    settings["temperature"] = temperature
    settings["max_tokens"] = max_tokens
    settings["top_p"] = top_p
    settings["max_tool_iterations"] = max_tool_iterations

    return settings


def render_retrieval_settings():
    """Render retrieval configuration section."""
    st.subheader("🔍 Retrieval Configuration")

    settings = st.session_state.agent_settings

    retrieval_top_k = st.slider(
        "Retrieval Top K",
        min_value=1,
        max_value=20,
        value=settings.get("retrieval_top_k", 5),
        step=1,
        help="Number of documents to retrieve"
    )

    settings["retrieval_top_k"] = retrieval_top_k

    return settings


def render_enhanced_retrieval_settings():
    """Render enhanced retrieval configuration section (Phase 2)."""
    st.subheader("🚀 Enhanced Retrieval (Phase 2)")

    settings = st.session_state.agent_settings

    with st.expander("检索增强配置"):
        col1, col2 = st.columns(2)

        with col1:
            enable_hybrid = st.checkbox(
                "Enable Hybrid Retrieval",
                value=settings.get("enable_hybrid", True),
                help="Use hybrid retrieval (dense + sparse + RRF)"
            )
            enable_rerank = st.checkbox(
                "Enable Reranking",
                value=settings.get("enable_rerank", False),
                help="Use reranker to improve result ranking"
            )

        with col2:
            enable_query_rewrite = st.checkbox(
                "Enable Query Rewrite",
                value=settings.get("enable_query_rewrite", False),
                help="Rewrite query to improve retrieval"
            )

            # 显示当前状态信息
            if enable_hybrid:
                st.caption("✅ Hybrid: Dense + Sparse + RRF")
            else:
                st.caption("⚠️ Hybrid: Dense only")

            if enable_rerank:
                st.caption("✅ Rerank: Enabled")
            else:
                st.caption("⚠️ Rerank: Disabled")

        settings["enable_hybrid"] = enable_hybrid
        settings["enable_rerank"] = enable_rerank
        settings["enable_query_rewrite"] = enable_query_rewrite

    return settings


def render_reflection_settings():
    """Render reflection mechanism configuration section (Phase 3)."""
    st.subheader("🧠 Reflection Mechanism (Phase 3)")

    settings = st.session_state.agent_settings

    with st.expander("反思机制配置"):
        st.info("反思机制使 Agent 能够自我评估检索结果质量，并在需要时进行多轮迭代优化。")

        col1, col2 = st.columns(2)

        with col1:
            enable_reflection = st.checkbox(
                "Enable Reflection",
                value=settings.get("enable_reflection", True),
                help="Enable self-evaluation of retrieval results"
            )
            max_iterations = st.number_input(
                "Max Iterations",
                min_value=1,
                max_value=10,
                value=settings.get("max_iterations", 3),
                step=1,
                help="Maximum number of reflection loops"
            )

        with col2:
            reflection_timeout = st.number_input(
                "Reflection Timeout (seconds)",
                min_value=10,
                max_value=120,
                value=settings.get("reflection_timeout", 30),
                step=5,
                help="Timeout for reflection node LLM call"
            )

            # 显示当前状态
            if enable_reflection:
                st.caption("✅ Reflection: Enabled")
                st.caption(f"🔄 Max Iterations: {max_iterations}")
                st.caption(f"⏱️ Timeout: {reflection_timeout}s")
            else:
                st.caption("⚠️ Reflection: Disabled")

        settings["enable_reflection"] = enable_reflection
        settings["max_iterations"] = max_iterations
        settings["reflection_timeout"] = reflection_timeout

    return settings


def render_ui_settings():
    """Render UI configuration section."""
    st.subheader("🖥️ UI Configuration")

    settings = st.session_state.agent_settings

    enable_citations = st.checkbox(
        "Enable Citations",
        value=settings.get("enable_citations", True),
        help="Show source citations in responses"
    )

    show_tool_steps = st.checkbox(
        "Show Tool Steps",
        value=settings.get("show_tool_steps", True),
        help="Display tool execution steps in chat"
    )

    settings["enable_citations"] = enable_citations
    settings["show_tool_steps"] = show_tool_steps

    return settings


def render_advanced_settings():
    """Render advanced configuration section."""
    st.subheader("⚡ Advanced")

    settings = st.session_state.agent_settings

    with st.expander("Vector Store Settings"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Provider:** chroma")
            st.markdown("**Collection:** knowledge_hub")
        with col2:
            st.markdown("**Embedding:** azure/text-embedding-ada-002")
            # 动态显示 rerank 状态
            rerank_status = "enabled" if settings.get("enable_rerank", False) else "disabled"
            st.markdown(f"**Reranker:** {rerank_status}")

    with st.expander("Phase 2 Enhancement Status"):
        col1, col2 = st.columns(2)
        with col1:
            hybrid_status = "✅ Enabled" if settings.get("enable_hybrid", True) else "❌ Disabled"
            rerank_status = "✅ Enabled" if settings.get("enable_rerank", False) else "❌ Disabled"
            rewrite_status = "✅ Enabled" if settings.get("enable_query_rewrite", False) else "❌ Disabled"
            st.markdown(f"**Hybrid Retrieval:** {hybrid_status}")
            st.markdown(f"**Reranking:** {rerank_status}")
        with col2:
            st.markdown(f"**Query Rewrite:** {rewrite_status}")
            st.markdown(f"**Structured Parsing:** ✅ Enabled")

    with st.expander("Phase 3 Reflection Status"):
        col1, col2 = st.columns(2)
        with col1:
            reflection_status = "✅ Enabled" if settings.get("enable_reflection", True) else "❌ Disabled"
            st.markdown(f"**Reflection:** {reflection_status}")
            st.markdown(f"**Max Iterations:** {settings.get('max_iterations', 3)}")
        with col2:
            st.markdown(f"**Timeout:** {settings.get('reflection_timeout', 30)}s")
            st.markdown(f"**Loop Retrieval:** {'✅ Enabled' if settings.get('enable_reflection', True) else '❌ Disabled'}")

    with st.expander("Logging Settings"):
        log_level = st.selectbox(
            "Log Level",
            ["DEBUG", "INFO", "WARNING", "ERROR"],
            index=1,
            help="Logging verbosity"
        )
        st.session_state.log_level = log_level


def save_settings():
    """Save settings to session state."""
    st.session_state.agent_settings = st.session_state.agent_settings
    st.success("✅ Settings saved!")


def render_settings_form():
    """Render the complete settings form."""
    init_settings_session()

    settings = st.session_state.agent_settings
    settings = render_model_settings()
    settings = render_retrieval_settings()
    settings = render_enhanced_retrieval_settings()
    settings = render_reflection_settings()  # 新增 Phase 3 反思机制配置
    settings = render_ui_settings()
    render_advanced_settings()

    st.session_state.agent_settings = settings

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("💾 Save Settings", type="primary"):
            save_settings()
    with col2:
        if st.button("🔄 Reset to Defaults"):
            st.session_state.agent_settings = get_default_settings()
            st.rerun()


def main():
    """Main settings page."""
    render_settings_header()
    render_settings_form()


if __name__ == "__main__":
    main()
