"""Memory store for Agent.

Low-level SQLite operations for memory storage.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from ..infra.db import get_connection
from ..infra.logging import get_logger


logger = get_logger(__name__)


class MemoryStore:
    """Low-level memory storage using SQLite."""

    def __init__(self):
        self._init_tables()

    def _init_tables(self) -> None:
        """Initialize memory tables."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS short_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session ON short_term_memory(session_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created ON short_term_memory(created_at)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user ON long_term_memory(user_id)
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_key ON long_term_memory(user_id, preference_key)
        """)

        conn.commit()
        logger.info("Memory tables initialized")

    def insert_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> int:
        """Insert a message into short-term memory."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO short_term_memory (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, role, content)
        )

        conn.commit()
        return cursor.lastrowid

    def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent messages for a session."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, role, content, created_at
            FROM short_term_memory
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit)
        )

        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "role": r[1],
                "content": r[2],
                "created_at": r[3]
            }
            for r in reversed(rows)
        ]

    def clear_session(self, session_id: str) -> int:
        """Clear all messages for a session."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM short_term_memory WHERE session_id = ?",
            (session_id,)
        )

        conn.commit()
        return cursor.rowcount

    def set_preference(
        self,
        user_id: str,
        preference_key: str,
        preference_value: str
    ) -> None:
        """Set a user preference."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO long_term_memory (user_id, preference_key, preference_value, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, preference_key)
            DO UPDATE SET preference_value = excluded.preference_value,
                          updated_at = datetime('now')
            """,
            (user_id, preference_key, preference_value)
        )

        conn.commit()
        logger.info(f"Set preference: {user_id}.{preference_key}")

    def get_preference(
        self,
        user_id: str,
        preference_key: str
    ) -> Optional[str]:
        """Get a user preference."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT preference_value
            FROM long_term_memory
            WHERE user_id = ? AND preference_key = ?
            """,
            (user_id, preference_key)
        )

        row = cursor.fetchone()
        return row[0] if row else None

    def get_all_preferences(
        self,
        user_id: str
    ) -> Dict[str, str]:
        """Get all preferences for a user."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT preference_key, preference_value
            FROM long_term_memory
            WHERE user_id = ?
            """,
            (user_id,)
        )

        rows = cursor.fetchall()
        return {r[0]: r[1] for r in rows}


_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get the singleton memory store."""
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
