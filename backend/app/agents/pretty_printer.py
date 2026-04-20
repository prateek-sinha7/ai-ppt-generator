"""
Slide Content Pretty Printer (Req 26)

Formats Slide_JSON objects into human-readable presentation outlines for
debugging, review, and audit logs.

Supported output formats:
  'text'     → plain text outline (default, for logs)
  'markdown' → markdown with headers and bullets (for review UI)
  'json'     → indented JSON (for debugging)

Performance: formatting 50 slides completes in < 2 seconds (pure in-memory
string operations, no I/O).
"""

import json
from typing import Any, Dict, List, Literal

import structlog

logger = structlog.get_logger(__name__)

OutputFormat = Literal["text", "markdown", "json"]


class SlidePrettyPrinter:
    """
    Formats Slide_JSON into human-readable outlines.

    Supports three output formats:
    - text:     plain-text outline suitable for logs and terminals
    - markdown: GitHub-flavoured markdown for review UIs
    - json:     pretty-printed indented JSON for debugging
    """

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def format(
        self,
        presentation: Dict[str, Any],
        output_format: OutputFormat = "text",
    ) -> str:
        """
        Format a complete presentation into a human-readable string.

        Args:
            presentation: Slide_JSON dict (schema_version, slides, …)
            output_format: 'text' | 'markdown' | 'json'

        Returns:
            Formatted string representation of the presentation.

        Raises:
            ValueError: if output_format is not one of the supported values.
        """
        if output_format not in ("text", "markdown", "json"):
            raise ValueError(
                f"Unsupported output_format '{output_format}'. "
                "Choose from: 'text', 'markdown', 'json'."
            )

        if output_format == "json":
            return json.dumps(presentation, indent=2, default=str)

        slides: List[Dict[str, Any]] = presentation.get("slides", [])
        total = presentation.get("total_slides", len(slides))
        schema_version = presentation.get("schema_version", "1.0.0")
        presentation_id = presentation.get("presentation_id", "")

        if output_format == "markdown":
            return self._format_markdown(
                slides, total, schema_version, presentation_id
            )

        # default: text
        return self._format_text(slides, total, schema_version, presentation_id)

    def format_slide(self, slide: Dict[str, Any]) -> str:
        """
        Format a single slide into a plain-text structured outline.

        Args:
            slide: Individual slide dict from Slide_JSON.

        Returns:
            Multi-line string representing the slide outline.
        """
        slide_number = slide.get("slide_number", "?")
        slide_type = str(slide.get("type", "unknown")).upper()
        title = slide.get("title", "")

        lines: List[str] = [f"[{slide_number}] {slide_type}: {title}"]

        content: Dict[str, Any] = slide.get("content", {})

        # Bullets
        for bullet in content.get("bullets", []):
            lines.append(f"  • {bullet}")

        # Chart
        chart_data = content.get("chart_data")
        if chart_data:
            chart_type = chart_data.get("chart_type", "unknown")
            lines.append(f"  [CHART: {chart_type}]")

        # Table
        table_data = content.get("table_data")
        if table_data:
            row_count = len(table_data.get("rows", []))
            lines.append(f"  [TABLE: {row_count} rows]")

        # Comparison
        comparison_data = content.get("comparison_data")
        if comparison_data:
            left_title = comparison_data.get("left_title", "Left")
            right_title = comparison_data.get("right_title", "Right")
            lines.append(f"  [COMPARISON: {left_title} vs {right_title}]")

        # Optional visual elements
        icon_name = content.get("icon_name")
        if icon_name:
            lines.append(f"  [ICON: {icon_name}]")

        highlight_text = content.get("highlight_text")
        if highlight_text:
            lines.append(f"  [HIGHLIGHT: {highlight_text}]")

        # Visual hint
        visual_hint = slide.get("visual_hint")
        if visual_hint:
            lines.append(f"  visual_hint: {visual_hint}")

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _format_text(
        self,
        slides: List[Dict[str, Any]],
        total: int,
        schema_version: str,
        presentation_id: str,
    ) -> str:
        """Render a plain-text outline of the full presentation."""
        header_parts = [f"Presentation ({total} slides)"]
        if presentation_id:
            header_parts.append(f"id={presentation_id}")
        header_parts.append(f"schema={schema_version}")
        header = " | ".join(header_parts)

        separator = "-" * len(header)
        sections = [header, separator]

        for slide in slides:
            sections.append(self.format_slide(slide))

        sections.append(separator)
        return "\n".join(sections)

    def _format_markdown(
        self,
        slides: List[Dict[str, Any]],
        total: int,
        schema_version: str,
        presentation_id: str,
    ) -> str:
        """Render a GitHub-flavoured markdown outline of the full presentation."""
        lines: List[str] = []

        # Header
        lines.append("# Presentation Outline")
        lines.append("")
        meta_parts = [f"**Slides:** {total}", f"**Schema:** `{schema_version}`"]
        if presentation_id:
            meta_parts.append(f"**ID:** `{presentation_id}`")
        lines.append(" | ".join(meta_parts))
        lines.append("")
        lines.append("---")
        lines.append("")

        for slide in slides:
            lines.extend(self._format_slide_markdown(slide))
            lines.append("")

        return "\n".join(lines)

    def _format_slide_markdown(self, slide: Dict[str, Any]) -> List[str]:
        """Render a single slide as markdown lines."""
        slide_number = slide.get("slide_number", "?")
        slide_type = str(slide.get("type", "unknown")).upper()
        title = slide.get("title", "")

        lines: List[str] = [
            f"## Slide {slide_number}: {title}",
            f"*Type: {slide_type}*",
            "",
        ]

        content: Dict[str, Any] = slide.get("content", {})

        bullets = content.get("bullets", [])
        if bullets:
            for bullet in bullets:
                lines.append(f"- {bullet}")
            lines.append("")

        chart_data = content.get("chart_data")
        if chart_data:
            chart_type = chart_data.get("chart_type", "unknown")
            lines.append(f"> 📊 **Chart:** {chart_type}")
            lines.append("")

        table_data = content.get("table_data")
        if table_data:
            row_count = len(table_data.get("rows", []))
            lines.append(f"> 📋 **Table:** {row_count} rows")
            lines.append("")

        comparison_data = content.get("comparison_data")
        if comparison_data:
            left_title = comparison_data.get("left_title", "Left")
            right_title = comparison_data.get("right_title", "Right")
            lines.append(f"> ⚖️ **Comparison:** {left_title} vs {right_title}")
            lines.append("")

        icon_name = content.get("icon_name")
        if icon_name:
            lines.append(f"> 🔷 **Icon:** `{icon_name}`")
            lines.append("")

        highlight_text = content.get("highlight_text")
        if highlight_text:
            lines.append(f"> ✨ **Highlight:** {highlight_text}")
            lines.append("")

        visual_hint = slide.get("visual_hint")
        if visual_hint:
            lines.append(f"*Layout: `{visual_hint}`*")

        return lines
