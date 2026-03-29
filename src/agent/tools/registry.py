"""
Tool registry for Agent.

Manages available tools for the agent.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .base import BaseTool
from ..infra.logging import get_logger


logger = get_logger(__name__)


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register default tools."""
        from .rag_tool import RagTool
        from .calculator_tool import CalculatorTool

        self.register(RagTool())
        self.register(CalculatorTool())

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """List all available tools."""
        return list(self._tools.values())


_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the singleton tool registry."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
