
"""Registration and planner-facing descriptions for controlled tools."""

from __future__ import annotations

from collections.abc import Sequence, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ToolInputError, ToolNotFoundError
from app.tools.base import BaseTool


class ToolRegistry:
    """Named registry of explicitly allowed local tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool[Any, Any]] = {}

    def register(self, tool: BaseTool[Any, Any]) -> None:
        """Register a tool once, rejecting duplicate names."""
        if not tool.name or not tool.name.strip():
            raise ToolInputError("Tool name cannot be empty")

        if tool.name in self._tools:
            raise ToolInputError(
                f"Tool is already registered: {tool.name}"
            )

        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool[Any, Any]:
        """Return a registered tool or raise a typed not-found error."""
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(
                f"Tool is not registered: {name}"
            ) from exc

    def list(self) -> Sequence[BaseTool[Any, Any]]:
        """Return tools in registration order."""
        return list(self._tools.values())

    def describe_all(self) -> Sequence[dict[str, Any]]:
        """Return planner-facing tool descriptions and JSON input schemas."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "timeout_seconds": tool.timeout,
                "input_schema": tool.input_model.model_json_schema(),
                "output_schema": tool.output_model.model_json_schema(),
            }
            for tool in self._tools.values()
        ]


def build_default_registry(
    session: AsyncSession | None = None,
    session_factory: Callable[[], AsyncSession] | None = None,
) -> ToolRegistry:
    """Build the four explicitly allowed local tools.

    Args:
        session: Optional existing database session for compatibility.
        session_factory: Optional callable that creates fresh async
            database sessions for database-backed tools.
    """
    from app.tools.calculator import CalculatorTool
    from app.tools.csv_reader import CSVReaderTool
    from app.tools.document_search import DocumentSearchTool
    from app.tools.report_generator import ReportGeneratorTool

    registry = ToolRegistry()

    registry.register(
        DocumentSearchTool(
            session=session,
            session_factory=session_factory,
        )
    )

    registry.register(
        CSVReaderTool(
            session=session,
            session_factory=session_factory,
        )
    )

    registry.register(CalculatorTool())
    registry.register(ReportGeneratorTool())

    return registry






# """Registration and planner-facing descriptions for controlled tools."""

# from __future__ import annotations

# from collections.abc import Sequence
# from typing import Any

# from app.core.errors import ToolInputError, ToolNotFoundError
# from app.tools.base import BaseTool


# class ToolRegistry:
#     """Named registry of explicitly allowed local tools."""

#     def __init__(self) -> None:
#         self._tools: dict[str, BaseTool[Any, Any]] = {}

#     def register(self, tool: BaseTool[Any, Any]) -> None:
#         """Register a tool once, rejecting duplicate names."""
#         if not tool.name or not tool.name.strip():
#             raise ToolInputError("Tool name cannot be empty")
#         if tool.name in self._tools:
#             raise ToolInputError(f"Tool is already registered: {tool.name}")
#         self._tools[tool.name] = tool

#     def get(self, name: str) -> BaseTool[Any, Any]:
#         """Return a registered tool or raise a typed not-found error."""
#         try:
#             return self._tools[name]
#         except KeyError as exc:
#             raise ToolNotFoundError(f"Tool is not registered: {name}") from exc

#     def list(self) -> Sequence[BaseTool[Any, Any]]:
#         """Return tools in registration order."""
#         return [tool for tool in self._tools.values()]

#     def describe_all(self) -> Sequence[dict[str, Any]]:
#         """Return planner-facing tool descriptions and JSON input schemas."""
#         return [
#             {
#                 "name": tool.name,
#                 "description": tool.description,
#                 "timeout_seconds": tool.timeout,
#                 "input_schema": tool.input_model.model_json_schema(),
#                 "output_schema": tool.output_model.model_json_schema(),
#             }
#             for tool in self._tools.values()
#         ]


# def build_default_registry(session: Any = None) -> ToolRegistry:
#     """Build the four explicitly allowed local tools."""
#     from app.tools.calculator import CalculatorTool
#     from app.tools.csv_reader import CSVReaderTool
#     from app.tools.document_search import DocumentSearchTool
#     from app.tools.report_generator import ReportGeneratorTool

#     registry = ToolRegistry()
#     registry.register(DocumentSearchTool(session=session))
#     registry.register(CSVReaderTool(session=session))
#     registry.register(CalculatorTool())
#     registry.register(ReportGeneratorTool())
#     return registry
