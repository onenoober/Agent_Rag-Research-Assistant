"""
Settings adapter for Agent.

Reads existing RAG configuration and maps to Agent-specific fields.
"""

from pathlib import Path
from typing import Any, Optional
import yaml

from ..infra.logging import get_logger


logger = get_logger(__name__)

# 配置缓存
_settings_cache: Optional[dict] = None


class AgentConfig:
    """Unified Agent configuration object."""

    def __init__(self, config: dict[str, Any]):
        self._config = config

    @property
    def llm_provider(self) -> str:
        """Get LLM provider."""
        return self._config.get("llm", {}).get("provider", "openai")

    @property
    def llm_model(self) -> str:
        """Get LLM model name."""
        return self._config.get("llm", {}).get("model", "gpt-4o")

    @property
    def llm_base_url(self) -> Optional[str]:
        """Get LLM base URL."""
        return self._config.get("llm", {}).get("base_url")

    @property
    def llm_api_key(self) -> Optional[str]:
        """Get LLM API key."""
        return self._config.get("llm", {}).get("api_key")

    @property
    def llm_temperature(self) -> float:
        """Get LLM temperature."""
        return self._config.get("llm", {}).get("temperature", 0.7)

    @property
    def llm_max_tokens(self) -> int:
        """Get LLM max tokens."""
        return self._config.get("llm", {}).get("max_tokens", 4096)

    @property
    def embedding_provider(self) -> str:
        """Get embedding provider."""
        return self._config.get("embedding", {}).get("provider", "openai")

    @property
    def embedding_model(self) -> str:
        """Get embedding model name."""
        return self._config.get("embedding", {}).get("model", "text-embedding-3-small")

    @property
    def embedding_dimensions(self) -> int:
        """Get embedding dimensions."""
        return self._config.get("embedding", {}).get("dimensions", 1536)

    @property
    def vector_store_provider(self) -> str:
        """Get vector store provider."""
        return self._config.get("vector_store", {}).get("provider", "chroma")

    @property
    def vector_store_path(self) -> str:
        """Get vector store persist directory."""
        return self._config.get("vector_store", {}).get("persist_directory", "./data/db/chroma")

    @property
    def vector_store_collection(self) -> str:
        """Get vector store collection name."""
        return self._config.get("vector_store", {}).get("collection_name", "knowledge_hub")

    @property
    def retrieval_top_k(self) -> int:
        """Get retrieval top_k."""
        return self._config.get("retrieval", {}).get("fusion_top_k", 10)

    @property
    def rerank_enabled(self) -> bool:
        """Get rerank enabled status."""
        return self._config.get("rerank", {}).get("enabled", False)

    @property
    def rerank_top_k(self) -> int:
        """Get rerank top_k."""
        return self._config.get("rerank", {}).get("top_k", 5)

    @property
    def log_level(self) -> str:
        """Get log level."""
        return self._config.get("observability", {}).get("log_level", "INFO")

    @property
    def temperature(self) -> float:
        """Get temperature for chat."""
        return self._config.get("llm", {}).get("temperature", 0.7)

    @property
    def max_tokens(self) -> int:
        """Get max tokens for chat."""
        return self._config.get("llm", {}).get("max_tokens", 2048)

    @property
    def top_p(self) -> float:
        """Get top_p for chat."""
        return self._config.get("llm", {}).get("top_p", 0.9)

    @property
    def max_tool_iterations(self) -> int:
        """Get max tool iterations."""
        return self._config.get("agent", {}).get("max_tool_iterations", 3)

    # ========== Phase 3: 反思机制配置 ==========
    @property
    def enable_reflection(self) -> bool:
        """Get reflection enabled status."""
        return self._config.get("agent", {}).get("enable_reflection", True)

    @property
    def max_iterations(self) -> int:
        """Get max reflection iterations."""
        return self._config.get("agent", {}).get("max_iterations", 3)

    @property
    def reflection_timeout(self) -> int:
        """Get reflection timeout in seconds."""
        return self._config.get("agent", {}).get("reflection_timeout", 30)
    # ============================================

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by key."""
        return self._config.get(key, default)


def read_rag_settings(settings_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Read existing RAG settings from YAML file (with caching).

    Args:
        settings_path: Path to settings file. If None, uses default path.

    Returns:
        dict: RAG configuration
    """
    global _settings_cache
    
    if settings_path is None:
        settings_path = Path(__file__).parent.parent.parent.parent / "config" / "settings.yaml"

    if not settings_path.exists():
        logger.warning(f"Settings file not found: {settings_path}")
        return {}

    # 简单的文件修改时间缓存检查
    import time
    current_mtime = settings_path.stat().st_mtime
    
    if _settings_cache is not None:
        cached_mtime, cached_config = _settings_cache
        if cached_mtime == current_mtime:
            # 文件未修改，使用缓存
            return cached_config

    # 重新读取
    with open(settings_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    _settings_cache = (current_mtime, config)
    logger.info(f"Loaded RAG settings from {settings_path}")
    return config


def map_to_agent_config(rag_config: dict[str, Any]) -> AgentConfig:
    """
    Map RAG configuration to Agent configuration.

    Args:
        rag_config: RAG configuration dict

    Returns:
        AgentConfig: Mapped Agent configuration
    """
    agent_config = {}

    if "llm" in rag_config:
        agent_config["llm"] = rag_config["llm"]

    if "embedding" in rag_config:
        agent_config["embedding"] = rag_config["embedding"]

    if "vector_store" in rag_config:
        agent_config["vector_store"] = rag_config["vector_store"]

    if "retrieval" in rag_config:
        agent_config["retrieval"] = rag_config["retrieval"]

    if "rerank" in rag_config:
        agent_config["rerank"] = rag_config["rerank"]

    if "observability" in rag_config:
        agent_config["observability"] = rag_config["observability"]

    return AgentConfig(agent_config)


def get_agent_config() -> AgentConfig:
    """
    Get Agent configuration from RAG settings.

    Returns:
        AgentConfig: Agent configuration object
    """
    rag_config = read_rag_settings()
    return map_to_agent_config(rag_config)
