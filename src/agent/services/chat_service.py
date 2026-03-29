"""Chat service for Agent."""

import asyncio
from typing import Optional
from dataclasses import dataclass

from ..schemas.chat import ChatRequest, ChatResponse, CitationItemSchema
from ..graph.builder import get_agent_graph
from ..memory.manager import get_memory_manager
from ..adapters.citation_adapter import get_citation_adapter
from ..adapters.settings_adapter import get_agent_config
from ..infra.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ChatResult:
    """Result from chat operation."""
    answer: str
    citations: Optional[list] = None
    tool_steps: Optional[list] = None


class ChatService:
    """Service for handling chat operations."""

    def __init__(self, enable_reflection: Optional[bool] = None):
        # 如果没有显式传入配置，则从全局配置读取
        if enable_reflection is None:
            try:
                config = get_agent_config()
                enable_reflection = config.enable_reflection
            except Exception:
                enable_reflection = True  # 默认启用

        self._enable_reflection = enable_reflection
        # 移除 force_recreate=True，改为按配置复用 Graph
        # 只有当配置变化时才重建 Graph
        self._graph = get_agent_graph(enable_reflection=enable_reflection)
        self._memory_manager = get_memory_manager()
        self._citation_adapter = get_citation_adapter()
        logger.info(f"ChatService initialized with enable_reflection={enable_reflection}")

    async def chat(
        self,
        query: str,
        session_id: str = "default",
        user_id: str = "default_user"
    ) -> ChatResponse:
        """Process a chat request asynchronously."""
        logger.info(f"Chat request: {query}, session: {session_id}")

        conversation_history = self._memory_manager.get_conversation_history(
            session_id=session_id,
            limit=10
        )

        initial_state = {
            "messages": [],
            "retrieved_docs": [],
            "tool_calls": [],
        }

        # 直接调用异步方法，不再需要 asyncio.run()
        result = await self._graph.run(query, session_id, **initial_state)

        answer = result.get("answer", "I couldn't process your request.")

        # 将同步的内存操作放到线程池中执行
        await asyncio.to_thread(
            self._memory_manager.add_message,
            session_id=session_id,
            role="user",
            content=query
        )
        await asyncio.to_thread(
            self._memory_manager.add_message,
            session_id=session_id,
            role="assistant",
            content=answer
        )

        retrieved_docs = result.get("retrieved_docs", [])

        if retrieved_docs:
            from ..adapters.citation_adapter import CitationAdapter, CitationItem

            citation_items = []
            for doc in retrieved_docs:
                if hasattr(doc, 'to_dict'):
                    citation_items.append(CitationItem(
                        index=len(citation_items) + 1,
                        chunk_id=getattr(doc, 'chunk_id', ''),
                        text=getattr(doc, 'text', ''),
                        source=getattr(doc, 'source', ''),
                        title=getattr(doc, 'title', 'Unknown'),
                        score=getattr(doc, 'score', 0.0),
                        metadata=getattr(doc, 'metadata', {})
                    ))

            if citation_items:
                CitationAdapter.format_response_with_citations(
                    response=answer,
                    citations=citation_items,
                    citation_style="text"
                )
                citation_objects = [
                    CitationItemSchema(
                        index=i+1,
                        chunk_id=getattr(doc, 'chunk_id', ''),
                        text=getattr(doc, 'text', ''),
                        source=getattr(doc, 'source', ''),
                        title=getattr(doc, 'title', 'Unknown'),
                        score=getattr(doc, 'score', 0.0),
                        page_no=getattr(doc, 'metadata', {}).get('page_no') if hasattr(doc, 'metadata') else None,
                        section_title=getattr(doc, 'metadata', {}).get('section_title') if hasattr(doc, 'metadata') else None
                    )
                    for i, doc in enumerate(retrieved_docs)
                ]
            else:
                citation_objects = []
        else:
            citation_objects = []

        return ChatResponse(
            answer=answer,
            citations=citation_objects,
            session_id=session_id
        )
