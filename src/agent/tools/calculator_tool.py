"""Calculator tool for Agent."""

import ast
import operator
from typing import Any, Callable, Dict

from .base import BaseTool, ToolInput, ToolOutput
from ..infra.logging import get_logger


logger = get_logger(__name__)


class CalculatorTool(BaseTool):
    """Tool for safe mathematical calculations."""

    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
    }

    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform mathematical calculations",
            input_schema={
                "expression": {"type": "string", "required": True}
            }
        )

    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """Execute the calculation."""
        expression = tool_input.expression
        if not expression:
            return ToolOutput(
                success=False,
                result=None,
                error="expression is required"
            )

        try:
            result = self._safe_eval(expression)
            return ToolOutput(success=True, result=result)
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            return ToolOutput(
                success=False,
                result=None,
                error=str(e)
            )

    def _safe_eval(self, expr: str) -> float:
        """Safely evaluate a mathematical expression."""
        expr = expr.strip()
        node = ast.parse(expr, mode='eval')
        return self._eval_node(node.body)

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Invalid constant: {node.value}")
        
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type not in self.OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type}")
            return self.OPERATORS[op_type](left, right)
        
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
        
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")
