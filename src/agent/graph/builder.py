"""
LangGraph builder for Agent.

Builds and compiles the LangGraph agent.
"""

from typing import Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes import (
    load_memory,
    planner,
    tool_executor,
    answer_builder,
    memory_writer,
    finalize,
    reflector,
    iteration_preparer,
)
from .edges import (
    should_use_tools,
    should_continue,
    should_reflect_or_finish,
    should_use_tools_or_finish,
)
from ..infra.logging import get_logger


logger = get_logger(__name__)


class AgentGraph:
    """LangGraph agent builder."""

    def __init__(self, enable_reflection: Optional[bool] = None):
        """
        Initialize the AgentGraph.

        Args:
            enable_reflection: Override reflection setting. If None, reads from config.
        """
        self.graph: Optional[StateGraph] = None

        # 如果没有显式传入配置，则从全局配置读取
        if enable_reflection is None:
            from ..infra.config import get_agent_runtime_settings
            settings = get_agent_runtime_settings()
            self.enable_reflection = settings.enable_reflection
            self.max_iterations = settings.max_iterations
            self.reflection_timeout = settings.reflection_timeout
        else:
            # 显式传入配置，覆盖全局配置
            self.enable_reflection = enable_reflection
            self.max_iterations = 3
            self.reflection_timeout = 30

        logger.info(f"AgentGraph initialized with enable_reflection={self.enable_reflection}")
        self._build()

    def _build(self) -> None:
        """Build the graph with reflection support."""
        workflow = StateGraph(AgentState)

        # 添加所有节点
        workflow.add_node("load_memory", load_memory)
        workflow.add_node("planner", planner)
        workflow.add_node("tool_executor", tool_executor)
        workflow.add_node("reflector", reflector)  # 反思节点（可选）
        workflow.add_node("iteration_preparer", iteration_preparer)  # 迭代准备节点
        workflow.add_node("answer_builder", answer_builder)
        workflow.add_node("memory_writer", memory_writer)
        workflow.add_node("finalize", finalize)

        # 设置入口
        workflow.set_entry_point("load_memory")
        workflow.add_edge("load_memory", "planner")

        # 根据是否启用反思机制选择不同的边策略
        if self.enable_reflection:
            # 启用反思：planner -> [tool_executor/answer_builder]
            # 工具执行后进入反思阶段
            workflow.add_conditional_edges(
                "planner",
                should_use_tools_or_finish,  # 使用整合后的边函数
                {
                    "tool_executor": "tool_executor",
                    "answer_builder": "answer_builder"
                }
            )

            # 工具执行后进入反思阶段
            workflow.add_edge("tool_executor", "reflector")

            # 反思决定是继续检索还是构建答案
            workflow.add_conditional_edges(
                "reflector",
                should_reflect_or_finish,  # 反思决策边函数
                {"iteration_preparer": "iteration_preparer", "answer_builder": "answer_builder"}
            )

            # 迭代准备后回到 planner
            workflow.add_edge("iteration_preparer", "planner")
        else:
            # 不启用反思：保持原有流程
            workflow.add_conditional_edges(
                "planner",
                should_use_tools,  # 使用原有函数，向后兼容
                {
                    "tool_executor": "tool_executor",
                    "answer_builder": "answer_builder"
                }
            )
            workflow.add_edge("tool_executor", "answer_builder")

        # 后续流程保持不变
        workflow.add_conditional_edges(
            "answer_builder",
            should_continue,
            {
                "memory_writer": "memory_writer",
                "finalize": "finalize",
            }
        )

        workflow.add_edge("memory_writer", "finalize")
        workflow.add_edge("finalize", END)

        checkpointer = MemorySaver()
        self.graph = workflow.compile(checkpointer=checkpointer)

        logger.info(f"Agent graph built with reflection={'enabled' if self.enable_reflection else 'disabled'}")

    def get_graph(self) -> StateGraph:
        """Get the compiled graph."""
        return self.graph

    async def run(self, query: str, session_id: str, **kwargs) -> AgentState:
        """Run the agent with a query."""
        config = {"configurable": {"thread_id": session_id}}

        initial_state = AgentState(
            query=query,
            session_id=session_id,
            **kwargs
        )

        result = await self.graph.ainvoke(initial_state, config)
        return result


_agent_graph: Optional[AgentGraph] = None
_graph_config: Optional[dict] = None


def get_agent_graph(enable_reflection: Optional[bool] = None, force_recreate: bool = False) -> AgentGraph:
    """Get the singleton agent graph instance.

    Args:
        enable_reflection: Override reflection setting. If None, reads from config.
        force_recreate: If True, always create a new graph instance.

    Returns:
        AgentGraph: The agent graph instance
    """
    global _agent_graph, _graph_config

    current_config = {
        "enable_reflection": enable_reflection,
    }

    # 如果 force_recreate 或者配置发生变化，重新创建 Graph
    if _agent_graph is None or force_recreate or _graph_config != current_config:
        _agent_graph = AgentGraph(enable_reflection=enable_reflection)
        _graph_config = current_config
        logger.info(f"AgentGraph recreated with config: {current_config}")

    return _agent_graph


def reset_agent_graph() -> None:
    """Reset the agent graph, forcing recreation on next call."""
    global _agent_graph, _graph_config
    _agent_graph = None
    _graph_config = None
    logger.info("Agent graph reset")


def compile_graph() -> StateGraph:
    """Get the compiled graph."""
    return get_agent_graph().get_graph()
