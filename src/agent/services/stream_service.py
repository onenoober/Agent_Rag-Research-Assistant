"""Stream service for Agent."""

import asyncio
import json
from typing import AsyncGenerator, Any, Dict, Optional
from dataclasses import asdict

from ..schemas.chat import ChatResponse
from ..infra.logging import get_logger


logger = get_logger(__name__)


class StreamEvent:
    """Stream event types."""
    START = "start"
    TOOL_STEP = "tool_step"
    TOKEN = "token"
    CITATION = "citation"
    DONE = "done"
    ERROR = "error"


class StreamService:
    """Service for handling streaming responses."""

    async def stream_chat(
        self,
        query: str,
        session_id: str = "default",
        user_id: str = "default_user"
    ) -> AsyncGenerator[str, None]:
        """Stream a chat response asynchronously."""
        from ..services.chat_service import ChatService

        yield self._make_event(StreamEvent.START, {"query": query})

        try:
            chat_service = ChatService()

            # 使用 await 调用异步方法
            response = await chat_service.chat(
                query=query,
                session_id=session_id,
                user_id=user_id
            )

            # 模拟流式输出
            words = response.answer.split()
            for word in words:
                yield self._make_event(StreamEvent.TOKEN, {"token": word + " "})
                # 添加小延迟模拟流式效果
                await asyncio.sleep(0.01)

            if response.citations:
                yield self._make_event(
                    StreamEvent.CITATION,
                    {"citations": [c.model_dump() for c in response.citations]}
                )

            yield self._make_event(StreamEvent.DONE, {"session_id": session_id})

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield self._make_event(StreamEvent.ERROR, {"error": str(e)})

    async def _tokenize(self, text: str) -> AsyncGenerator[str, None]:
        """Simple token generator."""
        words = text.split()
        for word in words:
            yield word + " "

    def _make_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """Create a stream event."""
        return json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
