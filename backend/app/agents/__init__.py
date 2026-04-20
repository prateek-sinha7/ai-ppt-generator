"""
AI Agents for Presentation Intelligence Platform.

This package contains all specialized AI agents:
- Industry Classifier Agent: Automatic industry detection and template selection
- Storyboarding Agent: Deterministic slide structure planning
- Research Agent: Topic analysis and insight generation
- Data Enrichment Agent: Realistic business data generation
- Prompt Engineering Agent: Multi-LLM provider prompt optimization
- Validation Agent: JSON structure validation and error correction
- Quality Scoring Agent: Multi-dimensional quality assessment
- Conflict Resolution Engine: Enforces Storyboarding Agent authority
- Presentation Compiler: Coordinates all agents in sequential phases
"""

from .storyboarding import (
    StoryboardingAgent,
    PresentationPlanJSON,
    SectionPlan,
    SlideType,
    VisualHint,
    TopicComplexity
)
from .conflict_resolution import (
    ConflictResolutionEngine,
    ConflictType,
    ConflictResolution,
    ConflictEvent
)
from .presentation_compiler import (
    PresentationCompiler,
    CompilationPhase,
    PhaseStatus,
    PhaseResult,
    CompilationReport
)
from .research import (
    ResearchAgent,
    ResearchFindings,
    ResearchOutput,
    ResearchInsights,
    research_agent,
)
from .validation import (
    ValidationAgent,
    SlideContentParser,
    ValidationResult,
    ValidationError as ValidationErrorModel,
    validation_agent,
)

__all__ = [
    # Storyboarding
    "StoryboardingAgent",
    "PresentationPlanJSON",
    "SectionPlan",
    "SlideType",
    "VisualHint",
    "TopicComplexity",
    # Conflict Resolution
    "ConflictResolutionEngine",
    "ConflictType",
    "ConflictResolution",
    "ConflictEvent",
    # Presentation Compiler
    "PresentationCompiler",
    "CompilationPhase",
    "PhaseStatus",
    "PhaseResult",
    "CompilationReport",
    # Research Agent
    "ResearchAgent",
    "ResearchFindings",
    "ResearchOutput",
    "ResearchInsights",
    "research_agent",
    # Validation Agent
    "ValidationAgent",
    "SlideContentParser",
    "ValidationResult",
    "ValidationErrorModel",
    "validation_agent",
]
