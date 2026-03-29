"""Evaluation result reporters for multiple output formats.

This module provides reporters for persisting evaluation results:
- JSONReporter: Structured JSON output
- CsvReporter: Flat CSV for spreadsheet analysis
- MarkdownReporter: Human-readable markdown reports
- BaseReporter: Abstract base for custom formats

Design Principles Applied:
- Strategy Pattern: Each format is a separate strategy
- Open/Closed: Add new formats without modifying existing code
- Single Responsibility: Each reporter handles one format

Example Usage::

    from src.evaluation.reporters import get_reporter

    # JSON output
    reporter = get_reporter("json")
    reporter.save_report(report, "output/report.json")

    # CSV output
    reporter = get_reporter("csv")
    reporter.save_report(report, "output/metrics.csv")

    # Markdown output
    reporter = get_reporter("markdown")
    reporter.save_report(report, "output/report.md")
"""

from __future__ import annotations

import csv
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

logger = logging.getLogger(__name__)


class BaseReporter(ABC):
    """Abstract base class for evaluation result reporters.

    All reporters must implement save() and format() methods.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the reporter name (e.g., 'json', 'csv')."""
        ...

    @property
    def extension(self) -> str:
        """Return the file extension for this format."""
        return self.name

    @abstractmethod
    def save(self, report: Any, path: Union[str, Path]) -> None:
        """Save the report to a file.

        Args:
            report: The EvalReport to save.
            path: Output file path.
        """
        ...

    @abstractmethod
    def format(self, report: Any) -> str:
        """Format the report as a string.

        Args:
            report: The EvalReport to format.

        Returns:
            Formatted string representation.
        """
        ...

    def save_report(
        self,
        report: Any,
        path: Union[str, Path],
        *,
        include_metadata: bool = True,
    ) -> Path:
        """Save the report with optional metadata.

        Args:
            report: The EvalReport to save.
            path: Output file path.
            include_metadata: If True, add timestamp and version info.

        Returns:
            The path where the report was saved.
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        content = self.format(report)
        file_path.write_text(content, encoding="utf-8")

        logger.info("Saved %s report to %s", self.name, file_path)
        return file_path


class JsonReporter(BaseReporter):
    """JSON format reporter for structured output.

    Output format::
    {
        "metadata": {
            "generated_at": "2026-03-26T10:00:00",
            "evaluator": "RagasEvaluator",
            "test_set": "tests/fixtures/...",
        },
        "summary": {
            "query_count": 10,
            "total_elapsed_ms": 1500.5,
            "metrics": {
                "faithfulness": 0.8542,
                "answer_relevancy": 0.7823
            }
        },
        "results": [...]
    }
    """

    @property
    def name(self) -> str:
        return "json"

    @property
    def extension(self) -> str:
        return "json"

    def format(self, report: Any) -> str:
        """Format report as JSON string."""
        data = self._to_dict(report)
        return json.dumps(data, indent=2, ensure_ascii=False)

    def save(self, report: Any, path: Union[str, Path]) -> None:
        """Save report as JSON file."""
        self.save_report(report, path)

    def _to_dict(self, report: Any) -> Dict[str, Any]:
        """Convert EvalReport to dict."""
        # Handle both new EvalReport and old dict format
        if hasattr(report, "to_dict"):
            return report.to_dict()
        if hasattr(report, "aggregate_metrics"):
            return {
                "evaluator_name": getattr(report, "evaluator_name", "unknown"),
                "test_set_path": getattr(report, "test_set_path", ""),
                "total_elapsed_ms": getattr(report, "total_elapsed_ms", 0),
                "aggregate_metrics": getattr(report, "aggregate_metrics", {}),
                "query_count": len(getattr(report, "query_results", [])),
                "query_results": [
                    self._qr_to_dict(qr) for qr in getattr(report, "query_results", [])
                ],
            }
        if isinstance(report, dict):
            return report
        return {"error": f"Unknown report type: {type(report).__name__}"}

    def _qr_to_dict(self, qr: Any) -> Dict[str, Any]:
        """Convert QueryResult to dict."""
        if hasattr(qr, "__dict__"):
            return {
                "query": getattr(qr, "query", ""),
                "retrieved_chunk_ids": getattr(qr, "retrieved_chunk_ids", []),
                "generated_answer": getattr(qr, "generated_answer", ""),
                "metrics": getattr(qr, "metrics", {}),
                "elapsed_ms": getattr(qr, "elapsed_ms", 0),
            }
        if isinstance(qr, dict):
            return qr
        return {}


class CsvReporter(BaseReporter):
    """CSV format reporter for spreadsheet analysis.

    Output format (metrics per query as rows):
    query,hit_rate,mrr,faithfulness,answer_relevancy,elapsed_ms
    "What is RAG?",1.0,0.5,0.85,0.78,150.2
    ...
    """

    @property
    def name(self) -> str:
        return "csv"

    @property
    def extension(self) -> str:
        return "csv"

    def format(self, report: Any) -> str:
        """Format report as CSV string."""
        import io
        output = io.StringIO()
        self._write_csv(report, output)
        return output.getvalue()

    def save(self, report: Any, path: Union[str, Path]) -> None:
        """Save report as CSV file."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("w", newline="", encoding="utf-8") as f:
            self._write_csv(report, f)

        logger.info("Saved CSV report to %s", file_path)

    def _write_csv(self, report: Any, output: Any) -> None:
        """Write CSV to output (file or StringIO)."""
        query_results = getattr(report, "query_results", [])
        if not query_results:
            output.write("# No query results to export\n")
            return

        # Collect all metric names
        metric_names: set = set()
        for qr in query_results:
            metrics = getattr(qr, "metrics", {})
            if isinstance(metrics, dict):
                metric_names.update(metrics.keys())

        # Build header
        fieldnames = ["query", "elapsed_ms"] + sorted(metric_names)
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        # Write rows
        for qr in query_results:
            row: Dict[str, Any] = {
                "query": getattr(qr, "query", ""),
                "elapsed_ms": round(getattr(qr, "elapsed_ms", 0), 1),
            }

            metrics = getattr(qr, "metrics", {})
            if isinstance(metrics, dict):
                for name in metric_names:
                    row[name] = round(metrics.get(name, ""), 4) if name in metrics else ""

            writer.writerow(row)

    def format_aggregate(self, report: Any) -> str:
        """Format aggregate metrics as CSV (one row)."""
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["metric", "value"])
        writer.writeheader()

        aggregate = getattr(report, "aggregate_metrics", {})
        for key, value in sorted(aggregate.items()):
            writer.writerow({"metric": key, "value": round(value, 4)})

        return output.getvalue()


class MarkdownReporter(BaseReporter):
    """Markdown format reporter for human-readable output.

    Output format:
    # Evaluation Report

    ## Summary
    - Evaluator: RagasEvaluator
    - Test Set: tests/fixtures/...
    - Query Count: 10
    - Total Time: 1500.5ms

    ## Aggregate Metrics
    | Metric | Value |
    |--------|-------|
    | faithfulness | 0.8542 |
    ...

    ## Per-Query Results
    ### Query 1: What is RAG?
    - Hit Rate: 1.0
    - Faithfulness: 0.85
    - Elapsed: 150.2ms
    """

    @property
    def name(self) -> str:
        return "markdown"

    @property
    def extension(self) -> str:
        return "md"

    def format(self, report: Any) -> str:
        """Format report as Markdown string."""
        lines: List[str] = []

        # Header
        lines.append("# Evaluation Report")
        lines.append("")
        lines.append(f"_Generated: {datetime.now().isoformat()}_")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Evaluator**: {getattr(report, 'evaluator_name', 'unknown')}")
        lines.append(f"- **Test Set**: {getattr(report, 'test_set_path', 'N/A')}")
        lines.append(f"- **Query Count**: {getattr(report, 'query_count', len(getattr(report, 'query_results', [])))}")
        lines.append(f"- **Total Time**: {getattr(report, 'total_elapsed_ms', 0):.1f}ms")
        lines.append("")

        # Aggregate Metrics
        aggregate = getattr(report, "aggregate_metrics", {})
        if aggregate:
            lines.append("## Aggregate Metrics")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for key, value in sorted(aggregate.items()):
                lines.append(f"| {key} | {value:.4f} |")
            lines.append("")

        # Per-Query Results
        query_results = getattr(report, "query_results", [])
        if query_results:
            lines.append("## Per-Query Results")
            lines.append("")
            for idx, qr in enumerate(query_results, 1):
                lines.append(f"### Query {idx}")
                lines.append("")
                lines.append(f"**Question**: {getattr(qr, 'query', '')}")
                lines.append("")

                metrics = getattr(qr, "metrics", {})
                if metrics:
                    lines.append("| Metric | Value |")
                    lines.append("|--------|-------|")
                    for key, value in sorted(metrics.items()):
                        lines.append(f"| {key} | {value:.4f} |")
                    lines.append("")

                lines.append(f"_Elapsed: {getattr(qr, 'elapsed_ms', 0):.1f}ms_")
                lines.append("")

        return "\n".join(lines)

    def save(self, report: Any, path: Union[str, Path]) -> None:
        """Save report as Markdown file."""
        self.save_report(report, path)


