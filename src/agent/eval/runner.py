"""Evaluation runner for agent-level evaluation.

This module orchestrates the evaluation process by running retrieval
and answer evaluation on test cases, and generating reports.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.agent.eval.dataset import EvalTestCase, EvalDatasetLoader
from src.agent.eval.retrieval_eval import (
    RetrievalCandidate,
    RetrievalEvaluator,
    RetrievalEvalSummary,
)
from src.agent.eval.answer_eval import AnswerEvaluator, AnswerEvalSummary
from src.agent.eval.reporter import (
    EvalExperimentConfig,
    EvalReporter,
    EvalReport,
)

logger = logging.getLogger(__name__)


@dataclass
class EvalRunResult:
    """Result of an evaluation run.

    Attributes:
        experiment_id: Unique identifier for this experiment.
        config: Experiment configuration.
        retrieval_summary: Retrieval evaluation summary.
        answer_summary: Answer evaluation summary.
        total_elapsed_ms: Total time for the evaluation.
    """

    experiment_id: str
    config: EvalExperimentConfig
    retrieval_summary: Optional[RetrievalEvalSummary] = None
    answer_summary: Optional[AnswerEvalSummary] = None
    total_elapsed_ms: float = 0.0


class AgentEvalRunner:
    """Runs agent-level evaluation on test cases.

    This runner orchestrates:
    1. Loading evaluation test cases
    2. Running retrieval for each query
    3. Optionally generating answers
    4. Evaluating retrieval results
    5. Evaluating generated answers
    6. Generating reports

    Example:
        runner = AgentEvalRunner(
            retriever=hybrid_search,
            answer_generator=llm.generate,
        )
        result = runner.run(
            dataset_path="data/eval/smoke_cases.jsonl",
            top_k=10,
        )
    """

    def __init__(
        self,
        retriever: Any = None,
        answer_generator: Optional[Callable[[str, List[Any]], str]] = None,
        reranker: Any = None,
        settings: Any = None,
    ) -> None:
        """Initialize the evaluation runner.

        Args:
            retriever: Retrieval function or object with search method.
            answer_generator: Optional callable(query, retrieved_chunks) -> str.
            reranker: Optional reranker object.
            settings: Application settings.
        """
        self.retriever = retriever
        self.answer_generator = answer_generator
        self.reranker = reranker
        self.settings = settings

        self.retrieval_evaluator = RetrievalEvaluator(k=10)
        self.answer_evaluator = AnswerEvaluator()
        self.dataset_loader = EvalDatasetLoader()
        self.reporter = EvalReporter()

    def run(
        self,
        dataset_path: str | Path,
        top_k: int = 10,
        dataset_type: str = "smoke",
        enable_query_rewrite: bool = False,
        enable_hybrid: bool = True,
        enable_rerank: bool = False,
        chunk_strategy: str = "default",
        case_ids: Optional[List[str]] = None,
    ) -> EvalRunResult:
        """Run evaluation on the dataset.

        Args:
            dataset_path: Path to the evaluation dataset.
            top_k: Number of chunks to retrieve per query.
            dataset_type: Type of dataset (smoke or dev).
            enable_query_rewrite: Whether to enable query rewrite.
            enable_hybrid: Whether to enable hybrid retrieval.
            enable_rerank: Whether to enable reranking.
            chunk_strategy: Chunk strategy identifier.
            case_ids: Optional list of case IDs to filter.

        Returns:
            EvalRunResult with evaluation results.
        """
        t0 = time.monotonic()

        experiment_id = self.reporter.generate_experiment_id()

        config = EvalExperimentConfig(
            dataset_type=dataset_type,
            top_k=top_k,
            enable_query_rewrite=enable_query_rewrite,
            enable_hybrid=enable_hybrid,
            enable_rerank=enable_rerank,
            chunk_strategy=chunk_strategy,
        )

        logger.info(f"Starting evaluation: {experiment_id}")

        test_cases = self.dataset_loader.load(dataset_path)
        if case_ids:
            test_cases = self.dataset_loader.filter_by_ids(test_cases, case_ids)

        retrieval_results = []
        answers = []

        for tc in test_cases:
            retrieved = self._retrieve(tc.question, top_k, enable_hybrid, enable_rerank)
            retrieval_results.append(retrieved)

            if self.answer_generator:
                answer = self._generate_answer(tc.question, retrieved)
                answers.append(answer)
            else:
                answers.append("")

        retrieval_summary = self._evaluate_retrieval(test_cases, retrieval_results, top_k)
        answer_summary = self._evaluate_answers(
            test_cases, answers
        ) if answers else None

        total_elapsed_ms = (time.monotonic() - t0) * 1000.0

        report = self.reporter.generate_report(
            experiment_id=experiment_id,
            config=config,
            retrieval_summary=retrieval_summary.to_dict() if retrieval_summary else None,
            answer_summary=answer_summary.to_dict() if answer_summary else None,
            total_elapsed_ms=total_elapsed_ms,
        )
        self.reporter.save_report(report)

        logger.info(f"Evaluation complete: {experiment_id}")

        return EvalRunResult(
            experiment_id=experiment_id,
            config=config,
            retrieval_summary=retrieval_summary,
            answer_summary=answer_summary,
            total_elapsed_ms=total_elapsed_ms,
        )

    def _retrieve(
        self,
        query: str,
        top_k: int,
        enable_hybrid: bool,
        enable_rerank: bool,
    ) -> List[RetrievalCandidate]:
        """Retrieve chunks for a query.

        Args:
            query: The search query.
            top_k: Number of results to retrieve.
            enable_hybrid: Whether to use hybrid retrieval.
            enable_rerank: Whether to apply reranking.

        Returns:
            List of RetrievalCandidate.
        """
        if self.retriever is None:
            logger.warning("No retriever configured; returning empty results.")
            return []

        try:
            if hasattr(self.retriever, "search"):
                results = self.retriever.search(query=query, top_k=top_k * 2 if enable_rerank else top_k)
                results = results if isinstance(results, list) else getattr(results, "results", [])
            elif callable(self.retriever):
                results = self.retriever(query, top_k)
            else:
                results = []

            if enable_rerank and self.reranker and results:
                rerank_result = self.reranker.rerank(query=query, results=results, top_k=top_k)
                results = rerank_result.results if hasattr(rerank_result, "results") else rerank_result

            candidates = []
            for r in results[:top_k]:
                candidates.append(self._convert_to_candidate(r))

            return candidates

        except Exception as exc:
            logger.warning(f"Retrieval failed for query '{query[:40]}': {exc}")
            return []

    def _convert_to_candidate(self, result: Any) -> RetrievalCandidate:
        """Convert a retrieval result to RetrievalCandidate.

        Args:
            result: The retrieval result object.

        Returns:
            RetrievalCandidate instance.
        """
        if isinstance(result, RetrievalCandidate):
            return result

        if isinstance(result, dict):
            return RetrievalCandidate(
                chunk_id=str(result.get("id", result.get("chunk_id", ""))),
                text=str(result.get("text", result.get("content", ""))),
                source=result.get("source"),
                page_no=result.get("page_no"),
                section_title=result.get("section_title"),
                score=result.get("score"),
            )

        return RetrievalCandidate(
            chunk_id=str(getattr(result, "id", getattr(result, "chunk_id", str(result)))),
            text=str(getattr(result, "text", getattr(result, "content", str(result)))),
            source=getattr(result, "source", None),
            page_no=getattr(result, "page_no", None),
            section_title=getattr(result, "section_title", None),
            score=getattr(result, "score", None),
        )

    def _generate_answer(self, query: str, chunks: List[RetrievalCandidate]) -> str:
        """Generate an answer from retrieved chunks.

        Args:
            query: The query.
            retrieved: List of retrieved candidates.

        Returns:
            Generated answer string.
        """
        if self.answer_generator is not None:
            try:
                return self.answer_generator(query, [c.text for c in chunks])
            except Exception as exc:
                logger.warning(f"Answer generation failed: {exc}")

        texts = [c.text for c in chunks[:3]]
        return " ".join(texts)

    def _evaluate_retrieval(
        self,
        test_cases: List[EvalTestCase],
        retrieved_list: List[List[RetrievalCandidate]],
        top_k: int,
    ) -> RetrievalEvalSummary:
        """Evaluate retrieval results.

        Args:
            test_cases: List of test cases.
            retrieved_list: List of retrieved candidates for each case.
            top_k: The k value for evaluation.

        Returns:
            RetrievalEvalSummary.
        """
        queries = [tc.question for tc in test_cases]
        expected_chunk_ids = [tc.expected_keywords for tc in test_cases]
        expected_sources = [tc.expected_sources for tc in test_cases]
        expected_page_nos = [tc.expected_page_no for tc in test_cases]
        expected_section_titles = [tc.expected_section_title for tc in test_cases]

        return self.retrieval_evaluator.evaluate_batch(
            queries=queries,
            retrieved_list=retrieved_list,
            expected_chunk_ids_list=None,
            expected_sources_list=expected_sources,
            expected_page_nos=expected_page_nos,
            expected_section_titles=expected_section_titles,
        )

    def _evaluate_answers(
        self,
        test_cases: List[EvalTestCase],
        answers: List[str],
    ) -> AnswerEvalSummary:
        """Evaluate generated answers.

        Args:
            test_cases: List of test cases.
            answers: List of generated answers.

        Returns:
            AnswerEvalSummary.
        """
        queries = [tc.question for tc in test_cases]
        expected_keywords = [tc.expected_keywords for tc in test_cases]
        reference_answers = [tc.reference_answer for tc in test_cases]

        return self.answer_evaluator.evaluate_batch(
            queries=queries,
            answers=answers,
            expected_keywords_list=expected_keywords,
            reference_answers=reference_answers,
        )

    def run_comparison(
        self,
        dataset_path: str | Path,
        configs: List[Dict[str, Any]],
    ) -> List[EvalRunResult]:
        """Run evaluation with multiple configurations for comparison.

        Args:
            dataset_path: Path to the evaluation dataset.
            configs: List of configuration dictionaries.

        Returns:
            List of EvalRunResult for each configuration.
        """
        results = []

        for config in configs:
            result = self.run(
                dataset_path=dataset_path,
                top_k=config.get("top_k", 10),
                dataset_type=config.get("dataset_type", "smoke"),
                enable_query_rewrite=config.get("enable_query_rewrite", False),
                enable_hybrid=config.get("enable_hybrid", True),
                enable_rerank=config.get("enable_rerank", False),
                chunk_strategy=config.get("chunk_strategy", "default"),
            )
            results.append(result)

        return results


def run_eval(
    dataset_path: str | Path,
    top_k: int = 10,
    dataset_type: str = "smoke",
    enable_query_rewrite: bool = False,
    enable_hybrid: bool = True,
    enable_rerank: bool = False,
    chunk_strategy: str = "default",
    retriever: Any = None,
    answer_generator: Any = None,
) -> EvalRunResult:
    """Convenience function to run evaluation.

    Args:
        dataset_path: Path to the evaluation dataset.
        top_k: Number of chunks to retrieve per query.
        dataset_type: Type of dataset (smoke or dev).
        enable_query_rewrite: Whether to enable query rewrite.
        enable_hybrid: Whether to enable hybrid retrieval.
        enable_rerank: Whether to enable reranking.
        chunk_strategy: Chunk strategy identifier.
        retriever: Retrieval function or object.
        answer_generator: Optional answer generator callable.

    Returns:
        EvalRunResult with evaluation results.
    """
    runner = AgentEvalRunner(
        retriever=retriever,
        answer_generator=answer_generator,
    )
    return runner.run(
        dataset_path=dataset_path,
        top_k=top_k,
        dataset_type=dataset_type,
        enable_query_rewrite=enable_query_rewrite,
        enable_hybrid=enable_hybrid,
        enable_rerank=enable_rerank,
        chunk_strategy=chunk_strategy,
    )
