"""Report generation for evaluation results.

This module provides functionality to generate evaluation reports in
markdown and JSON formats.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvalExperimentConfig:
    """Configuration for an evaluation experiment.

    Attributes:
        dataset_type: Type of dataset (smoke or dev).
        top_k: Number of results to retrieve.
        enable_query_rewrite: Whether query rewrite is enabled.
        enable_hybrid: Whether hybrid retrieval is enabled.
        enable_rerank: Whether rerank is enabled.
        chunk_strategy: Chunk strategy identifier.
    """

    dataset_type: str = "smoke"
    top_k: int = 10
    enable_query_rewrite: bool = False
    enable_hybrid: bool = True
    enable_rerank: bool = False
    chunk_strategy: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "dataset_type": self.dataset_type,
            "top_k": self.top_k,
            "enable_query_rewrite": self.enable_query_rewrite,
            "enable_hybrid": self.enable_hybrid,
            "enable_rerank": self.enable_rerank,
            "chunk_strategy": self.chunk_strategy,
        }


@dataclass
class EvalReport:
    """Evaluation report containing all metrics and results.

    Attributes:
        experiment_id: Unique identifier for this experiment.
        timestamp: Timestamp when the report was generated.
        config: Experiment configuration.
        retrieval_summary: Retrieval evaluation summary.
        answer_summary: Answer evaluation summary.
        total_elapsed_ms: Total time for the evaluation.
    """

    experiment_id: str
    timestamp: str
    config: EvalExperimentConfig
    retrieval_summary: Optional[Dict[str, Any]] = None
    answer_summary: Optional[Dict[str, Any]] = None
    total_elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "config": self.config.to_dict(),
            "retrieval_summary": self.retrieval_summary,
            "answer_summary": self.answer_summary,
            "total_elapsed_ms": round(self.total_elapsed_ms, 1),
        }


class EvalReporter:
    """Generates evaluation reports in various formats.

    Example:
        reporter = EvalReporter(output_dir="data/eval/results")
        report = EvalReport(...)
        reporter.save_report(report)
    """

    def __init__(self, output_dir: str | Path = "data/eval/results") -> None:
        """Initialize the reporter.

        Args:
            output_dir: Directory to save reports.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        experiment_id: str,
        config: EvalExperimentConfig,
        retrieval_summary: Optional[Dict[str, Any]] = None,
        answer_summary: Optional[Dict[str, Any]] = None,
        total_elapsed_ms: float = 0.0,
    ) -> EvalReport:
        """Generate an evaluation report.

        Args:
            experiment_id: Unique identifier for this experiment.
            config: Experiment configuration.
            retrieval_summary: Retrieval evaluation summary.
            answer_summary: Answer evaluation summary.
            total_elapsed_ms: Total time for the evaluation.

        Returns:
            EvalReport instance.
        """
        timestamp = datetime.now().isoformat()

        return EvalReport(
            experiment_id=experiment_id,
            timestamp=timestamp,
            config=config,
            retrieval_summary=retrieval_summary,
            answer_summary=answer_summary,
            total_elapsed_ms=total_elapsed_ms,
        )

    def save_report(
        self,
        report: EvalReport,
        format: str = "all",
    ) -> Path:
        """Save the report to files.

        Args:
            report: The report to save.
            format: Output format - "markdown", "json", or "all". Defaults to "all".

        Returns:
            Path to the main report file.
        """
        output_dir = self.output_dir / report.experiment_id
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []

        if format in ("markdown", "all"):
            md_path = self._save_markdown_report(report, output_dir)
            saved_paths.append(md_path)

        if format in ("json", "all"):
            json_path = self._save_json_report(report, output_dir)
            saved_paths.append(json_path)

        logger.info(f"Report saved to {output_dir}")
        return saved_paths[0] if saved_paths else output_dir

    def _save_markdown_report(
        self,
        report: EvalReport,
        output_dir: Path,
    ) -> Path:
        """Save report as markdown.

        Args:
            report: The report to save.
            output_dir: Directory to save the report.

        Returns:
            Path to the saved markdown file.
        """
        md_path = output_dir / "report.md"
        lines = []

        lines.append(f"# Evaluation Report: {report.experiment_id}\n")
        lines.append(f"**Generated**: {report.timestamp}\n")
        lines.append(f"**Total Time**: {report.total_elapsed_ms:.1f} ms\n")

        lines.append("\n## Configuration\n")
        lines.append(f"- Dataset: {report.config.dataset_type}\n")
        lines.append(f"- Top-K: {report.config.top_k}\n")
        lines.append(f"- Query Rewrite: {report.config.enable_query_rewrite}\n")
        lines.append(f"- Hybrid Retrieval: {report.config.enable_hybrid}\n")
        lines.append(f"- Rerank: {report.config.enable_rerank}\n")
        lines.append(f"- Chunk Strategy: {report.config.chunk_strategy}\n")

        if report.retrieval_summary:
            lines.append("\n## Retrieval Metrics\n")
            summary = report.retrieval_summary
            lines.append(f"- Total Queries: {summary.get('total_queries', 0)}\n")
            lines.append(f"- Avg Recall@K: {summary.get('avg_recall_at_k', 0):.4f}\n")
            lines.append(f"- Avg Hit@K: {summary.get('avg_hit_at_k', 0):.4f}\n")
            lines.append(f"- Avg MRR: {summary.get('avg_mrr', 0):.4f}\n")
            lines.append(f"- Total Source Hits: {summary.get('total_source_hits', 0)}\n")
            lines.append(f"- Total Page No Hits: {summary.get('total_page_no_hits', 0)}\n")
            lines.append(f"- Total Section Title Hits: {summary.get('total_section_title_hits', 0)}\n")

        if report.answer_summary:
            lines.append("\n## Answer Metrics\n")
            summary = report.answer_summary
            lines.append(f"- Total Queries: {summary.get('total_queries', 0)}\n")
            lines.append(f"- Avg Answer Length: {summary.get('avg_answer_length', 0):.2f}\n")
            lines.append(f"- Avg Citation Count: {summary.get('avg_citation_count', 0):.2f}\n")
            lines.append(f"- Avg Keyword Coverage: {summary.get('avg_keyword_coverage', 0):.4f}\n")
            lines.append(f"- Avg Completeness Score: {summary.get('avg_completeness_score', 0):.4f}\n")

        with md_path.open("w", encoding="utf-8") as f:
            f.writelines(lines)

        return md_path

    def _save_json_report(
        self,
        report: EvalReport,
        output_dir: Path,
    ) -> Path:
        """Save report as JSON.

        Args:
            report: The report to save.
            output_dir: Directory to save the report.

        Returns:
            Path to the saved JSON file.
        """
        json_path = output_dir / "metrics.json"

        with json_path.open("w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        return json_path

    def save_config(
        self,
        config: EvalExperimentConfig,
        experiment_id: str,
    ) -> Path:
        """Save experiment configuration.

        Args:
            config: The configuration to save.
            experiment_id: Experiment identifier.

        Returns:
            Path to the saved config file.
        """
        output_dir = self.output_dir / experiment_id
        output_dir.mkdir(parents=True, exist_ok=True)

        config_path = output_dir / "run_config.json"
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

        return config_path

    def generate_experiment_id(self) -> str:
        """Generate a unique experiment ID with timestamp.

        Returns:
            Experiment ID string.
        """
        return f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
