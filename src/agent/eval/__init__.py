"""Agent Evaluation Module.

This module provides agent-level evaluation capabilities built on top of
the existing observability/evaluation infrastructure. It includes:
- Dataset loading for evaluation test cases
- Retrieval evaluation metrics
- Answer evaluation metrics
- Report generation
- Evaluation runner orchestration
"""

# Import convenience alias for AgentEvalRunner
from src.agent.eval.runner import AgentEvalRunner, EvalRunResult, run_eval

# Also provide backward-compatible alias
EvalRunner = AgentEvalRunner

__all__ = [
    "dataset",
    "retrieval_eval",
    "answer_eval",
    "reporter",
    "runner",
    "AgentEvalRunner",
    "EvalRunner",
    "EvalRunResult",
    "run_eval",
]
