
"""Registry of explicitly permitted research tools."""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool


class ToolRegistry:
    """Store and retrieve tools by their unique names."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool[Any, Any]] = {}

    def register(self, tool: BaseTool[Any, Any]) -> None:
        """Register a tool by name."""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool[Any, Any]:
        """Return a registered tool or raise a clear error."""
        from app.core.errors import ToolNotFoundError

        if name not in self._tools:
            raise ToolNotFoundError(f"Tool is not registered: {name}")
        return self._tools[name]

    def list(self) -> list[BaseTool[Any, Any]]:
        """Return the registered tools."""
        return list(self._tools.values())


def build_default_registry(
    session: Any = None,
    session_factory: Any = None,
) -> ToolRegistry:
    """Build the approved tools with optional database access."""
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




# """Backward-compatible import path for the tool registry."""

# from app.tools.registry import ToolRegistry, build_default_registry


# def get_tool_registry() -> dict[str, object]:
#     """Return the default tools indexed by name for legacy call sites."""
#     registry = build_default_registry()
#     return {tool.name: tool for tool in registry.list()}


# __all__ = ["ToolRegistry", "build_default_registry", "get_tool_registry"]
