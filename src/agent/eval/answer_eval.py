"""Answer evaluation metrics for agent-level evaluation.

This module provides answer evaluation capabilities including:
- Answer length statistics
- Citation count statistics
- Keyword coverage statistics
- Rule-based completeness scoring
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class AnswerEvalResult:
    """Result of answer evaluation for a single query.

    Attributes:
        query: The test query.
        answer_length: Length of the answer in characters.
        answer_word_count: Number of words in the answer.
        citation_count: Number of citations in the answer.
        keyword_coverage: Keyword coverage ratio (0-1).
        completeness_score: Rule-based completeness score (0-1).
        missing_keywords: List of missing keywords.
        metrics: Additional metrics dictionary.
    """

    query: str
    answer_length: int = 0
    answer_word_count: int = 0
    citation_count: int = 0
    keyword_coverage: float = 0.0
    completeness_score: float = 0.0
    missing_keywords: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "query": self.query,
            "answer_length": self.answer_length,
            "answer_word_count": self.answer_word_count,
            "citation_count": self.citation_count,
            "keyword_coverage": round(self.keyword_coverage, 4),
            "completeness_score": round(self.completeness_score, 4),
            "missing_keywords": self.missing_keywords,
            "metrics": self.metrics,
        }


@dataclass
class AnswerEvalSummary:
    """Aggregated answer evaluation summary.

    Attributes:
        total_queries: Total number of queries evaluated.
        avg_answer_length: Average answer length.
        avg_citation_count: Average citation count.
        avg_keyword_coverage: Average keyword coverage.
        avg_completeness_score: Average completeness score.
        query_results: Per-query results.
    """

    total_queries: int = 0
    avg_answer_length: float = 0.0
    avg_citation_count: float = 0.0
    avg_keyword_coverage: float = 0.0
    avg_completeness_score: float = 0.0
    query_results: List[AnswerEvalResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "total_queries": self.total_queries,
            "avg_answer_length": round(self.avg_answer_length, 2),
            "avg_citation_count": round(self.avg_citation_count, 2),
            "avg_keyword_coverage": round(self.avg_keyword_coverage, 4),
            "avg_completeness_score": round(self.avg_completeness_score, 4),
            "query_results": [r.to_dict() for r in self.query_results],
        }


class AnswerEvaluator:
    """Evaluates generated answers against expected criteria.

    Example:
        evaluator = AnswerEvaluator()
        result = evaluator.evaluate(
            query="What is machine learning?",
            answer="Machine learning is a subset of artificial intelligence...",
            expected_keywords=["machine learning", "artificial intelligence", "algorithm"],
        )
    """

    CITATION_PATTERNS = [
        r"\[(\d+)\]",  # [1], [2], etc.
        r"\[\[(\d+)\]\]",  # [[1]], [[2]], etc.
        r"来源[\s:：]?(\d+)",  # 来源1, 来源:1, etc.
        r"引用[(\d+)]",  # 引用(1), etc.
        r"脚注(\d+)",  # 脚注1, etc.
    ]

    def __init__(self) -> None:
        """Initialize the answer evaluator."""
        self._citation_regexes = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.CITATION_PATTERNS
        ]

    def evaluate(
        self,
        query: str,
        answer: str,
        expected_keywords: Optional[List[str]] = None,
        reference_answer: Optional[str] = None,
    ) -> AnswerEvalResult:
        """Evaluate an answer for a single query.

        Args:
            query: The test query.
            answer: The generated answer.
            expected_keywords: List of expected keywords.
            reference_answer: Reference answer for comparison (optional).

        Returns:
            AnswerEvalResult with metrics.
        """
        result = AnswerEvalResult(query=query)

        if not answer:
            return result

        result.answer_length = len(answer)
        result.answer_word_count = len(answer.split())

        result.citation_count = self._count_citations(answer)

        if expected_keywords:
            (
                result.keyword_coverage,
                result.missing_keywords,
            ) = self._calculate_keyword_coverage(answer, expected_keywords)

        result.completeness_score = self._calculate_completeness(
            query, answer, expected_keywords
        )

        return result

    def _count_citations(self, answer: str) -> int:
        """Count citations in the answer.

        Args:
            answer: The answer text.

        Returns:
            Number of citations found.
        """
        citation_count = set()
        for regex in self._citation_regexes:
            matches = regex.findall(answer)
            citation_count.update(matches)
        return len(citation_count)

    def _calculate_keyword_coverage(
        self, answer: str, expected_keywords: List[str]
    ) -> tuple[float, List[str]]:
        """Calculate keyword coverage.

        Args:
            answer: The answer text.
            expected_keywords: List of expected keywords.

        Returns:
            Tuple of (coverage ratio, list of missing keywords).
        """
        if not expected_keywords:
            return 0.0, []

        answer_lower = answer.lower()
        found_keywords = []
        missing_keywords = []

        for keyword in expected_keywords:
            if keyword.lower() in answer_lower:
                found_keywords.append(keyword)
            else:
                missing_keywords.append(keyword)

        coverage = len(found_keywords) / len(expected_keywords)
        return coverage, missing_keywords

    def _calculate_completeness(
        self,
        query: str,
        answer: str,
        expected_keywords: Optional[List[str]] = None,
    ) -> float:
        """Calculate rule-based completeness score.

        The score is based on:
        - Answer has minimum length (not empty)
        - Answer is not just a repeat of the query
        - Keyword coverage
        - Contains structure (sentences, not just fragments)

        Args:
            query: The test query.
            answer: The generated answer.
            expected_keywords: List of expected keywords.

        Returns:
            Completeness score between 0 and 1.
        """
        if not answer:
            return 0.0

        score = 0.0

        if len(answer) >= 50:
            score += 0.2

        if len(answer.split(".")) >= 2:
            score += 0.2

        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        if len(answer_words - query_words) >= 10:
            score += 0.2

        if expected_keywords:
            coverage, _ = self._calculate_keyword_coverage(answer, expected_keywords)
            score += coverage * 0.4
        else:
            score += 0.2

        return min(score, 1.0)

    def evaluate_batch(
        self,
        queries: List[str],
        answers: List[str],
        expected_keywords_list: Optional[List[List[str]]] = None,
        reference_answers: Optional[List[Optional[str]]] = None,
    ) -> AnswerEvalSummary:
        """Evaluate answers for multiple queries.

        Args:
            queries: List of test queries.
            answers: List of generated answers.
            expected_keywords_list: List of expected keywords for each query.
            reference_answers: List of reference answers (optional).

        Returns:
            AnswerEvalSummary with aggregated metrics.
        """
        if expected_keywords_list is None:
            expected_keywords_list = [None] * len(queries)
        if reference_answers is None:
            reference_answers = [None] * len(queries)

        summary = AnswerEvalSummary(total_queries=len(queries))

        for i, query in enumerate(queries):
            result = self.evaluate(
                query=query,
                answer=answers[i],
                expected_keywords=expected_keywords_list[i],
                reference_answer=reference_answers[i],
            )
            summary.query_results.append(result)

        self._aggregate_summary(summary)
        return summary

    def _aggregate_summary(self, summary: AnswerEvalSummary) -> None:
        """Aggregate metrics across all queries.

        Args:
            summary: The summary to aggregate.
        """
        if not summary.query_results:
            return

        total = len(summary.query_results)

        summary.avg_answer_length = sum(
            r.answer_length for r in summary.query_results
        ) / total
        summary.avg_citation_count = sum(
            r.citation_count for r in summary.query_results
        ) / total
        summary.avg_keyword_coverage = sum(
            r.keyword_coverage for r in summary.query_results
        ) / total
        summary.avg_completeness_score = sum(
            r.completeness_score for r in summary.query_results
        ) / total


def evaluate_answer(
    query: str,
    answer: str,
    expected_keywords: Optional[List[str]] = None,
    reference_answer: Optional[str] = None,
) -> AnswerEvalResult:
    """Convenience function to evaluate a single answer.

    Args:
        query: The test query.
        answer: The generated answer.
        expected_keywords: List of expected keywords.
        reference_answer: Reference answer for comparison.

    Returns:
        AnswerEvalResult with metrics.
    """
    evaluator = AnswerEvaluator()
    return evaluator.evaluate(
        query=query,
        answer=answer,
        expected_keywords=expected_keywords,
        reference_answer=reference_answer,
    )
