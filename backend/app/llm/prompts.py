"""Versioned Jinja2 prompt templates for agent workflow stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_ENVIRONMENT = Environment(
    loader=FileSystemLoader(_PROMPT_DIR),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)
_ALLOWED_PROMPTS = {"planner", "analyzer", "validator", "reporter"}


def render_prompt(name: str, **context: Any) -> str:
    """Render a named, reviewed prompt template from the local prompts directory."""
    if name not in _ALLOWED_PROMPTS:
        raise ValueError(f"Unknown prompt template: {name}")
    return _ENVIRONMENT.get_template(f"{name}.md").render(**context)
