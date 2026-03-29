"""Long-term memory for Agent.

User preferences and persistent memory.
"""

from typing import Dict, Optional

from .store import get_memory_store
from ..infra.logging import get_logger


logger = get_logger(__name__)


class LongTermMemory:
    """Long-term memory for user preferences."""

    def __init__(self):
        self._store = get_memory_store()

    def set_preference(
        self,
        user_id: str,
        key: str,
        value: str
    ) -> None:
        """Set a user preference."""
        logger.info(f"Setting preference: {user_id}.{key}")
        self._store.set_preference(user_id, key, value)

    def get_preference(
        self,
        user_id: str,
        key: str
    ) -> Optional[str]:
        """Get a user preference."""
        return self._store.get_preference(user_id, key)

    def get_all_preferences(
        self,
        user_id: str
    ) -> Dict[str, str]:
        """Get all preferences for a user."""
        return self._store.get_all_preferences(user_id)

    def delete_preference(
        self,
        user_id: str,
        key: str
    ) -> bool:
        """Delete a user preference."""
        self._store.set_preference(user_id, key, "")
        return True


_long_term_memory: Optional[LongTermMemory] = None


def get_long_term_memory() -> LongTermMemory:
    """Get the singleton long-term memory."""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory
