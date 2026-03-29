"""Evaluation module for RAG quality assessment.

This module provides a unified evaluation framework:
- Registry: @register_evaluator decorator for automatic registration
- Evaluators: Base, Custom, Ragas, Composite evaluators
- Datasets: Abstract test dataset loaders (JSON, CSV, etc.)
- Reporters: Result persistence in multiple formats

Note: EvalRunner is imported directly from src.observability.evaluation.eval_runner
to avoid circular imports.

Directory Structure::

    src/evaluation/
    ├── __init__.py          # Unified exports
    ├── registry.py          # Evaluator registry with decorators
    ├── evaluators/
    │   ├── __init__.py     # Evaluator package exports
    │   ├── base.py         # BaseEvaluator, NoneEvaluator
    │   ├── custom.py       # CustomEvaluator (hit_rate, mrr)
    │   ├── ragas.py        # RagasEvaluator (LLM-as-Judge)
    │   ├── composite.py    # CompositeEvaluator (multi-backend)
    │   └── factory.py      # EvaluatorFactory
    ├── datasets.py         # Dataset loaders (JSON, JSONL)
    └── reporters.py         # Report generators (JSON, CSV, Markdown)

Quick Start::

    # Using the registry
    from src.evaluation import create_evaluator, list_available_evaluators

    evaluators = list_available_evaluators()
    evaluator = create_evaluator("ragas", settings=settings)

    # Using test datasets
    from src.evaluation.datasets import load_dataset

    test_set = load_dataset("tests/fixtures/phoenix_test_set.json")

    # Using reporters
    from src.evaluation.reporters import get_reporter

    reporter = get_reporter("json")
    reporter.save_report(eval_report, "output/report.json")

    # Using EvalRunner
    from src.observability.evaluation.eval_runner import EvalRunner

    runner = EvalRunner(evaluator=evaluator, hybrid_search=search)
    report = await runner.run_async(test_set_path)
"""

from __future__ import annotations

# Registry
from src.evaluation.registry import (
    get_evaluator_registry,
    register_evaluator,
    register_evaluator_lazy,
    create_evaluator,
    list_available_evaluators,
    get_evaluator_info,
    reset_registry,
)

# Dataset loaders
from src.evaluation.datasets import (
    BaseDataset,
    JsonDataset,
    GoldenTestCase,
    load_dataset,
    load_test_set,
)

# Reporters
from src.evaluation.reporters import (
    BaseReporter,
    JsonReporter,
    CsvReporter,
    MarkdownReporter,
    ConsoleReporter,
    get_reporter,
    list_reporters,
    save_report,
)

# Evaluators (re-export for convenience)
from src.evaluation.evaluators import (
    BaseEvaluator,
    NoneEvaluator,
    CustomEvaluator,
    EvaluatorFactory,
)

__all__ = [
    # Registry
    "get_evaluator_registry",
    "register_evaluator",
    "register_evaluator_lazy",
    "create_evaluator",
    "list_available_evaluators",
    "get_evaluator_info",
    "reset_registry",
    # Datasets
    "BaseDataset",
    "JsonDataset",
    "GoldenTestCase",
    "load_dataset",
    "load_test_set",
    # Reporters
    "BaseReporter",
    "JsonReporter",
    "CsvReporter",
    "MarkdownReporter",
    "ConsoleReporter",
    "get_reporter",
    "list_reporters",
    "save_report",
    # Evaluators
    "BaseEvaluator",
    "NoneEvaluator",
    "CustomEvaluator",
    "EvaluatorFactory",
]
