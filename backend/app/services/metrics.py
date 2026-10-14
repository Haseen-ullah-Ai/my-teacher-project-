"""Prometheus metrics for research runs and controlled tool execution."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

runs_total = Counter("researchpilot_runs_total", "Research runs by terminal status", ["status"])
tool_calls_total = Counter(
    "researchpilot_tool_calls_total", "Controlled tool calls by tool and status", ["tool", "status"]
)
tool_duration_seconds = Histogram(
    "researchpilot_tool_duration_seconds",
    "Controlled tool execution duration in seconds",
    ["tool"],
)
run_duration_seconds = Histogram(
    "researchpilot_run_duration_seconds",
    "Research run duration in seconds",
)
retries_total = Counter("researchpilot_retries_total", "Tool retries scheduled")


def record_tool_call(tool: str, status: str, duration_seconds: float) -> None:
    """Record a tool attempt and observe its duration."""
    tool_calls_total.labels(tool=tool, status=status).inc()
    tool_duration_seconds.labels(tool=tool).observe(max(0, duration_seconds))


def render_metrics() -> tuple[bytes, str]:
    """Return the current Prometheus exposition and content type."""
    return generate_latest(), CONTENT_TYPE_LATEST