class ConsoleReporter(BaseReporter):
    """Console format reporter for terminal output."""

    @property
    def name(self) -> str:
        return "console"

    def format(self, report: Any) -> str:
        """Format report for console output."""
        lines: List[str] = []

        # Header
        lines.append("=" * 60)
        lines.append("EVALUATION REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        lines.append(f"Evaluator: {getattr(report, 'evaluator_name', 'unknown')}")
        lines.append(f"Test Set: {getattr(report, 'test_set_path', 'N/A')}")
        lines.append(f"Queries: {getattr(report, 'query_count', len(getattr(report, 'query_results', [])))}")
        lines.append(f"Total Time: {getattr(report, 'total_elapsed_ms', 0):.1f}ms")
        lines.append("")

        # Metrics
        aggregate = getattr(report, "aggregate_metrics", {})
        if aggregate:
            lines.append("Aggregate Metrics:")
            for key, value in sorted(aggregate.items()):
                bar = self._make_bar(value)
                lines.append(f"  {key:20s}: {value:.4f} {bar}")
        else:
            lines.append("No metrics recorded.")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def save(self, report: Any, path: Union[str, Path]) -> None:
        """Print to console instead of saving."""
        print(self.format(report))

    @staticmethod
    def _make_bar(value: float, width: int = 20) -> str:
        """Create a simple ASCII bar chart."""
        filled = int(value * width)
        bar = "#" * filled + "-" * (width - filled)
        return f"[{bar}]"


# ── Reporter Factory ─────────────────────────────────────────────────────────────

_REPORTER_REGISTRY: Dict[str, Type[BaseReporter]] = {
    "json": JsonReporter,
    "csv": CsvReporter,
    "markdown": MarkdownReporter,
    "md": MarkdownReporter,
    "console": ConsoleReporter,
}


def get_reporter(name: str) -> BaseReporter:
    """Get a reporter instance by name.

    Args:
        name: Reporter name (e.g., 'json', 'csv', 'markdown').

    Returns:
        A BaseReporter instance.

    Raises:
        ValueError: If the reporter name is unknown.
    """
    reporter_class = _REPORTER_REGISTRY.get(name.lower())
    if reporter_class is None:
        available = ", ".join(sorted(_REPORTER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown reporter: '{name}'. Available: {available}"
        )
    return reporter_class()


def list_reporters() -> List[str]:
    """List all available reporter names."""
    return sorted(_REPORTER_REGISTRY.keys())


def register_reporter(name: str, reporter_class: Type[BaseReporter]) -> None:
    """Register a custom reporter.

    Args:
        name: Reporter name (e.g., 'parquet').
        reporter_class: BaseReporter subclass.
    """
    if not issubclass(reporter_class, BaseReporter):
        raise ValueError(f"{reporter_class.__name__} must inherit from BaseReporter")
    _REPORTER_REGISTRY[name.lower()] = reporter_class


# ── Convenience Functions ───────────────────────────────────────────────────────

def save_report(
    report: Any,
    path: Union[str, Path],
    format_hint: Optional[str] = None,
) -> Path:
    """Save a report in the appropriate format.

    Args:
        report: The EvalReport to save.
        path: Output file path.
        format_hint: Force a specific format (e.g., 'json').

    Returns:
        The path where the report was saved.
    """
    file_path = Path(path)

    # Determine format from extension if not specified
    if format_hint is None:
        format_hint = file_path.suffix.lower().lstrip(".")

    reporter = get_reporter(format_hint or "json")
    return reporter.save_report(report, file_path)


def print_report(report: Any) -> None:
    """Print a report to the console."""
    reporter = ConsoleReporter()
    print(reporter.format(report))
