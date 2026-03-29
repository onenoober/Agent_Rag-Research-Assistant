"""
Database module for Agent.

Manages SQLite connections and table creation.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from .config import get_agent_runtime_settings
from .logging import get_logger


logger = get_logger(__name__)

_db_connection: Optional[sqlite3.Connection] = None


def get_db_path() -> Path:
    """Get database path from settings."""
    settings = get_agent_runtime_settings()
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def init_db() -> sqlite3.Connection:
    """
    Initialize database connection.

    Returns:
        sqlite3.Connection: Database connection
    """
    global _db_connection

    if _db_connection is not None:
        return _db_connection

    db_path = get_db_path()
    logger.info(f"Initializing database at {db_path}")

    _db_connection = sqlite3.connect(str(db_path), check_same_thread=False)
    _db_connection.row_factory = sqlite3.Row

    create_tables()

    logger.info("Database initialized successfully")
    return _db_connection


def get_connection() -> sqlite3.Connection:
    """
    Get database connection.

    Returns:
        sqlite3.Connection: Database connection
    """
    global _db_connection

    if _db_connection is None:
        return init_db()

    return _db_connection


@contextmanager
def get_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """
    Get database cursor with automatic commit/rollback.

    Yields:
        sqlite3.Cursor: Database cursor
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        cursor.close()


def create_tables() -> None:
    """Create necessary tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_calls TEXT,
            citations TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            preferences TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_history_session
        ON chat_history(session_id, created_at)
    """)

    conn.commit()
    cursor.close()

    logger.info("Database tables created successfully")


def close_db() -> None:
    """Close database connection."""
    global _db_connection

    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
        logger.info("Database connection closed")
