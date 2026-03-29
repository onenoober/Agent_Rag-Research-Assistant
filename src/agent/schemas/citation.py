"""
Citation schemas for Agent.

Defines citation-related models.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CitationChunk:
    """Citation chunk model."""

    chunk_id: str
    text: str
    source: str
    title: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source": self.source,
            "title": self.title,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class Citation:
    """Citation model with index."""

    index: int
    chunk: CitationChunk

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "index": self.index,
            "chunk": self.chunk.to_dict(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        return f"[{self.index}] {self.chunk.title}\n  来源: {self.chunk.source}\n  相关度: {self.chunk.score:.2%}"

    def to_reference(self) -> str:
        """Convert to inline reference."""
        return f"[{self.index}]"


@dataclass
class CitationCollection:
    """Collection of citations."""

    citations: List[Citation] = field(default_factory=list)

    def add(self, citation: Citation) -> None:
        """Add a citation."""
        self.citations.append(citation)

    def to_list(self) -> List[Dict[str, Any]]:
        """Convert to list of dicts."""
        return [c.to_dict() for c in self.citations]

    def to_references(self) -> str:
        """Convert to inline references."""
        return "".join([c.to_reference() for c in self.citations])

    def to_text(self) -> str:
        """Convert to text format with all citations."""
        if not self.citations:
            return ""
        lines = ["\n\n参考资料:\n"]
        for citation in self.citations:
            lines.append(citation.to_markdown())
        return "\n".join(lines)
