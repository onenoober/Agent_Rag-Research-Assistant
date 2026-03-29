"""
Retrieval schema definitions for agent-level retrieval operations.

This module defines the unified data structures for retrieval operations,
including request/result objects and rewrite/rerank results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetrievalRequest:
    """Request object for retrieval operations."""

    query: str
    top_k: int = 10
    session_id: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    enable_rewrite: bool = False
    enable_hybrid: bool = True
    enable_rerank: bool = False


@dataclass
class RetrievalCandidate:
    """Single retrieval candidate with metadata."""

    chunk_id: str
    text: str
    score: float
    source: str = ""
    title: str = ""
    page_no: Optional[int] = None
    section_title: Optional[str] = None
    content_type: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Unified retrieval result with debug information."""

    candidates: List[RetrievalCandidate] = field(default_factory=list)
    total_hits: int = 0
    query_time_ms: float = 0.0
    debug_trace: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "candidates": [
                {
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "score": c.score,
                    "source": c.source,
                    "title": c.title,
                    "page_no": c.page_no,
                    "section_title": c.section_title,
                    "content_type": c.content_type,
                    "metadata": c.metadata,
                }
                for c in self.candidates
            ],
            "total_hits": self.total_hits,
            "query_time_ms": self.query_time_ms,
            "debug_trace": self.debug_trace,
        }


@dataclass
class RewriteResult:
    """Result of query rewrite operation."""

    original_query: str
    rewritten_queries: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    rewrite_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "original_query": self.original_query,
            "rewritten_queries": self.rewritten_queries,
            "keywords": self.keywords,
            "filters": self.filters,
            "rewrite_time_ms": self.rewrite_time_ms,
        }


@dataclass
class RerankResult:
    """Result of rerank operation."""

    candidates: List[RetrievalCandidate] = field(default_factory=list)
    rerank_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "candidates": [
                {
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "score": c.score,
                    "source": c.source,
                    "title": c.title,
                    "page_no": c.page_no,
                    "section_title": c.section_title,
                }
                for c in self.candidates
            ],
            "rerank_time_ms": self.rerank_time_ms,
        }


@dataclass
class RetrievalConfig:
    """Configuration for enhanced retrieval."""

    enable_query_rewrite: bool = False
    enable_hybrid: bool = True
    enable_rerank: bool = False
    dense_top_k: int = 20
    sparse_top_k: int = 20
    fusion_top_k: int = 10
    rerank_top_k: int = 5

    @classmethod
    def from_settings(cls, settings: Any) -> "RetrievalConfig":
        """Create config from settings object."""
        config = cls()

        retrieval_config = getattr(settings, "retrieval", None)
        if retrieval_config:
            config.dense_top_k = getattr(retrieval_config, "dense_top_k", 20)
            config.sparse_top_k = getattr(retrieval_config, "sparse_top_k", 20)
            config.fusion_top_k = getattr(retrieval_config, "fusion_top_k", 10)

        rerank_config = getattr(settings, "rerank", None)
        if rerank_config:
            config.enable_rerank = getattr(rerank_config, "enabled", False)
            config.rerank_top_k = getattr(rerank_config, "top_k", 5)

        return config
