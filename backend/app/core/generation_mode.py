"""
Generation mode enum and provider-to-mode default mapping.

Defines the four LLM output modes (artisan, studio, craft, express) and maps
each LLM provider type to its recommended default mode based on capability.

Mode mapping from previous names:
  json    → express
  hybrid  → craft
  code    → studio
  (new)   → artisan
"""

import enum

from app.db.models import ProviderType


class GenerationMode(str, enum.Enum):
    """LLM output generation mode for slide rendering."""

    ARTISAN = "artisan"
    STUDIO = "studio"
    CRAFT = "craft"
    EXPRESS = "express"


PROVIDER_DEFAULT_MODES: dict[ProviderType, GenerationMode] = {
    ProviderType.claude: GenerationMode.ARTISAN,
    ProviderType.openai: GenerationMode.STUDIO,
    ProviderType.groq: GenerationMode.CRAFT,
    ProviderType.local: GenerationMode.EXPRESS,
}
