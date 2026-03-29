"""RAG tool for Agent."""

from typing import Any, Dict, List

from .base import BaseTool, ToolInput, ToolOutput
from ..adapters.rag_adapter import get_rag_adapter
from ..infra.logging import get_logger


logger = get_logger(__name__)


class RagTool(BaseTool):
    """Tool for searching the knowledge base."""

    def __init__(self):
        super().__init__(
            name="rag_search",
            description="Search the knowledge base for relevant information",
            input_schema={
                "query": {"type": "string", "required": True},
                "top_k": {"type": "integer", "required": False, "default": 5}
            }
        )
        self._rag_adapter = get_rag_adapter()

    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """Execute the RAG search."""
        query = tool_input.query
        top_k = tool_input.top_k or 5
        
        logger.info(f"RAG search: query={query}, top_k={top_k}")

        try:
            results = self._rag_adapter.search(query, top_k=top_k)

            if not results:
                return ToolOutput(
                    success=True,
                    result={"results": [], "summary": "No relevant information found."}
                )

            formatted_results = []
            for idx, result in enumerate(results, 1):
                formatted_results.append({
                    "index": idx,
                    "title": result.title,
                    "text": result.text,
                    "source": result.source,
                    "score": result.score
                })

            return ToolOutput(
                success=True,
                result={
                    "results": formatted_results,
                    "count": len(formatted_results)
                }
            )
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return ToolOutput(success=False, result=None, error=str(e))


def search_knowledge_base(query: str, top_k: int = 5) -> List[Any]:
    """Search the knowledge base."""
    adapter = get_rag_adapter()
    return adapter.search(query, top_k=top_k)
