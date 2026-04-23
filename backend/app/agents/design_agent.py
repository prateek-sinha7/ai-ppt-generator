"""
Design Agent — Claude-style presentation design system.

This agent runs after IndustryClassifier and before Storyboarding.
It uses the LLM to produce a DesignSpec: a topic-specific color palette,
visual motif, font pairing, and layout guidance — exactly how Claude
"decides the design" before rendering a deck.

The DesignSpec is:
1. Stored in PipelineContext.design_spec
2. Passed to the PromptEngineeringAgent so the LLM generates content
   that is design-aware (e.g. knows the accent color for callouts)
3. Sent to the pptx-service Node.js renderer at export time

Design principles enforced (from SKILL.md):
- Bold, content-informed color palette — specific to THIS topic
- Dominance over equality: one color 60-70%, 1-2 supporting, one sharp accent
- Dark/light contrast sandwich: dark title + conclusion, light content
- One visual motif carried across all slides
- No cream/beige backgrounds, no accent lines under titles
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Design Spec schema
# ---------------------------------------------------------------------------

@dataclass
class DesignSpec:
    """
    Complete design specification for a presentation.
    Produced by DesignAgent, consumed by pptx-service renderer.
    """
    # Color palette (6-char hex, no #)
    primary_color: str          # Dominant color (60-70% visual weight)
    secondary_color: str        # Supporting color
    accent_color: str           # Sharp accent for callouts and highlights
    text_color: str             # Body text
    text_light_color: str       # Muted text (axis labels, captions)
    background_color: str       # Light slide background
    background_dark_color: str  # Dark slide background (title, conclusion)

    # Chart colors (list of 5 hex strings)
    chart_colors: list[str]

    # Typography
    font_header: str            # Header font (e.g. "Georgia", "Arial Black")
    font_body: str              # Body font (e.g. "Calibri", "Arial")

    # Visual motif (carried across all slides)
    motif: str                  # e.g. "left-bar", "corner-accent", "icon-circle"

    # Palette name for logging/debugging
    palette_name: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DesignSpec":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Built-in fallback palettes (used when LLM is unavailable)
# ---------------------------------------------------------------------------

FALLBACK_PALETTES: Dict[str, DesignSpec] = {
    "executive": DesignSpec(
        primary_color="002F6C",
        secondary_color="0077C8",
        accent_color="FFB81C",
        text_color="1A1A1A",
        text_light_color="4A4A4A",
        background_color="FFFFFF",
        background_dark_color="002F6C",
        chart_colors=["0077C8", "FFB81C", "00A651", "ED1C24", "8DC63F"],
        font_header="Georgia",
        font_body="Calibri",
        motif="left-bar",
        palette_name="Midnight Executive",
    ),
    "professional": DesignSpec(
        primary_color="000000",
        secondary_color="86BC25",
        accent_color="00B4CC",
        text_color="1A1A1A",
        text_light_color="4A4A4A",
        background_color="FFFFFF",
        background_dark_color="000000",
        chart_colors=["86BC25", "00B4CC", "FF8C00", "662D91", "009639"],
        font_header="Arial Black",
        font_body="Arial",
        motif="corner-accent",
        palette_name="Charcoal Minimal",
    ),
    "dark_modern": DesignSpec(
        primary_color="1E2761",
        secondary_color="CADCFC",
        accent_color="FFFFFF",
        text_color="DCDCDC",
        text_light_color="A0A0A0",
        background_color="121212",
        background_dark_color="0A0A0A",
        chart_colors=["CADCFC", "FFFFFF", "7EC8E3", "A8D8EA", "B8D4E8"],
        font_header="Calibri",
        font_body="Calibri Light",
        motif="glow-dot",
        palette_name="Midnight Executive",
    ),
    "corporate": DesignSpec(
        primary_color="002855",
        secondary_color="005288",
        accent_color="0078AC",
        text_color="212121",
        text_light_color="646464",
        background_color="FFFFFF",
        background_dark_color="002855",
        chart_colors=["002855", "005288", "0078AC", "4682B4", "8CAAC8"],
        font_header="Calibri",
        font_body="Calibri",
        motif="left-bar",
        palette_name="Corporate Navy",
    ),
}

# Industry → palette hints for the LLM prompt
INDUSTRY_PALETTE_HINTS: Dict[str, str] = {
    "healthcare": "Trust and calm — teal, navy, or sage. Avoid red (emergency connotations).",
    "finance": "Authority and precision — navy, charcoal, or deep blue with gold accent.",
    "technology": "Innovation — deep blue, teal, or dark with electric accent.",
    "consulting": "Executive credibility — navy or charcoal with gold or lime accent.",
    "energy": "Power and sustainability — deep green, navy, or charcoal.",
    "retail": "Energy and approachability — coral, teal, or warm terracotta.",
    "education": "Clarity and trust — navy, forest green, or teal.",
    "manufacturing": "Precision and reliability — charcoal, steel blue, or navy.",
    "real_estate": "Premium and grounded — warm terracotta, charcoal, or forest.",
    "general": "Professional and distinctive — avoid generic blue; pick colors that reflect the topic.",
}

# Available palettes for the LLM to choose from
AVAILABLE_PALETTES = """
| Name | Primary | Secondary | Accent |
|------|---------|-----------|--------|
| Midnight Executive | 1E2761 (navy) | CADCFC (ice blue) | FFFFFF (white) |
| Forest & Moss | 2C5F2D (forest) | 97BC62 (moss) | F5F5F5 (cream) |
| Coral Energy | F96167 (coral) | F9E795 (gold) | 2F3C7E (navy) |
| Warm Terracotta | B85042 (terracotta) | E7E8D1 (sand) | A7BEAE (sage) |
| Ocean Gradient | 065A82 (deep blue) | 1C7293 (teal) | 21295C (midnight) |
| Charcoal Minimal | 36454F (charcoal) | F2F2F2 (off-white) | 212121 (black) |
| Teal Trust | 028090 (teal) | 00A896 (seafoam) | 02C39A (mint) |
| Berry & Cream | 6D2E46 (berry) | A26769 (dusty rose) | ECE2D0 (cream) |
| Sage Calm | 84B59F (sage) | 69A297 (eucalyptus) | 50808E (slate) |
| Cherry Bold | 990011 (cherry) | FCF6F5 (off-white) | 2F3C7E (navy) |
"""

AVAILABLE_MOTIFS = """
- left-bar: Thin colored left border on content cards
- corner-accent: Small colored square in top-left corner of slides
- icon-circle: Icons in colored circles next to section headers
- stat-callout: Large number callouts with colored backgrounds
- glow-dot: Subtle colored dot accent near titles
"""

AVAILABLE_FONT_PAIRS = """
| Header | Body |
|--------|------|
| Georgia | Calibri |
| Arial Black | Arial |
| Calibri | Calibri Light |
| Cambria | Calibri |
| Trebuchet MS | Calibri |
"""


# ---------------------------------------------------------------------------
# Design Agent
# ---------------------------------------------------------------------------

class DesignAgent:
    """
    Produces a DesignSpec for a presentation using the LLM.

    The LLM is asked to:
    1. Pick a color palette that feels designed for THIS specific topic
    2. Choose a visual motif to carry across all slides
    3. Select a font pairing
    4. Justify the choices briefly

    Falls back to a built-in palette if the LLM call fails.
    """

    DESIGN_SYSTEM_PROMPT = """You are a senior presentation designer at a top consulting firm.
