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
    # ── Hexaware Corporate ────────────────────────────────────────────────────
    # Deep navy primary, electric blue accent, white content slides.
    # Formal enterprise decks, client-facing proposals, board presentations.
    "hexaware_corporate": DesignSpec(
        primary_color="0A2240",
        secondary_color="000080",
        accent_color="000080",
        text_color="1A1A2E",
        text_light_color="5A6A7A",
        background_color="FFFFFF",
        background_dark_color="060F1E",
        chart_colors=["000080", "FF6B35", "22C55E", "E63946", "F5A623"],
        font_header="Calibri",
        font_body="Calibri",
        motif="left-bar",
        palette_name="Hexaware Corporate",
    ),
    # ── Hexaware Professional ─────────────────────────────────────────────────
    # Near-black primary, Hexaware orange accent, crisp white background.
    # Analyst briefings, technical deep-dives, innovation showcases.
    "hexaware_professional": DesignSpec(
        primary_color="0D0D0D",
        secondary_color="000080",
        accent_color="FF6B35",
        text_color="1A1A1A",
        text_light_color="5A5A6A",
        background_color="FFFFFF",
        background_dark_color="000000",
        chart_colors=["FF6B35", "000080", "22C55E", "E63946", "F5A623"],
        font_header="Arial",
        font_body="Arial",
        motif="corner-accent",
        palette_name="Hexaware Professional",
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
| Name                   | Primary   | Secondary | Accent    | Use when                                      |
|------------------------|-----------|-----------|-----------|-----------------------------------------------|
| Hexaware Corporate     | 0A2240    | 000080    | 000080    | Formal enterprise, board, client proposals    |
| Hexaware Professional  | 0D0D0D    | 000080    | FF6B35    | Analyst briefings, tech deep-dives, innovation|
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

    DESIGN_SYSTEM_PROMPT = """You are a senior presentation designer at Hexaware Technologies.
Your job is to select the correct Hexaware-branded design variant for a slide deck.

IMPORTANT: Hexaware has exactly TWO approved presentation palettes. You MUST choose one:

1. Hexaware Corporate  — deep navy (#0A2240) primary, Navy Blue (#000080) accent.
   Use for: formal enterprise decks, board presentations, client proposals, strategy reviews.

2. Hexaware Professional — near-black (#0D0D0D) primary, Hexaware orange (#FF6B35) accent.
   Use for: analyst briefings, technical deep-dives, innovation showcases, internal workshops.

Do NOT invent new colors. Do NOT use any other palette. Return ONLY valid JSON."""

    DESIGN_USER_TEMPLATE = """Topic: {topic}
Industry: {industry}
User Selected Theme: {theme}

Choose the Hexaware palette that best fits this presentation.
IMPORTANT: Respect the user's theme preference ({theme}) unless there is a strong design reason to override it.

Available palettes:
{palettes}

Return JSON:
{{
  "palette_name": "Hexaware Corporate" or "Hexaware Professional",
  "primary_color": "0A2240" or "0D0D0D",
  "secondary_color": "000080" or "000080",
  "accent_color": "000080" or "FF6B35",
  "text_color": "1A1A2E" or "1A1A1A",
  "text_light_color": "5A6A7A" or "5A5A6A",
  "background_color": "FFFFFF",
  "background_dark_color": "060F1E" or "000000",
  "chart_colors": ["000080","FF6B35","22C55E","E63946","F5A623"] or ["FF6B35","000080","22C55E","E63946","F5A623"],
  "font_header": "Calibri" or "Arial",
  "font_body": "Calibri" or "Arial",
  "motif": "left-bar" or "corner-accent",
  "design_rationale": "1 sentence explaining why this palette fits the topic"
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
            spec = await self._generate_via_llm(topic, industry, theme, execution_id)
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
        self, topic: str, industry: str, theme: str, execution_id: str
    ) -> DesignSpec:
        from langchain_core.messages import HumanMessage, SystemMessage

        user_prompt = self.DESIGN_USER_TEMPLATE.format(
            topic=topic,
            industry=industry,
            theme=theme,
            palettes=AVAILABLE_PALETTES,
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
        """Parse LLM JSON response and snap to the nearest Hexaware palette."""
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in design response")

        data = json.loads(match.group())

        # Snap palette_name to one of the two valid options
        palette_name = str(data.get("palette_name", "")).lower()
        if "professional" in palette_name:
            return FALLBACK_PALETTES["hexaware_professional"]
        # Default to Corporate for any other value
        return FALLBACK_PALETTES["hexaware_corporate"]

    def _fallback_spec(self, theme: str) -> DesignSpec:
        """Return the appropriate Hexaware fallback palette."""
        if "professional" in theme.lower():
            return FALLBACK_PALETTES["hexaware_professional"]
        return FALLBACK_PALETTES["hexaware_corporate"]


# Global singleton
design_agent = DesignAgent()
