"""Base tool interface for Agent."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class ToolInput:
    """Input schema for tools."""

    query: Optional[str] = None
    top_k: Optional[int] = 5
    file_path: Optional[str] = None
    collection_name: Optional[str] = None
    expression: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ToolOutput:
    """Output schema for tools."""

    success: bool
    result: Any
    error: Optional[str] = None


class BaseTool(ABC):
    """Abstract base class for all agent tools."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any]
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    @abstractmethod
    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """Execute the tool with given input."""
        pass

    def validate_input(self, tool_input: ToolInput) -> bool:
        """Validate input against schema."""
        return True

    def get_schema(self) -> Dict[str, Any]:
        """Return the tool's JSON schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }
