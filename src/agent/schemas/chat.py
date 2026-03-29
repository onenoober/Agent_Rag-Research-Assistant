"""
Chat schemas for Agent.

Defines request/response models for chat API.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChatRequest:
    """Chat request model."""

    query: str
    session_id: str
    user_id: Optional[str] = None
    top_k: int = 5
    temperature: float = 0.7
    stream: bool = False
    use_tools: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "top_k": self.top_k,
            "temperature": self.temperature,
            "stream": self.stream,
            "use_tools": self.use_tools,
            "metadata": self.metadata,
        }


@dataclass
class ToolStep:
    """Tool execution step."""

    tool_name: str
    input: Dict[str, Any]
    output: Optional[str] = None
    status: str = "pending"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class CitationItemSchema:
    """Citation item schema."""

    index: int
    chunk_id: str
    text: str
    source: str
    title: str
    score: float
    page_no: Optional[int] = None
    section_title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "index": self.index,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source": self.source,
            "title": self.title,
            "score": self.score,
        }
        if self.page_no is not None:
            result["page_no"] = self.page_no
        if self.section_title is not None:
            result["section_title"] = self.section_title
        return result


@dataclass
class ChatResponse:
    """Chat response model."""

    answer: str
    session_id: str
    citations: List[CitationItemSchema] = field(default_factory=list)
    tool_steps: List[ToolStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "answer": self.answer,
            "session_id": self.session_id,
            "citations": [c.to_dict() for c in self.citations],
            "tool_steps": [t.to_dict() for t in self.tool_steps],
            "metadata": self.metadata,
        }
