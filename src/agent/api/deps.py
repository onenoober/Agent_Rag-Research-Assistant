"""API dependencies."""

from ..services.chat_service import ChatService
from ..services.stream_service import StreamService
from ..graph.builder import get_agent_graph
from ..memory.manager import get_memory_manager
from ..adapters.rag_adapter import get_rag_adapter
from ..adapters.ingestion_adapter import get_ingestion_adapter


def get_chat_service() -> ChatService:
    """Get chat service instance."""
    return ChatService()


def get_stream_service() -> StreamService:
    """Get stream service instance."""
    return StreamService()


def get_agent_graph():
    """Get agent graph builder."""
    return AgentGraphBuilder().build()


def get_memory():
    """Get memory manager."""
    return get_memory_manager()


def get_rag():
    """Get RAG adapter."""
    return get_rag_adapter()


def get_ingestion():
    """Get ingestion adapter."""
    return get_ingestion_adapter()
