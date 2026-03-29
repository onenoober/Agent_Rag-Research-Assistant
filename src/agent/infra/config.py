"""
Agent configuration module.

Loads configuration from settings.yaml and provides Agent runtime settings.
"""

from pathlib import Path
from typing import Any, Optional
import yaml


class AgentSettings:
    """Agent configuration settings."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._rag_settings_path = config.get("rag_settings_path", "./config/settings.yaml")

    @property
    def rag_settings_path(self) -> Path:
        """Get RAG settings file path."""
        return Path(self._rag_settings_path)

    @property
    def default_temperature(self) -> float:
        """Get default temperature for LLM."""
        return self.config.get("default_temperature", 0.7)

    @property
    def default_top_p(self) -> float:
        """Get default top_p for LLM."""
        return self.config.get("default_top_p", 0.9)

    @property
    def default_max_tokens(self) -> int:
        """Get default max tokens for LLM."""
        return self.config.get("default_max_tokens", 4096)

    @property
    def default_top_k(self) -> int:
        """Get default top_k for retrieval."""
        return self.config.get("default_top_k", 5)

    @property
    def session_history_limit(self) -> int:
        """Get max number of conversation turns to keep in memory."""
        return self.config.get("session_history_limit", 10)

    @property
    def db_path(self) -> Path:
        """Get SQLite database path."""
        db_path = self.config.get("db_path", "./data/db/agent.db")
        return Path(db_path)

    @property
    def log_level(self) -> str:
        """Get log level."""
        return self.config.get("log_level", "INFO")

    @property
    def log_file(self) -> Optional[Path]:
        """Get log file path."""
        log_file = self.config.get("log_file")
        if log_file:
            return Path(log_file)
        return None

    # ========== 新增：反思机制配置 ==========
    @property
    def enable_reflection(self) -> bool:
        """是否启用反思机制（默认关闭）。"""
        return self.config.get("enable_reflection", False)

    @property
    def max_iterations(self) -> int:
        """最大迭代次数（防止无限循环）。"""
        return self.config.get("max_iterations", 3)

    @property
    def reflection_timeout(self) -> int:
        """反思节点超时时间（秒）。"""
        return self.config.get("reflection_timeout", 30)
    # ========================================


# 配置缓存
_agent_settings_cache: Optional[AgentSettings] = None
_agent_settings_mtime: float = 0


def load_settings() -> AgentSettings:
    """
    Load agent settings from configuration (with caching).

    Returns:
        AgentSettings: Agent configuration object
    """
    global _agent_settings_cache, _agent_settings_mtime
    
    # 修正路径：从 src/agent/infra/config.py 到项目根目录
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "settings.yaml"

    if not config_path.exists():
        return AgentSettings({})

    # 检查缓存
    current_mtime = config_path.stat().st_mtime
    if _agent_settings_cache is not None and _agent_settings_mtime == current_mtime:
        return _agent_settings_cache

    # 重新读取
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    agent_config = config.get("agent", {})
    _agent_settings_cache = AgentSettings(agent_config)
    _agent_settings_mtime = current_mtime
    
    return _agent_settings_cache


def get_rag_settings_path() -> Path:
    """
    Get the RAG settings file path.

    Returns:
        Path: Path to settings.yaml
    """
    settings = load_settings()
    return settings.rag_settings_path


def get_agent_runtime_settings() -> AgentSettings:
    """
    Get agent runtime settings.

    Returns:
        AgentSettings: Agent configuration object
    """
    return load_settings()
