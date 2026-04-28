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
    "ocean_depths": DesignSpec(
        primary_color="1A2332",
        secondary_color="2D8B8B",
        accent_color="A8DADC",
        text_color="1A2332",
        text_light_color="6B7280",
        background_color="F1FAEE",
        background_dark_color="0D1520",
        chart_colors=["1A2332", "2D8B8B", "A8DADC", "5BA3A3", "3D6B6B"],
        font_header="Georgia",
        font_body="Calibri",
        motif="left-bar",
        palette_name="Ocean Depths",
    ),
    "sunset_boulevard": DesignSpec(
        primary_color="E76F51",
        secondary_color="F4A261",
        accent_color="E9C46A",
        text_color="264653",
        text_light_color="6B7280",
        background_color="FFFFFF",
        background_dark_color="1A2F3A",
        chart_colors=["E76F51", "F4A261", "E9C46A", "264653", "2A9D8F"],
        font_header="Georgia",
        font_body="Calibri",
        motif="corner-accent",
        palette_name="Sunset Boulevard",
    ),
    "forest_canopy": DesignSpec(
        primary_color="2D4A2B",
        secondary_color="7D8471",
        accent_color="A4AC86",
        text_color="2D4A2B",
        text_light_color="6B7280",
        background_color="FAF9F6",
        background_dark_color="1A2D1A",
        chart_colors=["2D4A2B", "7D8471", "A4AC86", "5A7A58", "8B9B78"],
        font_header="Cambria",
        font_body="Calibri",
        motif="left-bar",
        palette_name="Forest Canopy",
    ),
    "modern_minimalist": DesignSpec(
        primary_color="36454F",
        secondary_color="708090",
        accent_color="D3D3D3",
        text_color="36454F",
        text_light_color="708090",
        background_color="FFFFFF",
        background_dark_color="1A2028",
        chart_colors=["36454F", "708090", "A0A0A0", "505A64", "8896A0"],
        font_header="Calibri",
        font_body="Calibri Light",
        motif="left-bar",
        palette_name="Modern Minimalist",
    ),
    "golden_hour": DesignSpec(
        primary_color="F4A900",
        secondary_color="C1666B",
        accent_color="D4B896",
        text_color="4A403A",
        text_light_color="6B7280",
        background_color="FFFFFF",
        background_dark_color="2A2420",
        chart_colors=["F4A900", "C1666B", "D4B896", "8B6914", "A0524E"],
        font_header="Georgia",
        font_body="Calibri",
        motif="stat-callout",
        palette_name="Golden Hour",
    ),
    "arctic_frost": DesignSpec(
        primary_color="4A6FA5",
        secondary_color="C0C0C0",
        accent_color="D4E4F7",
        text_color="2C3E50",
        text_light_color="6B7280",
        background_color="FAFAFA",
        background_dark_color="2A3A50",
        chart_colors=["4A6FA5", "7A9CC6", "A8C4E0", "5580A8", "3D5A80"],
        font_header="Calibri",
        font_body="Calibri Light",
        motif="left-bar",
        palette_name="Arctic Frost",
    ),
    "desert_rose": DesignSpec(
        primary_color="D4A5A5",
        secondary_color="B87D6D",
        accent_color="E8D5C4",
        text_color="5D2E46",
        text_light_color="6B7280",
        background_color="FFFFFF",
        background_dark_color="3A1A2A",
        chart_colors=["D4A5A5", "B87D6D", "E8D5C4", "5D2E46", "9B6B6B"],
        font_header="Georgia",
        font_body="Calibri",
        motif="corner-accent",
        palette_name="Desert Rose",
    ),
    "tech_innovation": DesignSpec(
        primary_color="0066FF",
        secondary_color="00FFFF",
        accent_color="00CCCC",
        text_color="FFFFFF",
        text_light_color="9CA3AF",
        background_color="1E1E1E",
        background_dark_color="0A0A0A",
        chart_colors=["0066FF", "00FFFF", "00CCCC", "3388FF", "66DDFF"],
        font_header="Calibri",
        font_body="Calibri Light",
        motif="glow-dot",
        palette_name="Tech Innovation",
    ),
    "botanical_garden": DesignSpec(
        primary_color="4A7C59",
        secondary_color="F9A620",
        accent_color="B7472A",
        text_color="3A3A3A",
        text_light_color="6B7280",
        background_color="F5F3ED",
        background_dark_color="2A3A2A",
        chart_colors=["4A7C59", "F9A620", "B7472A", "6B9B78", "D4881A"],
        font_header="Cambria",
        font_body="Calibri",
        motif="icon-circle",
        palette_name="Botanical Garden",
    ),
    "midnight_galaxy": DesignSpec(
        primary_color="4A4E8F",
        secondary_color="A490C2",
        accent_color="E6E6FA",
        text_color="E6E6FA",
        text_light_color="9CA3AF",
        background_color="2B1E3E",
        background_dark_color="1A1028",
        chart_colors=["4A4E8F", "A490C2", "E6E6FA", "6B6FAF", "C4B8D8"],
        font_header="Calibri",
        font_body="Calibri Light",
        motif="glow-dot",
        palette_name="Midnight Galaxy",
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
| Instrument Sans | Calibri |
| Work Sans | Calibri Light |
| Lora | Calibri |
| Outfit | Calibri |
| Crimson Pro | Calibri |
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

AVOID — these are common design mistakes:
- No cream or beige backgrounds (no F5F5DC, FAF0E6, FAEBD7, FFF8E1). Use white (FFFFFF) or a palette color.
- No repeated layouts across slides — vary columns, cards, and callouts.
- No centered body text — left-align paragraphs and lists; center only titles.
- No accent lines under titles — these are a hallmark of AI-generated slides.
- Pick colors specific to the topic, not generic blue — if the topic is healthcare, use teal/sage; if finance, use navy/gold.

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
        theme: str = "ocean-depths",
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
        return FALLBACK_PALETTES.get(key, FALLBACK_PALETTES["ocean_depths"])


# Global singleton
design_agent = DesignAgent()
