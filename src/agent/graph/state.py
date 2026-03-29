"""
Agent state for LangGraph.

Defines the state object that flows through the graph nodes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal

from ..schemas.chat import ToolStep
from ..schemas.citation import CitationChunk


def _get_max_iterations() -> int:
    """从配置获取最大迭代次数"""
    try:
        from ..infra.config import get_agent_runtime_settings
        return get_agent_runtime_settings().max_iterations
    except Exception:
        return 3  # 默认值


@dataclass
class AgentState:
    """
    State that flows through the LangGraph agent.

    This is the main state object that is passed between nodes in the graph.
    """

    query: str
    session_id: str
    user_id: Optional[str] = None
    top_k: int = 5
    temperature: float = 0.7
    use_tools: bool = True

    messages: List[Dict[str, Any]] = field(default_factory=list)
    current_message: Optional[Dict[str, Any]] = None

    memory_context: str = ""
    retrieved_docs: List[CitationChunk] = field(default_factory=list)

    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)

    answer: str = ""
    citations: List[CitationChunk] = field(default_factory=list)

    next_node: Optional[str] = None
    should_use_tools: bool = False

    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ========== 新增：反思机制相关字段 ==========
    needs_more_retrieval: bool = False
    reflection_notes: str = ""
    improvement_suggestions: List[str] = field(default_factory=list)
    reasoning_steps: List[Dict[str, str]] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = field(default_factory=lambda: _get_max_iterations())
    # ===========================================

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append({"role": role, "content": content})

    def add_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        """Add a tool call to the list."""
        self.tool_calls.append({
            "tool_name": tool_name,
            "arguments": arguments,
            "status": "pending"
        })

    def add_tool_result(self, tool_name: str, result: str, error: Optional[str] = None) -> None:
        """Add a tool result to the list."""
        self.tool_results.append({
            "tool_name": tool_name,
            "result": result,
            "error": error,
            "status": "error" if error else "success"
        })

    def get_conversation_history(self) -> str:
        """Get formatted conversation history."""
        if not self.messages:
            return ""
        
        history_parts = []
        for msg in self.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_parts.append(f"{role}: {content}")
        
        return "\n".join(history_parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "query": self.query,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "top_k": self.top_k,
            "temperature": self.temperature,
            "use_tools": self.use_tools,
            "messages": self.messages,
            "memory_context": self.memory_context,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "next_node": self.next_node,
            "should_use_tools": self.should_use_tools,
            "error": self.error,
            "metadata": self.metadata,
            # 新增：反思机制字段
            "needs_more_retrieval": self.needs_more_retrieval,
            "reflection_notes": self.reflection_notes,
            "improvement_suggestions": self.improvement_suggestions,
            "reasoning_steps": self.reasoning_steps,
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
        }
