"""
Edges for Agent LangGraph.

Defines the conditional edges that control flow between nodes.
"""

from typing import Literal

from .state import AgentState
from ..infra.logging import get_logger

logger = get_logger(__name__)


def should_use_tools(state: AgentState) -> Literal["tool_executor", "answer_builder"]:
    """
    Determine whether to use tools based on planner decision.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    if state.should_use_tools:
        return "tool_executor"
    else:
        return "answer_builder"


def should_continue(state: AgentState) -> Literal["memory_writer", "finalize"]:
    """
    Determine whether to continue or end the conversation.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    if state.error:
        return "finalize"
    else:
        return "memory_writer"


# ========== 新增：循环检索边函数 ==========
def should_reflect_or_finish(state: AgentState) -> Literal["iteration_preparer", "answer_builder"]:
    """
    决定是否需要继续检索（反思后迭代）还是构建答案。

    决策逻辑：
    1. 如果 needs_more_retrieval=True 且未超过最大迭代次数，返回 iteration_preparer
    2. 如果 needs_more_retrieval=True 但已超过最大迭代次数，强制进入 answer_builder
    3. 如果 needs_more_retrieval=False，进入 answer_builder

    Args:
        state: Current agent state

    Returns:
        Next node name: "iteration_preparer" 或 "answer_builder"
    """
    # 检查迭代次数保护
    if getattr(state, 'needs_more_retrieval', False):
        if state.iteration_count >= state.max_iterations:
            logger.warning(f"Max iterations ({state.max_iterations}) reached, forcing answer builder")
            state.reflection_notes = (state.reflection_notes or "") + f"\n[WARNING] Max iterations reached, forcing answer."
            return "answer_builder"
        else:
            logger.info(f"Reflection: needs more retrieval, iteration {state.iteration_count + 1}/{state.max_iterations}")
            return "iteration_preparer"
    else:
        logger.info("Reflection: sufficient information, proceeding to answer builder")
        return "answer_builder"


def should_use_tools_or_finish(state: AgentState) -> Literal["tool_executor", "answer_builder"]:
    """
    决定是否使用工具还是结束（整合迭代次数检查）。

    决策逻辑：
    1. 如果需要工具但已超过最大迭代次数，返回 answer_builder（强制结束）
    2. 如果需要工具且未超过最大迭代次数，返回 tool_executor
    3. 如果不需要工具，返回 answer_builder

    ⚠️ 重要：这个边只在不启用反思机制时使用
    保持原有逻辑，用于向后兼容

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    # 检查迭代次数保护（仅在启用反思时）
    if state.should_use_tools and state.iteration_count >= state.max_iterations:
        logger.warning(f"Max iterations ({state.max_iterations}) reached, forcing answer builder")
        return "answer_builder"

    if state.should_use_tools:
        return "tool_executor"
    else:
        return "answer_builder"
# ==========================================
