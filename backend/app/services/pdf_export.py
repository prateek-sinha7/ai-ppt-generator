"""
PDF Export Service — generates PDF documents from Slide_JSON using reportlab.
"""
import io
from typing import Any, Dict, List, Optional

import structlog
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Theme color palettes (hex strings for reportlab HexColor)
# ---------------------------------------------------------------------------

THEME_PALETTES: Dict[str, Dict[str, str]] = {
    "ocean-depths": {
        "primary": "#1a2332",
        "secondary": "#2d8b8b",
        "accent": "#a8dadc",
        "text": "#1a2332",
        "text_light": "#6b7280",
        "background": "#f1faee",
        "header_bar": "#1a2332",
        "chart_colors": ["#1a2332", "#2d8b8b", "#a8dadc", "#5ba3a3", "#3d6b6b", "#82b4b4", "#6b7280"],
    },
    "sunset-boulevard": {
        "primary": "#e76f51",
        "secondary": "#f4a261",
        "accent": "#e9c46a",
        "text": "#264653",
        "text_light": "#6b7280",
        "background": "#ffffff",
        "header_bar": "#264653",
        "chart_colors": ["#e76f51", "#f4a261", "#e9c46a", "#264653", "#2a9d8f", "#b45a41", "#6b7280"],
    },
    "forest-canopy": {
        "primary": "#2d4a2b",
        "secondary": "#7d8471",
        "accent": "#a4ac86",
        "text": "#2d4a2b",
        "text_light": "#6b7280",
        "background": "#faf9f6",
        "header_bar": "#2d4a2b",
        "chart_colors": ["#2d4a2b", "#7d8471", "#a4ac86", "#5a7a58", "#8b9b78", "#466444", "#6b7280"],
    },
    "modern-minimalist": {
        "primary": "#36454f",
        "secondary": "#708090",
        "accent": "#d3d3d3",
        "text": "#36454f",
        "text_light": "#708090",
        "background": "#ffffff",
        "header_bar": "#36454f",
        "chart_colors": ["#36454f", "#708090", "#a0a0a0", "#505a64", "#889698", "#283c46", "#b4b4b4"],
    },
    "golden-hour": {
        "primary": "#f4a900",
        "secondary": "#c1666b",
        "accent": "#d4b896",
        "text": "#4a403a",
        "text_light": "#6b7280",
        "background": "#ffffff",
        "header_bar": "#4a403a",
        "chart_colors": ["#f4a900", "#c1666b", "#d4b896", "#8b6914", "#a0524e", "#b48c3c", "#6b7280"],
    },
    "arctic-frost": {
        "primary": "#4a6fa5",
        "secondary": "#c0c0c0",
        "accent": "#d4e4f7",
        "text": "#2c3e50",
        "text_light": "#6b7280",
        "background": "#fafafa",
        "header_bar": "#4a6fa5",
        "chart_colors": ["#4a6fa5", "#7a9cc6", "#a8c4e0", "#5580a8", "#3d5a80", "#648cb4", "#6b7280"],
    },
    "desert-rose": {
        "primary": "#d4a5a5",
        "secondary": "#b87d6d",
        "accent": "#e8d5c4",
        "text": "#5d2e46",
        "text_light": "#6b7280",
        "background": "#ffffff",
        "header_bar": "#5d2e46",
        "chart_colors": ["#d4a5a5", "#b87d6d", "#e8d5c4", "#5d2e46", "#9b6b6b", "#aa8c8c", "#6b7280"],
    },
    "tech-innovation": {
        "primary": "#0066ff",
        "secondary": "#00ffff",
        "accent": "#00cccc",
        "text": "#ffffff",
        "text_light": "#9ca3af",
        "background": "#1e1e1e",
        "header_bar": "#0066ff",
        "chart_colors": ["#0066ff", "#00ffff", "#00cccc", "#3388ff", "#66ddff", "#00aaaa", "#9ca3af"],
    },
    "botanical-garden": {
        "primary": "#4a7c59",
        "secondary": "#f9a620",
        "accent": "#b7472a",
        "text": "#3a3a3a",
        "text_light": "#6b7280",
        "background": "#f5f3ed",
        "header_bar": "#4a7c59",
        "chart_colors": ["#4a7c59", "#f9a620", "#b7472a", "#6b9b78", "#d4881a", "#5a9669", "#6b7280"],
    },
    "midnight-galaxy": {
        "primary": "#4a4e8f",
        "secondary": "#a490c2",
        "accent": "#e6e6fa",
        "text": "#e6e6fa",
        "text_light": "#9ca3af",
        "background": "#2b1e3e",
        "header_bar": "#4a4e8f",
        "chart_colors": ["#4a4e8f", "#a490c2", "#e6e6fa", "#6b6faf", "#c4b8d8", "#5a5ea0", "#9ca3af"],
    },
}

