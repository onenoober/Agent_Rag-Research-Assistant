"""Retrieval evaluation metrics for agent-level evaluation.

This module provides retrieval evaluation capabilities including:
- Recall@k
- Hit@k
- MRR (Mean Reciprocal Rank)
- Citation hit statistics
- Page number hit statistics (Phase 2 enhancement)
- Section title hit statistics (Phase 2 enhancement)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class RetrievalCandidate:
    """A retrieved candidate result.

    Attributes:
        chunk_id: Unique identifier for the chunk.
        text: Text content of the chunk.
        source: Source file name.
        page_no: Page number (optional, from Phase 2).
        section_title: Section title (optional, from Phase 2).
        score: Retrieval score (optional).
    """

    chunk_id: str
    text: str
    source: Optional[str] = None
    page_no: Optional[int] = None
    section_title: Optional[str] = None
    score: Optional[float] = None


@dataclass
class RetrievalEvalResult:
    """Result of retrieval evaluation for a single query.

    Attributes:
        query: The test query.
        recall_at_k: Recall@k metric.
        hit_at_k: Hit@k metric.
        mrr: Mean Reciprocal Rank (if calculated).
        source_hits: Number of source hits.
        page_no_hits: Number of page number hits (Phase 2).
        section_title_hits: Number of section title hits (Phase 2).
        retrieved_count: Total number of retrieved chunks.
        expected_count: Total number of expected chunks.
        metrics: Additional metrics dictionary.
    """

    query: str
    recall_at_k: float = 0.0
    hit_at_k: float = 0.0
    mrr: float = 0.0
    source_hits: int = 0
    page_no_hits: int = 0
    section_title_hits: int = 0
    retrieved_count: int = 0
    expected_count: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "query": self.query,
            "recall_at_k": round(self.recall_at_k, 4),
            "hit_at_k": round(self.hit_at_k, 4),
            "mrr": round(self.mrr, 4),
            "source_hits": self.source_hits,
            "page_no_hits": self.page_no_hits,
            "section_title_hits": self.section_title_hits,
            "retrieved_count": self.retrieved_count,
            "expected_count": self.expected_count,
            "metrics": self.metrics,
        }


@dataclass
class RetrievalEvalSummary:
    """Aggregated retrieval evaluation summary.

    Attributes:
        total_queries: Total number of queries evaluated.
        avg_recall_at_k: Average Recall@k across all queries.
        avg_hit_at_k: Average Hit@k across all queries.
        avg_mrr: Average MRR across all queries.
        total_source_hits: Total source hits.
        total_page_no_hits: Total page number hits.
        total_section_title_hits: Total section title hits.
        query_results: Per-query results.
    """

    total_queries: int = 0
    avg_recall_at_k: float = 0.0
    avg_hit_at_k: float = 0.0
    avg_mrr: float = 0.0
    total_source_hits: int = 0
    total_page_no_hits: int = 0
    total_section_title_hits: int = 0
    query_results: List[RetrievalEvalResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "total_queries": self.total_queries,
            "avg_recall_at_k": round(self.avg_recall_at_k, 4),
            "avg_hit_at_k": round(self.avg_hit_at_k, 4),
            "avg_mrr": round(self.avg_mrr, 4),
            "total_source_hits": self.total_source_hits,
            "total_page_no_hits": self.total_page_no_hits,
            "total_section_title_hits": self.total_section_title_hits,
            "query_results": [r.to_dict() for r in self.query_results],
        }


class RetrievalEvaluator:
    """Evaluates retrieval results against expected outcomes.

    Example:
        evaluator = RetrievalEvaluator(k=10)
        result = evaluator.evaluate(
            query="What is machine learning?",
            retrieved=[...],
            expected_chunk_ids=["id1", "id2"],
            expected_sources=["doc1.pdf"],
            expected_page_no=1,
            expected_section_title="Introduction",
        )
    """

    def __init__(self, k: int = 10) -> None:
        """Initialize the retrieval evaluator.

        Args:
            k: The k value for k-precision, k-recall, etc. Defaults to 10.
        """
        self.k = k

    def evaluate(
        self,
        query: str,
        retrieved: List[RetrievalCandidate],
        expected_chunk_ids: Optional[List[str]] = None,
        expected_sources: Optional[List[str]] = None,
        expected_page_no: Optional[int] = None,
        expected_section_title: Optional[str] = None,
    ) -> RetrievalEvalResult:
        """Evaluate retrieval results for a single query.

        Args:
            query: The test query.
            retrieved: List of retrieved candidates.
            expected_chunk_ids: Expected chunk IDs.
            expected_sources: Expected source files.
            expected_page_no: Expected page number.
            expected_section_title: Expected section title.

        Returns:
            RetrievalEvalResult with metrics.
        """
        result = RetrievalEvalResult(query=query)

        if expected_chunk_ids is None:
            expected_chunk_ids = []
        if expected_sources is None:
            expected_sources = []

        retrieved = retrieved[:self.k]
        result.retrieved_count = len(retrieved)
        result.expected_count = len(expected_chunk_ids) + len(expected_sources)

        expected_set: Set[str] = set(expected_chunk_ids)
        retrieved_ids = {self._get_chunk_id(c) for c in retrieved}
        retrieved_sources = {c.source for c in retrieved if c.source}

        if expected_set:
            hits = len(expected_set & retrieved_ids)
            result.recall_at_k = hits / len(expected_set)
            result.hit_at_k = 1.0 if hits > 0 else 0.0

            mrr = self._calculate_mrr(expected_set, retrieved)
            result.mrr = mrr

        if expected_sources:
            source_hits = len(set(expected_sources) & retrieved_sources)
            result.source_hits = source_hits

        if expected_page_no is not None:
            page_no_hits = sum(
                1 for c in retrieved if c.page_no == expected_page_no
            )
            result.page_no_hits = page_no_hits

        if expected_section_title is not None:
            section_title_hits = sum(
                1 for c in retrieved
                if c.section_title and expected_section_title.lower()
                in c.section_title.lower()
            )
            result.section_title_hits = section_title_hits

        return result

    def _get_chunk_id(self, candidate: RetrievalCandidate) -> str:
        """Extract chunk ID from candidate.

        Args:
            candidate: The retrieval candidate.

        Returns:
            Chunk ID string.
        """
        return candidate.chunk_id

    def _calculate_mrr(
        self,
        expected: Set[str],
        retrieved: List[RetrievalCandidate],
    ) -> float:
        """Calculate Mean Reciprocal Rank.

        Args:
            expected: Set of expected chunk IDs.
            retrieved: List of retrieved candidates.

        Returns:
            MRR score.
        """
        for rank, candidate in enumerate(retrieved, start=1):
            if self._get_chunk_id(candidate) in expected:
                return 1.0 / rank
        return 0.0

    def evaluate_batch(
        self,
        queries: List[str],
        retrieved_list: List[List[RetrievalCandidate]],
        expected_chunk_ids_list: Optional[List[List[str]]] = None,
        expected_sources_list: Optional[List[List[str]]] = None,
        expected_page_nos: Optional[List[Optional[int]]] = None,
        expected_section_titles: Optional[List[Optional[str]]] = None,
    ) -> RetrievalEvalSummary:
        """Evaluate retrieval results for multiple queries.

        Args:
            queries: List of test queries.
            retrieved_list: List of retrieved candidates for each query.
            expected_chunk_ids_list: List of expected chunk IDs for each query.
            expected_sources_list: List of expected sources for each query.
            expected_page_nos: List of expected page numbers.
            expected_section_titles: List of expected section titles.

        Returns:
            RetrievalEvalSummary with aggregated metrics.
        """
        if expected_chunk_ids_list is None:
            expected_chunk_ids_list = [None] * len(queries)
        if expected_sources_list is None:
            expected_sources_list = [None] * len(queries)
        if expected_page_nos is None:
            expected_page_nos = [None] * len(queries)
        if expected_section_titles is None:
            expected_section_titles = [None] * len(queries)

        summary = RetrievalEvalSummary(total_queries=len(queries))

        for i, query in enumerate(queries):
            result = self.evaluate(
                query=query,
                retrieved=retrieved_list[i],
                expected_chunk_ids=expected_chunk_ids_list[i],
                expected_sources=expected_sources_list[i],
                expected_page_no=expected_page_nos[i],
                expected_section_title=expected_section_titles[i],
            )
            summary.query_results.append(result)

        self._aggregate_summary(summary)
        return summary

    def _aggregate_summary(self, summary: RetrievalEvalSummary) -> None:
        """Aggregate metrics across all queries.

        Args:
            summary: The summary to aggregate.
        """
        if not summary.query_results:
            return

        total = len(summary.query_results)

        summary.avg_recall_at_k = sum(
            r.recall_at_k for r in summary.query_results
        ) / total
        summary.avg_hit_at_k = sum(
            r.hit_at_k for r in summary.query_results
        ) / total
        summary.avg_mrr = sum(r.mrr for r in summary.query_results) / total
        summary.total_source_hits = sum(
            r.source_hits for r in summary.query_results
        )
        summary.total_page_no_hits = sum(
            r.page_no_hits for r in summary.query_results
        )
        summary.total_section_title_hits = sum(
            r.section_title_hits for r in summary.query_results
        )


def evaluate_retrieval(
    query: str,
    retrieved: List[RetrievalCandidate],
    expected_chunk_ids: Optional[List[str]] = None,
    expected_sources: Optional[List[str]] = None,
    expected_page_no: Optional[int] = None,
    expected_section_title: Optional[str] = None,
    k: int = 10,
) -> RetrievalEvalResult:
    """Convenience function to evaluate a single retrieval result.

    Args:
        query: The test query.
        retrieved: List of retrieved candidates.
        expected_chunk_ids: Expected chunk IDs.
        expected_sources: Expected source files.
        expected_page_no: Expected page number.
        expected_section_title: Expected section title.
        k: The k value for evaluation.

    Returns:
        RetrievalEvalResult with metrics.
    """
    evaluator = RetrievalEvaluator(k=k)
    return evaluator.evaluate(
        query=query,
        retrieved=retrieved,
        expected_chunk_ids=expected_chunk_ids,
        expected_sources=expected_sources,
        expected_page_no=expected_page_no,
        expected_section_title=expected_section_title,
    )
