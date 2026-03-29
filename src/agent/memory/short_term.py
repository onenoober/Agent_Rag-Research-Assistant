"""Short-term memory for Agent.

Session-based conversation memory.
"""

from typing import Any, Dict, List, Optional

from .store import get_memory_store
from ..infra.logging import get_logger


logger = get_logger(__name__)


class ShortTermMemory:
    """Short-term memory for conversation history."""

    def __init__(self):
        self._store = get_memory_store()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> int:
        """Add a message to session history."""
        logger.info(f"Adding message to session {session_id}: {role}")
        return self._store.insert_message(session_id, role, content)

    def get_recent(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent messages for a session."""
        return self._store.get_recent_messages(session_id, limit)

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> str:
        """Get formatted conversation history."""
        messages = self.get_recent(session_id, limit)

        if not messages:
            return ""

        parts = []
        for msg in messages:
            parts.append(f"{msg['role']}: {msg['content']}")

        return "\n".join(parts)

    def clear(self, session_id: str) -> int:
        """Clear session history."""
        logger.info(f"Clearing session {session_id}")
        return self._store.clear_session(session_id)


_short_term_memory: Optional[ShortTermMemory] = None


def get_short_term_memory() -> ShortTermMemory:
    """Get the singleton short-term memory."""
    global _short_term_memory
    if _short_term_memory is None:
        _short_term_memory = ShortTermMemory()
    return _short_term_memory
