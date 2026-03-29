"""
Citation adapter for Agent.

Converts retrieval results to unified citation structure.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Optional

from .rag_adapter import SearchResult


@dataclass
class CitationItem:
    """Unified citation item for agent responses."""

    index: int
    chunk_id: str
    text: str
    source: str
    title: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "index": self.index,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source": self.source,
            "title": self.title,
            "score": round(self.score, 4),
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format citation."""
        return f"[{self.index}] {self.title}\n  来源: {self.source}\n  相关度: {self.score:.2%}"

    def to_reference(self) -> str:
        """Convert to inline reference format."""
        return f"[{self.index}]"


class CitationAdapter:
    """Adapter for formatting citations."""

    @staticmethod
    def from_search_results(results: List[SearchResult]) -> List[CitationItem]:
        """
        Convert search results to citation items.

        Args:
            results: List of SearchResult objects

        Returns:
            List of CitationItem objects
        """
        citations = []
        for idx, result in enumerate(results, start=1):
            citation = CitationItem(
                index=idx,
                chunk_id=result.chunk_id,
                text=result.text,
                source=result.source,
                title=result.title or "Unknown",
                score=result.score,
                metadata=result.metadata,
            )
            citations.append(citation)

        return citations

    @staticmethod
    def to_citation_text(citations: List[CitationItem]) -> str:
        """
        Convert citations to text format.

        Args:
            citations: List of CitationItem objects

        Returns:
            Formatted citation text
        """
        if not citations:
            return ""

        lines = ["\n\n参考资料:\n"]
        for citation in citations:
            lines.append(citation.to_markdown())

        return "\n".join(lines)

    @staticmethod
    def to_inline_references(citations: List[CitationItem]) -> str:
        """
        Convert citations to inline reference format.

        Args:
            citations: List of CitationItem objects

        Returns:
            Inline references like [1][2]
        """
        if not citations:
            return ""

        return "".join([citation.to_reference() for citation in citations])

    @staticmethod
    def format_response_with_citations(
        response: str,
        citations: List[CitationItem],
        citation_style: str = "inline"
    ) -> str:
        """
        Format response with citations.

        Args:
            response: Original response text
            citations: List of CitationItem objects
            citation_style: Style of citation (inline, text, both)

        Returns:
            Formatted response with citations
        """
        if not citations:
            return response

        references = CitationAdapter.to_inline_references(citations)

        if citation_style == "inline":
            return f"{response} {references}"
        elif citation_style == "text":
            citation_text = CitationAdapter.to_citation_text(citations)
            return f"{response}{citation_text}"
        elif citation_style == "both":
            citation_text = CitationAdapter.to_citation_text(citations)
            return f"{response} {references}{citation_text}"
        else:
            return response


_citation_adapter: Optional[CitationAdapter] = None


def get_citation_adapter() -> CitationAdapter:
    """Get the singleton citation adapter."""
    global _citation_adapter
    if _citation_adapter is None:
        _citation_adapter = CitationAdapter()
    return _citation_adapter