_DEFAULT_THEME = "ocean-depths"


def _resolve_theme(theme: str) -> Dict[str, str]:
    """Resolve a theme name to its color palette, falling back to ocean-depths."""
    key = theme.lower().replace("_", "-")
    return THEME_PALETTES.get(key, THEME_PALETTES[_DEFAULT_THEME])


def _hex(color_str: str) -> HexColor:
    """Convert a hex color string to a reportlab HexColor."""
    return HexColor(color_str)


def _extract_slides(slides_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the slides list from slides_data (dict with 'slides' key or list)."""
    if isinstance(slides_data, list):
        return slides_data
    if isinstance(slides_data, dict):
        slides = slides_data.get("slides", slides_data.get("slide_json", []))
        if isinstance(slides, list):
            return slides
    return []


# ---------------------------------------------------------------------------
# Chart rendering helpers (matplotlib → reportlab Image)
# ---------------------------------------------------------------------------

def _render_chart_image(chart_data: List[Dict[str, Any]], chart_type: str, palette: Dict[str, str]) -> Optional[Image]:
    """Render chart_data as a matplotlib figure and return a reportlab Image."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        labels = [str(item.get("label", item.get("name", f"Item {i}"))) for i, item in enumerate(chart_data)]
        values = []
        for item in chart_data:
            val = item.get("value", item.get("y", 0))
            try:
                values.append(float(val))
            except (TypeError, ValueError):
                values.append(0)

        colors = palette.get("chart_colors", ["#1a2332"])
        bar_colors = [colors[i % len(colors)] for i in range(len(labels))]

        fig, ax = plt.subplots(figsize=(7, 3.5))

        chart_type_lower = (chart_type or "bar").lower()
        if chart_type_lower in ("pie", "donut"):
            wedges, texts, autotexts = ax.pie(
                values, labels=labels, colors=bar_colors, autopct="%1.0f%%",
                startangle=90, textprops={"fontsize": 8},
            )
            if chart_type_lower == "donut":
                centre_circle = plt.Circle((0, 0), 0.55, fc="white")
                ax.add_artist(centre_circle)
        elif chart_type_lower == "line":
            ax.plot(labels, values, color=colors[0], marker="o", linewidth=2)
            ax.set_ylabel("Value", fontsize=8)
            ax.tick_params(axis="both", labelsize=7)
        else:
            ax.bar(labels, values, color=bar_colors)
            ax.set_ylabel("Value", fontsize=8)
            ax.tick_params(axis="both", labelsize=7)

        plt.tight_layout()

        img_buf = io.BytesIO()
        fig.savefig(img_buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        img_buf.seek(0)

        return Image(img_buf, width=6.5 * inch, height=3.2 * inch)
    except Exception:
        logger.warning("pdf_export.chart_render_failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Table rendering helper
# ---------------------------------------------------------------------------

def _build_table(table_data: Dict[str, Any], palette: Dict[str, str], styles: Any) -> Optional[Table]:
    """Build a reportlab Table from slide table_data."""
    try:
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        if not headers and not rows:
            return None

        data = []
        if headers:
            data.append([str(h) for h in headers])
        for row in rows:
            if isinstance(row, dict):
                data.append([str(row.get(h, "")) for h in headers])
            elif isinstance(row, (list, tuple)):
                data.append([str(c) for c in row])

        if not data:
            return None

        col_count = max(len(r) for r in data) if data else 1
        page_width = landscape(A4)[0] - 2 * inch
        col_width = page_width / col_count

        tbl = Table(data, colWidths=[col_width] * col_count)

        header_bg = _hex(palette.get("header_bar", palette["primary"]))
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, _hex("#d1d5db")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, _hex("#f9fafb")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        tbl.setStyle(TableStyle(style_cmds))
        return tbl
    except Exception:
        logger.warning("pdf_export.table_build_failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_pdf(
    slides_data: Dict[str, Any],
    theme: str = "ocean-depths",
    design_spec: Optional[Dict] = None,
) -> bytes:
    """Generate a PDF document from Slide_JSON.

    Args:
        slides_data: Dict with a ``"slides"`` key (list of slide dicts), or a
            plain list of slide dicts.
        theme: Theme identifier (e.g. ``"ocean-depths"``).
        design_spec: Optional design specification dict (currently unused but
            reserved for future refinement).

    Returns:
        PDF file content as ``bytes``.
    """
    palette = _resolve_theme(theme)
    slides = _extract_slides(slides_data)

    buf = io.BytesIO()
    page_w, page_h = landscape(A4)
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.5 * inch,
    )

    base_styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "SlideTitle",
        parent=base_styles["Heading1"],
        fontSize=24,
        leading=30,
        textColor=_hex(palette["primary"]),
        spaceAfter=14,
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    )

    subtitle_style = ParagraphStyle(
        "SlideSubtitle",
        parent=base_styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=_hex(palette.get("secondary", palette["primary"])),
        spaceAfter=10,
        fontName="Helvetica",
        alignment=TA_LEFT,
    )

    bullet_style = ParagraphStyle(
        "SlideBullet",
        parent=base_styles["Normal"],
        fontSize=12,
        leading=17,
        textColor=_hex(palette["text"]),
        spaceAfter=6,
        fontName="Helvetica",
        leftIndent=20,
        bulletIndent=8,
        bulletFontName="Helvetica",
        bulletFontSize=12,
    )

    body_style = ParagraphStyle(
        "SlideBody",
        parent=base_styles["Normal"],
        fontSize=11,
        leading=15,
        textColor=_hex(palette["text"]),
        spaceAfter=6,
        fontName="Helvetica",
    )

    story: List[Any] = []

    for idx, slide in enumerate(slides):
        try:
            _render_slide(slide, story, palette, title_style, subtitle_style, bullet_style, body_style, base_styles)
        except Exception:
            logger.warning("pdf_export.slide_render_failed", slide_index=idx, exc_info=True)

        # Page break after every slide except the last
        if idx < len(slides) - 1:
            story.append(PageBreak())

    if not story:
        # Empty presentation — add a placeholder page
        story.append(Paragraph("No slides to export.", body_style))

    doc.build(story)
    return buf.getvalue()


def _render_slide(
    slide: Dict[str, Any],
    story: List[Any],
    palette: Dict[str, str],
    title_style: ParagraphStyle,
    subtitle_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
    body_style: ParagraphStyle,
    base_styles: Any,
) -> None:
    """Render a single slide's content into the platypus story."""
    title = slide.get("title", "")
    subtitle = slide.get("subtitle", "")
    slide_type = slide.get("type", "content")
    bullets = slide.get("bullets", slide.get("content", []))
    chart_data = slide.get("chart_data", slide.get("chartData", None))
    chart_type = slide.get("chart_type", slide.get("chartType", "bar"))
    table_data = slide.get("table_data", slide.get("tableData", None))

    # Title
    if title:
        story.append(Paragraph(_escape(title), title_style))

    # Subtitle
    if subtitle:
        story.append(Paragraph(_escape(subtitle), subtitle_style))

    # Bullets / content
    if isinstance(bullets, list) and bullets:
        for bullet in bullets:
            text = bullet if isinstance(bullet, str) else str(bullet)
            story.append(Paragraph(f"\u2022  {_escape(text)}", bullet_style))
        story.append(Spacer(1, 8))

    # Chart
    if chart_data and isinstance(chart_data, list):
        chart_img = _render_chart_image(chart_data, chart_type, palette)
        if chart_img:
            story.append(Spacer(1, 6))
            story.append(chart_img)
        else:
            story.append(Paragraph(
                "<i>Chart data available in PPTX format.</i>", body_style
            ))

    # Table
    if table_data and isinstance(table_data, dict):
        tbl = _build_table(table_data, palette, base_styles)
        if tbl:
            story.append(Spacer(1, 6))
            story.append(tbl)


def _escape(text: str) -> str:
    """Escape XML-sensitive characters for reportlab Paragraph markup."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
