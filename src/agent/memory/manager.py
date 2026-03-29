"""Optimized memory manager with caching and async support."""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from collections import OrderedDict
from threading import Lock

from ..infra.logging import get_logger
from ..infra.db import get_connection


logger = get_logger(__name__)

# 线程池用于执行同步数据库操作
_db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="memory_db")


@dataclass
class Message:
    """Chat message."""

    role: str
    content: str
    timestamp: Optional[str] = None


class MemoryCache:
    """Simple LRU cache for memory with TTL."""

    def __init__(self, max_size: int = 100, ttl_seconds: float = 60.0):
        self._cache: OrderedDict[str, List[Message]] = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()

    def get(self, key: str) -> Optional[List[Message]]:
        """Get from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                return None

            # 检查 TTL
            if time.time() - self._timestamps.get(key, 0) > self._ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None

            # 移到末尾（LRU）
            self._cache.move_to_end(key)
            return list(self._cache[key])  # 返回副本

    def set(self, key: str, value: List[Message]) -> None:
        """Set cache with TTL."""
        with self._lock:
            # 如果已存在，删除旧的
            if key in self._cache:
                del self._cache[key]

            # 如果达到最大容量，删除最老的
            if len(self._cache) >= self._max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                del self._timestamps[oldest]

            self._cache[key] = list(value)  # 保存副本
            self._timestamps[key] = time.time()

    def invalidate(self, key: str) -> None:
        """Invalidate a cache entry."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]

    def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all cache entries with keys starting with prefix."""
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._cache[key]
                if key in self._timestamps:
                    del self._timestamps[key]

    def clear(self) -> None:
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()


class MemoryManager:
    """Manages conversation memory with caching."""

    def __init__(self):
        self.max_history = 10
        self._cache = MemoryCache(max_size=100, ttl_seconds=60.0)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to session history (synchronous)."""
        logger.info(f"Adding message to session {session_id}: {role}")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO chat_history (session_id, role, content, created_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (session_id, role, content)
            )
            conn.commit()

            # Invalidate cache when new message is added (invalidate all keys for this session)
            self._cache.invalidate_prefix(session_id)

        except Exception as e:
            logger.error(f"Failed to add message: {e}")

    async def add_message_async(self, session_id: str, role: str, content: str) -> None:
        """Add a message to session history (async, uses thread pool)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_db_executor, self.add_message, session_id, role, content)

    def get_history(self, session_id: str, limit: int = 10) -> List[Message]:
        """Get conversation history for a session with caching (synchronous)."""
        cache_key = f"{session_id}:{limit}"

        # Try cache first
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Memory cache hit for {session_id}")
            return cached

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT role, content, created_at
                FROM chat_history
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit)
            )

            rows = cursor.fetchall()
            messages = [Message(role=r[0], content=r[1], timestamp=r[2]) for r in reversed(rows)]

            # Cache the result
            self._cache.set(cache_key, messages)

            return messages

        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    async def get_history_async(self, session_id: str, limit: int = 10) -> List[Message]:
        """Get conversation history for a session with caching (async)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_db_executor, self.get_history, session_id, limit)

    def get_conversation_history(self, session_id: str, limit: int = 10) -> str:
        """Get formatted conversation history string."""
        messages = self.get_history(session_id, limit)

        if not messages:
            return ""

        return "\n".join(f"{msg.role}: {msg.content}" for msg in messages)

    async def get_conversation_history_async(self, session_id: str, limit: int = 10) -> str:
        """Get formatted conversation history string (async)."""
        messages = await self.get_history_async(session_id, limit)
        if not messages:
            return ""
        return "\n".join(f"{msg.role}: {msg.content}" for msg in messages)

    def get_context(self, session_id: str) -> str:
        """Get formatted context from history."""
        return self.get_conversation_history(session_id, self.max_history)

    def clear_history(self, session_id: str) -> None:
        """Clear session history."""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
            conn.commit()

            # Invalidate cache
            self._cache.invalidate_prefix(session_id)

            logger.info(f"Cleared history for session {session_id}")

        except Exception as e:
            logger.error(f"Failed to clear history: {e}")


_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the singleton memory manager."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
