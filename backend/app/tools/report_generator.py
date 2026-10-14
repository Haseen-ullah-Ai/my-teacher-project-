"""Render structured report drafts to Markdown and styled PDF files."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings
from app.tools.base import BaseTool
from app.tools.schemas import ReportDraft, ReportEvidenceReference, ReportGeneratorOutput


class ReportGeneratorTool(BaseTool[ReportDraft, ReportGeneratorOutput]):
    """Produce local Markdown and PDF report artifacts."""

    name = "report_generator"
    description = "Render a validated structured research report as Markdown and styled PDF."
    input_model = ReportDraft
    output_model = ReportGeneratorOutput
    timeout = 30.0

    def __init__(self, reports_dir: Path | None = None, timeout: float | None = None) -> None:
        self.reports_dir = (reports_dir or settings.reports_root).resolve()
        if timeout is not None:
            self.timeout = timeout

    async def run(self, input: ReportDraft) -> ReportGeneratorOutput:
        """Render and persist both report formats without blocking the event loop."""
        markdown = self._to_markdown(input)
        token = uuid4().hex[:12]
        slug = re.sub(r"[^a-z0-9]+", "-", input.title.lower()).strip("-")[:60] or "research-report"
        markdown_path = self.reports_dir / f"{slug}-{token}.md"
        pdf_path = self.reports_dir / f"{slug}-{token}.pdf"
        await asyncio.to_thread(self._write_files, input, markdown, markdown_path, pdf_path)
        return ReportGeneratorOutput(
            markdown=markdown,
            markdown_path=str(markdown_path),
            pdf_path=str(pdf_path),
        )

    @staticmethod
    def _reference_lines(references: Sequence[ReportEvidenceReference]) -> str:
        """Format evidence references for the report body."""
        rendered = []
        for reference in references:
            rendered.append(f"- {reference.citation} (`{reference.reference}`)")
        return "\n".join(rendered)

    @classmethod
    def _to_markdown(cls, draft: ReportDraft) -> str:
        """Build Markdown in the stable structured draft order."""
        parts = [f"# {draft.title}", "", "## Executive Summary", "", draft.executive_summary, ""]
        for section in draft.sections:
            parts.extend([f"## {section.heading}", "", section.body, ""])
            citations = cls._reference_lines(section.evidence_refs)
            if citations:
                parts.extend(["**Evidence**", citations, ""])

        if draft.findings:
            parts.extend(["## Findings", ""])
            for finding in draft.findings:
                parts.append(f"- {finding.statement}")
                for citation in finding.evidence_refs:
                    parts.append(f"  - {citation.citation} (`{citation.reference}`)")
            parts.append("")

        if draft.recommendations:
            parts.extend(["## Recommendations", ""])
            parts.extend(f"{index}. {item}" for index, item in enumerate(draft.recommendations, 1))
            parts.append("")

        if draft.limitations:
            parts.extend(["## Limitations", ""])
            parts.extend(f"- {item}" for item in draft.limitations)
            parts.append("")

        for table in draft.appendix_tables:
            parts.extend([f"## {table.title}", ""])
            parts.append("| " + " | ".join(table.columns) + " |")
            parts.append("| " + " | ".join("---" for _ in table.columns) + " |")
            parts.extend(
                "| " + " | ".join(str(value) for value in row) + " |" for row in table.rows
            )
            parts.append("")

        return "\n".join(parts).rstrip() + "\n"

    @classmethod
    def _write_files(
        cls,
        draft: ReportDraft,
        markdown: str,
        markdown_path: Path,
        pdf_path: Path,
    ) -> None:
        """Write Markdown and a styled PDF document."""
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=styles["Title"],
                alignment=TA_CENTER,
                textColor=colors.HexColor("#12304A"),
                spaceAfter=14,
            )
        )
        styles.add(
            ParagraphStyle(
                name="ReportHeading",
                parent=styles["Heading2"],
                textColor=colors.HexColor("#126782"),
                spaceBefore=12,
                spaceAfter=6,
            )
        )

        story: list[object] = [Paragraph(cls._escape(draft.title), styles["ReportTitle"])]
        story.extend(
            [
                Paragraph("Executive Summary", styles["ReportHeading"]),
                Paragraph(cls._escape(draft.executive_summary), styles["BodyText"]),
                Spacer(1, 5 * mm),
            ]
        )
        for section in draft.sections:
            story.append(Paragraph(cls._escape(section.heading), styles["ReportHeading"]))
            story.append(Paragraph(cls._escape(section.body), styles["BodyText"]))
            for reference in section.evidence_refs:
                story.append(
                    Paragraph(
                        cls._escape(f"Evidence: {reference.citation} [{reference.reference}]"),
                        styles["Italic"],
                    )
                )
        if draft.findings:
            story.append(Paragraph("Findings", styles["ReportHeading"]))
            story.extend(
                Paragraph(cls._escape(f"- {finding.statement}"), styles["BodyText"])
                for finding in draft.findings
            )
        if draft.recommendations:
            story.append(Paragraph("Recommendations", styles["ReportHeading"]))
            story.extend(
                Paragraph(cls._escape(f"{index}. {item}"), styles["BodyText"])
                for index, item in enumerate(draft.recommendations, 1)
            )
        if draft.limitations:
            story.append(Paragraph("Limitations", styles["ReportHeading"]))
            story.extend(
                Paragraph(cls._escape(f"- {item}"), styles["BodyText"])
                for item in draft.limitations
            )
        for appendix in draft.appendix_tables:
            story.append(Paragraph(cls._escape(appendix.title), styles["ReportHeading"]))
            table_data = [
                [cls._escape(value) for value in appendix.columns],
                *[[cls._escape(str(value)) for value in row] for row in appendix.rows],
            ]
            report_table = Table(table_data, repeatRows=1, hAlign="LEFT")
            report_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12304A")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#F1F5F9")],
                        ),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.extend([report_table, Spacer(1, 4 * mm)])

        document = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=draft.title,
            author="ResearchPilot",
        )
        document.build(story)

    @staticmethod
    def _escape(value: str) -> str:
        """Escape XML-sensitive characters used by ReportLab Paragraph."""
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