Your job is to choose a visual design system for a slide deck on a specific topic.

Design principles you MUST follow:
- Pick a bold, content-informed color palette: it should feel designed for THIS topic specifically.
  If swapping your colors into a completely different presentation would still "work," you haven't
  made specific enough choices.
- Dominance over equality: one color should dominate (60-70% visual weight), with 1-2 supporting
  tones and one sharp accent. Never give all colors equal weight.
- Dark/light contrast: the title and conclusion slides use a dark background; content slides use
  a light background ("sandwich" structure).
- Commit to ONE visual motif and carry it across every slide.
- NEVER default to cream/beige backgrounds (no F5F5DC, FAF0E6, FAEBD7, FFF8E1).
- NEVER use accent lines under titles.
- Use white (FFFFFF) or a palette color for backgrounds — not warm neutrals.

Return ONLY valid JSON. No markdown, no explanation."""

    DESIGN_USER_TEMPLATE = """Topic: {topic}
Industry: {industry}
Industry palette guidance: {palette_hint}

Available palettes to choose from (or create your own variation):
{palettes}

Available visual motifs:
{motifs}

Available font pairings:
{font_pairs}

Choose the design system that best fits this specific topic. Return JSON:
{{
  "palette_name": "string (name of chosen palette or your custom name)",
  "primary_color": "6-char hex (no #) — dominant color",
  "secondary_color": "6-char hex (no #) — supporting color",
  "accent_color": "6-char hex (no #) — sharp accent for callouts",
  "text_color": "6-char hex (no #) — body text on light background",
  "text_light_color": "6-char hex (no #) — muted text, axis labels",
  "background_color": "6-char hex (no #) — light slide background (use FFFFFF or near-white)",
  "background_dark_color": "6-char hex (no #) — dark slide background (title + conclusion)",
  "chart_colors": ["hex1", "hex2", "hex3", "hex4", "hex5"],
  "font_header": "font name from the available pairs",
  "font_body": "font name from the available pairs",
  "motif": "motif name from the available list",
  "design_rationale": "1-2 sentences explaining why these choices fit this topic"
}}"""

    def __init__(self) -> None:
        self._llm_client = None

    def _get_llm_client(self):
        """Lazy-load the LLM provider."""
        if self._llm_client is None:
            try:
                from app.services.llm_provider import provider_factory
                self._llm_client = provider_factory
            except Exception as e:
                logger.warning("design_agent_llm_unavailable", error=str(e))
        return self._llm_client

    async def generate_design_spec(
        self,
        topic: str,
        industry: str,
        theme: str = "corporate",
        execution_id: str = "",
    ) -> DesignSpec:
        """
        Generate a DesignSpec for the given topic and industry.

        Tries the LLM first; falls back to built-in palette on any failure.
        """
        logger.info(
            "design_agent_started",
            topic=topic[:80],
            industry=industry,
            execution_id=execution_id,
        )

        try:
            spec = await self._generate_via_llm(topic, industry, execution_id)
            logger.info(
                "design_agent_completed",
                palette=spec.palette_name,
                motif=spec.motif,
                execution_id=execution_id,
            )
            return spec
        except Exception as exc:
            logger.warning(
                "design_agent_llm_failed_using_fallback",
                error=str(exc),
                execution_id=execution_id,
            )
            return self._fallback_spec(theme)

    async def _generate_via_llm(
        self, topic: str, industry: str, execution_id: str
    ) -> DesignSpec:
        from langchain_core.messages import HumanMessage, SystemMessage

        palette_hint = INDUSTRY_PALETTE_HINTS.get(
            industry.lower().replace(" ", "_"), INDUSTRY_PALETTE_HINTS["general"]
        )

        user_prompt = self.DESIGN_USER_TEMPLATE.format(
            topic=topic,
            industry=industry,
            palette_hint=palette_hint,
            palettes=AVAILABLE_PALETTES,
            motifs=AVAILABLE_MOTIFS,
            font_pairs=AVAILABLE_FONT_PAIRS,
        )

        factory = self._get_llm_client()
        if factory is None:
            raise RuntimeError("LLM provider unavailable")

        async def call_llm(client):
            messages = [
                SystemMessage(content=self.DESIGN_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
            response = await client.ainvoke(messages)
            return response.content

        raw = await factory.call_with_failover(
            call_llm,
            execution_id=execution_id,
            industry=industry,
        )

        return self._parse_design_response(raw)

    def _parse_design_response(self, raw: str) -> DesignSpec:
        """Parse LLM JSON response into a DesignSpec."""
        # Strip markdown fences
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

        # Extract JSON object
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in design response")

        data = json.loads(match.group())

        # Validate and sanitize hex colors
        def clean_hex(val: str, fallback: str) -> str:
            if not val:
                return fallback
            val = str(val).strip().lstrip("#")
            if len(val) == 6 and all(c in "0123456789ABCDEFabcdef" for c in val):
                return val.upper()
            return fallback

        chart_colors = data.get("chart_colors", [])
        if not isinstance(chart_colors, list) or len(chart_colors) < 5:
            chart_colors = ["0077C8", "FFB81C", "00A651", "ED1C24", "8DC63F"]

        return DesignSpec(
            palette_name=str(data.get("palette_name", "Custom")),
            primary_color=clean_hex(data.get("primary_color"), "002F6C"),
            secondary_color=clean_hex(data.get("secondary_color"), "0077C8"),
            accent_color=clean_hex(data.get("accent_color"), "FFB81C"),
            text_color=clean_hex(data.get("text_color"), "1A1A1A"),
            text_light_color=clean_hex(data.get("text_light_color"), "4A4A4A"),
            background_color=clean_hex(data.get("background_color"), "FFFFFF"),
            background_dark_color=clean_hex(data.get("background_dark_color"), "002F6C"),
            chart_colors=[clean_hex(c, "0077C8") for c in chart_colors[:5]],
            font_header=str(data.get("font_header", "Georgia")),
            font_body=str(data.get("font_body", "Calibri")),
            motif=str(data.get("motif", "left-bar")),
        )

    def _fallback_spec(self, theme: str) -> DesignSpec:
        """Return a built-in fallback palette."""
        key = theme.replace("-", "_").lower()
        return FALLBACK_PALETTES.get(key, FALLBACK_PALETTES["corporate"])


# Global singleton
design_agent = DesignAgent()
