"""Restricted AST arithmetic evaluator; never uses eval()."""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable

from app.core.errors import ToolExecutionError, ToolInputError
from app.tools.base import BaseTool
from app.tools.schemas import CalculatorInput, CalculatorOutput

_MAX_EXPONENT = 100
_MAX_ABS_RESULT = 1e100
_MAX_AST_NODES = 100

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}


class CalculatorTool(BaseTool[CalculatorInput, CalculatorOutput]):
    """Calculate arithmetic and approved statistical functions safely."""

    name = "calculator"
    description = "Evaluate arithmetic using +, -, *, /, //, %, ** and approved math functions."
    input_model = CalculatorInput
    output_model = CalculatorOutput
    timeout = 5.0

    async def run(self, input: CalculatorInput) -> CalculatorOutput:
        """Evaluate a restricted mathematical expression."""
        try:
            tree = ast.parse(input.expression, mode="eval")
        except SyntaxError as exc:
            raise ToolInputError("Expression is not valid arithmetic syntax") from exc
        if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
            raise ToolInputError("Expression is too complex")
        value = self._visit(tree.body)
        normalized = ast.unparse(tree.body)
        return CalculatorOutput(value=value, normalized_expression=normalized)

    def _visit(self, node: ast.AST) -> float:
        """Evaluate a single node from the approved arithmetic AST subset."""
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            if isinstance(node.value, bool):
                raise ToolInputError("Boolean values are not valid arithmetic inputs")
            return self._bounded(float(node.value))
        if isinstance(node, ast.BinOp):
            left = self._visit(node.left)
            right = self._visit(node.right)
            try:
                if isinstance(node.op, ast.Pow):
                    if abs(right) > _MAX_EXPONENT:
                        raise ToolInputError(f"Exponent magnitude cannot exceed {_MAX_EXPONENT:g}")
                    value = operator.pow(left, right)
                else:
                    operation = _BIN_OPS.get(type(node.op))
                    if operation is None:
                        raise ToolInputError("Unsupported arithmetic operator")
                    value = operation(left, right)
            except ZeroDivisionError as exc:
                raise ToolExecutionError("Division by zero is not allowed") from exc
            except OverflowError as exc:
                raise ToolInputError("Expression result is too large") from exc
            return self._bounded(value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            value = self._visit(node.operand)
            return self._bounded(value if isinstance(node.op, ast.UAdd) else -value)
        if isinstance(node, ast.Call):
            return self._call(node)
        raise ToolInputError(f"Unsupported expression element: {type(node).__name__}")

    def _call(self, node: ast.Call) -> float:
        """Evaluate only explicit calls to approved bare function names."""
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise ToolInputError("Only direct calls to approved calculator functions are allowed")
        name = node.func.id
        if name not in {
            "abs",
            "round",
            "min",
            "max",
            "sum",
            "sqrt",
            "pct_change",
            "pct_of",
            "cagr",
        }:
            raise ToolInputError(f"Unsupported function or argument count: {name}")
        args = [self._visit(argument) for argument in node.args]
        try:
            if name == "abs" and len(args) == 1:
                result = abs(args[0])
            elif name == "round" and len(args) in {1, 2}:
                digits = int(args[1]) if len(args) == 2 else 0
                if abs(digits) > 12:
                    raise ToolInputError("round precision cannot exceed 12 digits")
                result = round(args[0], digits)
            elif name in {"min", "max", "sum"} and args:
                if name == "min":
                    result = min(args)
                elif name == "max":
                    result = max(args)
                else:
                    result = sum(args)
            elif name == "sqrt" and len(args) == 1:
                if args[0] < 0:
                    raise ToolInputError("sqrt input cannot be negative")
                result = math.sqrt(args[0])
            elif name == "pct_change" and len(args) == 2:
                old, new = args
                if old == 0:
                    raise ToolExecutionError("pct_change is undefined when old is zero")
                result = (new - old) / old * 100
            elif name == "pct_of" and len(args) == 2:
                part, total = args
                if total == 0:
                    raise ToolExecutionError("pct_of is undefined when total is zero")
                result = part / total * 100
            elif name == "cagr" and len(args) == 3:
                start, end, years = args
                if start <= 0 or end < 0 or years <= 0:
                    raise ToolInputError("cagr requires start > 0, end >= 0, and years > 0")
                result = ((end / start) ** (1 / years) - 1) * 100
            else:
                raise ToolInputError(f"Unsupported function or argument count: {name}")
        except (OverflowError, ValueError) as exc:
            raise ToolInputError(f"Invalid arguments for {name}: {exc}") from exc
        return self._bounded(float(result))

    @staticmethod
    def _bounded(value: float) -> float:
        """Reject NaN, infinite, and excessively large intermediate results."""
        if not math.isfinite(value) or abs(value) > _MAX_ABS_RESULT:
            raise ToolInputError("Expression result is outside the supported numeric range")
        return value
