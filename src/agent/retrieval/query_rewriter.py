"""
Query rewriter for agent-level retrieval.

This module provides query rewriting capabilities by wrapping the existing
QueryProcessor from core/query_engine.
"""

import time
from typing import List, Optional

from ..infra.logging import get_logger
from ..schemas.retrieval import RewriteResult
from src.core.query_engine.query_processor import QueryProcessor

logger = get_logger(__name__)


class QueryRewriter:
    """Query rewriter using existing QueryProcessor.

    This class wraps the existing QueryProcessor to provide query rewriting
    capabilities for the agent-level retrieval pipeline.

    Attributes:
        _processor: The underlying QueryProcessor instance
    """

    def __init__(self, processor: Optional[QueryProcessor] = None):
        """Initialize QueryRewriter.

        Args:
            processor: Optional QueryProcessor instance. Creates default if not provided.
        """
        self._processor = processor or QueryProcessor()

    def rewrite(self, query: str) -> RewriteResult:
        """Rewrite a query to improve retrieval.

        This method uses the existing QueryProcessor to:
        - Clean the original query
        - Extract keywords
        - Parse filters

        Args:
            query: Original user query

        Returns:
            RewriteResult containing rewritten query, keywords, and filters
        """
        start_time = time.time()

        if not query or not query.strip():
            return RewriteResult(
                original_query=query or "",
                rewritten_queries=[],
                keywords=[],
                filters={},
                rewrite_time_ms=0.0,
            )

        try:
            # Use existing QueryProcessor
            processed = self._processor.process(query)

            # Build result - currently using single query
            # Can be extended to multi-query rewriting in future
            rewritten_queries = [query]
            if processed.keywords:
                # Optionally generate keyword-enhanced query
                rewritten_queries.append(" ".join(processed.keywords))

            rewrite_time = (time.time() - start_time) * 1000

            return RewriteResult(
                original_query=query,
                rewritten_queries=rewritten_queries,
                keywords=processed.keywords or [],
                filters=processed.filters or {},
                rewrite_time_ms=rewrite_time,
            )

        except Exception as e:
            logger.error(f"Query rewrite failed: {e}")
            # Return original query on failure
            return RewriteResult(
                original_query=query,
                rewritten_queries=[query],
                keywords=[],
                filters={},
                rewrite_time_ms=0.0,
            )

    def extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from a query.

        Args:
            query: Input query

        Returns:
            List of extracted keywords
        """
        processed = self._processor.process(query)
        return processed.keywords or []

    def parse_filters(self, query: str) -> dict:
        """Parse filters from a query.

        Args:
            query: Input query

        Returns:
            Dictionary of parsed filters
        """
        processed = self._processor.process(query)
        return processed.filters or {}
