

from __future__ import annotations

import re
from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import PlanStep
from app.agent.nodes.common import log_transition
from app.agent.state import AgentState


# Match expressions such as 125 * 8, 100 / 4, and 2 ** 3.
_ARITHMETIC_PATTERN = re.compile(
    r"(?<![\w.])-?\d+(?:\.\d+)?"
    r"(?:\s*(?:\*\*|//|[+\-*/%])\s*-?\d+(?:\.\d+)?)+"
    r"(?![\w.])"
)

# Recognize basic arithmetic written in natural language.
_WORD_ARITHMETIC_PATTERNS = (
    (
        re.compile(
            r"(-?\d+(?:\.\d+)?)\s+"
            r"(?:multiplied\s+by|times)\s+"
            r"(-?\d+(?:\.\d+)?)",
            re.IGNORECASE,
        ),
        "*",
    ),
    (
        re.compile(
            r"(-?\d+(?:\.\d+)?)\s+"
            r"(?:divided\s+by|over)\s+"
            r"(-?\d+(?:\.\d+)?)",
            re.IGNORECASE,
        ),
        "/",
    ),
    (
        re.compile(
            r"(-?\d+(?:\.\d+)?)\s+"
            r"(?:plus|added\s+to)\s+"
            r"(-?\d+(?:\.\d+)?)",
            re.IGNORECASE,
        ),
        "+",
    ),
    (
        re.compile(
            r"(-?\d+(?:\.\d+)?)\s+"
            r"(?:minus|less)\s+"
            r"(-?\d+(?:\.\d+)?)",
            re.IGNORECASE,
        ),
        "-",
    ),
)

# Common instruction words that are not useful for document search.
_SEARCH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "can", "could",
    "describe", "do", "does", "explain", "find", "for", "from",
    "give", "help", "how", "i", "in", "information", "into", "is",
    "it", "me", "my", "of", "on", "or", "please", "provide",
    "regarding", "research", "search", "show", "summarize", "summary",
    "tell", "that", "the", "their", "these", "this", "to", "us",
    "we", "what", "when", "where", "which", "who", "why", "with",
    "would", "you", "your", "local", "documents", "document",
    "findings", "results", "relevant",
}


def _extract_arithmetic_expression(task: str) -> str | None:
    """Extract arithmetic written using symbols or common words."""

    match = _ARITHMETIC_PATTERN.search(task)
    if match:
        return match.group(0).strip()

    for pattern, operator in _WORD_ARITHMETIC_PATTERNS:
        match = pattern.search(task)
        if match:
            left, right = match.groups()
            return f"{left} {operator} {right}"

    return None


def _build_document_query(task: str) -> str:
    """Remove common instruction words from a search query."""

    words = re.findall(
        r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*",
        task,
    )

    keywords = [
        word
        for word in words
        if word.casefold() not in _SEARCH_STOPWORDS
    ]

    return " ".join(keywords) if keywords else task.strip()


def _make_step(
    *,
    description: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> PlanStep:
    """Create a single-step local-tool plan."""

    return PlanStep(
        index=0,
        description=description,
        tool_name=tool_name,
        tool_args=tool_args,
    )


async def planner(
    state: AgentState,
    deps: AgentDependencies,
) -> dict[str, Any]:
    """Select an appropriate local tool for the requested task."""

    task = str(state.get("task") or "").strip()

    update = await log_transition(
        state,
        deps,
        "planner",
        "planning",
        "Selecting a suitable local tool for the requested task.",
    )

    # Do not overwrite an existing plan.
    if state.get("plan"):
        return update

    # Stop safely if the task is empty.
    if not task:
        message = "Cannot plan the task because its description is empty."

        update["errors"] = [
            *state.get("errors", []),
            message,
        ]
        update["plan"] = []
        update["abort_requested"] = True

        return update

    task_lower = task.casefold()

    # Route recognizable arithmetic requests to the calculator.
    expression = _extract_arithmetic_expression(task)

    if expression:
        update["plan"] = [
            _make_step(
                description=f"Calculate {expression}",
                tool_name="calculator",
                tool_args={
                    "expression": expression,
                },
            )
        ]

        return update

    # Detect requests that may concern local tabular data.
    csv_keywords = (
        "csv",
        "spreadsheet",
        "sales data",
        "sales revenue",
        "revenue data",
        "dataset",
        "dataframe",
    )

    if any(keyword in task_lower for keyword in csv_keywords):
        # Do not invent a filename or pass an empty filename.
        # Use document search until dataset discovery is implemented.
        search_query = _build_document_query(task)

        update["plan"] = [
            _make_step(
                description=(
                    "Search local documents for information about: "
                    f"{search_query}"
                ),
                tool_name="document_search",
                tool_args={
                    "query": search_query,
                    "top_k": 5,
                },
            )
        ]

        return update

    # General research uses the local document collection.
    # This node does not perform external web searches.
    search_query = _build_document_query(task)

    update["plan"] = [
        _make_step(
            description=(
                "Search local documents for information about: "
                f"{search_query}"
            ),
            tool_name="document_search",
            tool_args={
                "query": search_query,
                "top_k": 5,
            },
        )
    ]

    return update
