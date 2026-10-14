"""Write the compiled graph's Mermaid representation to the documentation tree."""

from __future__ import annotations

import sys
from pathlib import Path

from app.agent.graph import build_graph


def export_graph(destination: Path | None = None) -> Path:
    """Export the current graph topology to docs/agent_graph.mmd."""
    repository_root = Path(__file__).resolve().parents[3]
    output_path = destination or repository_root / "docs" / "agent_graph.mmd"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_graph().get_graph().draw_mermaid(), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    sys.stdout.write(f"{export_graph()}\n")
