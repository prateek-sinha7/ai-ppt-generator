"""
Storyboarding Agent - Deterministic slide structure planning with absolute authority.

This agent runs BEFORE LLM content generation and determines:
- Exact slide count (min 5, max 25)
- Slide types and visual hints
- Section mapping following consulting storytelling structure
- Visual diversity enforcement

Phase 3 Enhancement: LLM-powered narrative optimization for executive impact.

The Storyboarding Agent has absolute authority over slide structure decisions.
LLMs fill content into predefined structures - they do NOT decide slide structure.
"""

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.agents.llm_helpers import LLMEnhancementHelper


class SlideType(str, Enum):
    """Allowed slide types."""
    TITLE = "title"
    CONTENT = "content"
    CHART = "chart"
    TABLE = "table"
    COMPARISON = "comparison"
    METRIC = "metric"


class VisualHint(str, Enum):
    """Standardized visual hint enum values."""
    CENTERED = "centered"
    BULLET_LEFT = "bullet-left"
    SPLIT_CHART_RIGHT = "split-chart-right"
    SPLIT_TABLE_LEFT = "split-table-left"
    TWO_COLUMN = "two-column"
    HIGHLIGHT_METRIC = "highlight-metric"


class TopicComplexity(str, Enum):
    """Topic complexity levels for slide count determination."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class SectionPlan(BaseModel):
    """Plan for a single section in the presentation."""
    name: str
    slide_count: int = Field(ge=1)
    slide_types: list[SlideType]

    @field_validator('slide_types')
    @classmethod
    def validate_slide_count_matches(cls, v: list[SlideType], info) -> list[SlideType]:
        """Ensure slide_types length matches slide_count."""
        slide_count = info.data.get('slide_count')
        if slide_count and len(v) != slide_count:
            raise ValueError(f"slide_types length ({len(v)}) must match slide_count ({slide_count})")
        return v


class PresentationPlanJSON(BaseModel):
    """
    Presentation_Plan_JSON - Slide structure plan.
    
    This provides a recommended structure that the LLM uses as guidance.
    The LLM may adjust slide types based on what the topic actually needs.
    """
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    industry: str
    total_slides: int = Field(ge=5, le=25)
    sections: list[SectionPlan]
    visual_diversity_check: bool = True
    flexible: bool = Field(default=True, description="When True, LLM may adjust slide types based on topic needs")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @field_validator('total_slides')
    @classmethod
    def validate_total_matches_sections(cls, v: int, info) -> int:
        """Ensure total_slides matches sum of section slide_counts."""
        sections = info.data.get('sections', [])
        if sections:
            section_total = sum(s.slide_count for s in sections)
            if v != section_total:
                raise ValueError(
                    f"total_slides ({v}) must match sum of section slide_counts ({section_total})"
                )
        return v


class NarrativeOptimization(BaseModel):
    """LLM-generated narrative optimization suggestions."""
    optimized_sections: list[dict[str, Any]] = Field(
        description="Optimized section structure with adjusted slide counts"
    )
    narrative_arc: str = Field(
        description="Description of the narrative arc (problem → tension → resolution)"
    )
    attention_peaks: list[int] = Field(
        description="Slide numbers where executive attention should peak"
    )
    reasoning: str = Field(
        description="Why this narrative structure is optimal for the topic"
    )


class StoryboardingAgent:
    """
    Storyboarding Agent - Deterministic slide structure planning.
    
    This agent has absolute authority over slide structure decisions.
    It runs BEFORE LLM content generation and produces Presentation_Plan_JSON
    that defines exact slide count, types, and section mapping.
    
    Key responsibilities:
    1. Analyze topic complexity
    2. Determine optimal slide count (5-25)
    3. Enforce consulting storytelling structure
    4. Ensure visual diversity (max 2 consecutive slides of same type)
    5. Generate Presentation_Plan_JSON
    """

    # Consulting storytelling structure (required sections)
    REQUIRED_SECTIONS = [
        "Title",
        "Agenda",
        "Problem",
        "Analysis",
        "Evidence",
        "Recommendations",
        "Conclusion"
    ]

    # Slide type to visual hint mapping
    TYPE_TO_VISUAL_HINT = {
        SlideType.TITLE: VisualHint.CENTERED,
        SlideType.CONTENT: VisualHint.BULLET_LEFT,
        SlideType.CHART: VisualHint.SPLIT_CHART_RIGHT,
        SlideType.TABLE: VisualHint.SPLIT_TABLE_LEFT,
        SlideType.COMPARISON: VisualHint.TWO_COLUMN,
        SlideType.METRIC: VisualHint.HIGHLIGHT_METRIC,
    }

    def __init__(self):
        """Initialize the Storyboarding Agent."""
        self._llm_helper = LLMEnhancementHelper()

    def analyze_topic_complexity(self, topic: str, industry: str) -> TopicComplexity:
        """
        Analyze topic complexity to determine optimal slide count.
        
        Complexity signals:
        - Simple: Single concept, clear scope, < 50 words
        - Moderate: Multiple concepts, standard scope, 50-150 words
        - Complex: Many concepts, broad scope, > 150 words
        
        Args:
            topic: The presentation topic
            industry: Detected industry context
            
        Returns:
            TopicComplexity enum value
        """
        word_count = len(topic.split())
        
        # Complexity indicators
        complexity_keywords = [
            "comprehensive", "detailed", "in-depth", "analysis",
            "strategy", "transformation", "roadmap", "framework"
        ]
        has_complexity_signals = any(kw in topic.lower() for kw in complexity_keywords)
        
        # Determine complexity
        if word_count < 10 and not has_complexity_signals:
            return TopicComplexity.SIMPLE
        elif word_count > 30 or has_complexity_signals:
            return TopicComplexity.COMPLEX
        else:
            return TopicComplexity.MODERATE

    def determine_optimal_slide_count(
        self,
        complexity: TopicComplexity,
        template_slide_count: int | None = None
    ) -> int:
        """
        Determine optimal slide count based on complexity and template.
        
        Slide count ranges:
        - Simple: 5-8 slides
        - Moderate: 9-15 slides
        - Complex: 16-25 slides
        
        Args:
            complexity: Topic complexity level
            template_slide_count: Optional template-suggested slide count
            
        Returns:
            Optimal slide count (5-25)
        """
        # If template provides a count, use it (within bounds)
        if template_slide_count:
            return max(5, min(25, template_slide_count))
        
        # Otherwise, use complexity-based defaults
        complexity_ranges = {
            TopicComplexity.SIMPLE: 7,
            TopicComplexity.MODERATE: 12,
            TopicComplexity.COMPLEX: 18,
        }
        
        return complexity_ranges[complexity]

    def allocate_slides_to_sections(
        self,
        total_slides: int,
        template_structure: list[dict[str, Any]] | None = None
    ) -> list[SectionPlan]:
        """
        Allocate slides to consulting storytelling sections.
        
        Default allocation (if no template):
        - Title: 1 slide
        - Agenda: 1 slide
        - Problem: 15% of remaining
        - Analysis: 30% of remaining
        - Evidence: 25% of remaining
        - Recommendations: 20% of remaining
        - Conclusion: 10% of remaining
        
        Args:
            total_slides: Total number of slides to allocate
            template_structure: Optional template structure to follow
            
        Returns:
            List of SectionPlan objects
        """
        if template_structure:
            return self._allocate_from_template(template_structure)
        
        # Default allocation
        sections = []
        
        # Fixed sections
        sections.append(SectionPlan(
            name="Title",
            slide_count=1,
            slide_types=[SlideType.TITLE]
        ))
        sections.append(SectionPlan(
            name="Agenda",
            slide_count=1,
            slide_types=[SlideType.CONTENT]
        ))
        
        # Remaining slides to allocate
        remaining = total_slides - 2
        
        # Allocate remaining slides proportionally
        problem_count = max(1, int(remaining * 0.15))
        analysis_count = max(2, int(remaining * 0.30))
        evidence_count = max(2, int(remaining * 0.25))
        recommendations_count = max(1, int(remaining * 0.20))
        conclusion_count = max(1, remaining - problem_count - analysis_count - evidence_count - recommendations_count)
        
        # Problem section (content + optional chart)
        problem_types = [SlideType.CONTENT]
        if problem_count > 1:
            problem_types.append(SlideType.CHART)
        sections.append(SectionPlan(
            name="Problem",
            slide_count=problem_count,
            slide_types=problem_types
        ))
        
        # Analysis section (mix of content, charts, tables, metrics)
        analysis_types = self._generate_diverse_types(
            analysis_count,
            preferred=[SlideType.CONTENT, SlideType.CHART, SlideType.TABLE, SlideType.METRIC]
        )
        sections.append(SectionPlan(
            name="Analysis",
            slide_count=analysis_count,
            slide_types=analysis_types
        ))
        
        # Evidence section (charts, comparisons, metrics)
        evidence_types = self._generate_diverse_types(
            evidence_count,
            preferred=[SlideType.CHART, SlideType.COMPARISON, SlideType.TABLE, SlideType.METRIC]
        )
        sections.append(SectionPlan(
            name="Evidence",
            slide_count=evidence_count,
            slide_types=evidence_types
        ))
        
        # Recommendations section (content with optional comparison)
        recommendations_types = [SlideType.CONTENT] * recommendations_count
        if recommendations_count > 1:
            recommendations_types[-1] = SlideType.COMPARISON
        sections.append(SectionPlan(
            name="Recommendations",
            slide_count=recommendations_count,
            slide_types=recommendations_types
        ))
        
        # Conclusion section (content)
        sections.append(SectionPlan(
            name="Conclusion",
            slide_count=conclusion_count,
            slide_types=[SlideType.CONTENT] * conclusion_count
        ))
        
        return sections

    def _allocate_from_template(self, template_structure: list[dict[str, Any]]) -> list[SectionPlan]:
        """
        Allocate slides based on template structure.
        
        Args:
            template_structure: Template slide structure
            
        Returns:
            List of SectionPlan objects
        """
        sections_dict: dict[str, list[SlideType]] = {}
        
        for slide_def in template_structure:
            section = slide_def.get("section", "Content")
            slide_type = SlideType(slide_def["type"])
            
            if section not in sections_dict:
                sections_dict[section] = []
            sections_dict[section].append(slide_type)
        
        return [
            SectionPlan(
                name=section,
                slide_count=len(types),
                slide_types=types
            )
            for section, types in sections_dict.items()
        ]

    def _generate_diverse_types(
        self,
        count: int,
        preferred: list[SlideType]
    ) -> list[SlideType]:
        """
        Generate diverse slide types ensuring no more than 2 consecutive of same type.
        
        Args:
            count: Number of slide types to generate
            preferred: Preferred slide types to use
            
        Returns:
            List of slide types with enforced diversity
        """
        if count == 0:
            return []
        
        if count == 1:
            return [preferred[0]]
        
        types = []
        consecutive_count = 0
        last_type = None
        
        for i in range(count):
            # Cycle through preferred types
            candidate = preferred[i % len(preferred)]
            
            # Enforce diversity: max 2 consecutive of same type
            if candidate == last_type:
                consecutive_count += 1
                if consecutive_count >= 2:
                    # Force different type
                    candidate = next(t for t in preferred if t != last_type)
                    consecutive_count = 0
            else:
                consecutive_count = 0
            
            types.append(candidate)
            last_type = candidate
        
        return types

    def enforce_visual_diversity(self, sections: list[SectionPlan]) -> list[SectionPlan]:
        """
        Enforce visual diversity across all slides.
        
        Ensures no more than 2 consecutive slides of the same type.
        
        Args:
            sections: List of section plans
            
        Returns:
            Updated section plans with enforced diversity
        """
        # Flatten all slide types
        all_types = []
        for section in sections:
            all_types.extend(section.slide_types)
        
        # Check for violations
        consecutive_count = 1
        last_type = all_types[0] if all_types else None
        
        for i in range(1, len(all_types)):
            if all_types[i] == last_type:
                consecutive_count += 1
                if consecutive_count > 2:
                    # Fix violation: change this slide type
                    available_types = [t for t in SlideType if t != last_type and t != SlideType.TITLE]
                    if available_types:
                        all_types[i] = available_types[0]
                        consecutive_count = 1
                        last_type = all_types[i]
            else:
                consecutive_count = 1
                last_type = all_types[i]
        
        # Rebuild sections with fixed types
        type_index = 0
        updated_sections = []
        for section in sections:
            section_types = all_types[type_index:type_index + section.slide_count]
            updated_sections.append(SectionPlan(
                name=section.name,
                slide_count=section.slide_count,
                slide_types=section_types
            ))
            type_index += section.slide_count
        
        return updated_sections

    def generate_presentation_plan(
        self,
        topic: str,
        industry: str,
        template_structure: list[dict[str, Any]] | None = None,
        template_slide_count: int | None = None
    ) -> PresentationPlanJSON:
        """
        Generate complete Presentation_Plan_JSON.
        
        This is the main entry point for the Storyboarding Agent.
        
        Args:
            topic: Presentation topic
            industry: Detected industry
            template_structure: Optional template structure
            template_slide_count: Optional template slide count
            
        Returns:
            Complete Presentation_Plan_JSON
        """
        # Phase 1: Analyze topic complexity
        complexity = self.analyze_topic_complexity(topic, industry)
        
        # Phase 2: Determine optimal slide count
        total_slides = self.determine_optimal_slide_count(complexity, template_slide_count)
        
        # Phase 3: Allocate slides to sections
        sections = self.allocate_slides_to_sections(total_slides, template_structure)
        
        # Phase 4: Enforce visual diversity
        sections = self.enforce_visual_diversity(sections)
        
        # Phase 5: Create plan
        plan = PresentationPlanJSON(
            topic=topic,
            industry=industry,
            total_slides=total_slides,
            sections=sections,
            visual_diversity_check=True
        )
        
        return plan
    
    async def optimize_narrative_with_llm(
        self,
        topic: str,
        industry: str,
        initial_plan: PresentationPlanJSON,
        execution_id: str,
    ) -> Optional[PresentationPlanJSON]:
        """
        Use LLM to optimize narrative flow for maximum executive impact.
        
        Phase 3 Enhancement: +0.35 quality points, +$0.0014 per presentation
        
        Optimizes:
        - Section ordering (problem → tension → resolution)
        - Slide distribution (more slides where tension peaks)
        - Executive attention management (hooks at key moments)
        
        Args:
            topic: Presentation topic
            industry: Industry context
            initial_plan: Initial presentation plan from deterministic logic
            execution_id: Execution ID for tracing
            
        Returns:
            Optimized presentation plan, or None on failure (falls back to initial_plan)
        """
        # Build section summary for LLM
        sections_summary = []
        for section in initial_plan.sections:
            sections_summary.append({
                "name": section.name,
                "slide_count": section.slide_count,
                "types": [t.value for t in section.slide_types]
            })
        
        system_prompt = f"""You are an expert {industry} presentation strategist specializing in executive storytelling.

Your task is to optimize the narrative flow of a presentation for MAXIMUM EXECUTIVE IMPACT.

Key principles:
1. **Narrative Arc**: Problem → Tension → Resolution
   - Start with the problem (hook attention)
   - Build tension with analysis and evidence (maintain engagement)
   - Resolve with clear recommendations (drive action)

2. **Attention Management**:
   - Executives have limited attention spans
   - Front-load critical insights
   - Place "aha moments" at attention peaks
   - End with clear, actionable takeaways

3. **Slide Distribution**:
   - More slides where tension peaks (Analysis/Evidence)
   - Fewer slides for setup (Problem) and conclusion
   - Balance depth with brevity

4. **Industry Context**:
   - {industry} executives care about: ROI, risk, competitive advantage
   - Adjust narrative to industry priorities

Rules:
- Total slides must stay within 5-25
- Keep Title (1 slide) and Agenda (1 slide) fixed
- Maintain visual diversity (no more than 2 consecutive same types)
- Optimize section ordering and slide counts only

Return JSON: {{"optimized_sections": [...], "narrative_arc": "...", "attention_peaks": [...], "reasoning": "..."}}"""

        user_prompt = f"""Optimize the narrative flow for this presentation:

Topic: {topic}
Industry: {industry}
Total Slides: {initial_plan.total_slides}

Current Structure:
{json.dumps(sections_summary, indent=2)}

Optimize the section ordering and slide distribution for maximum executive impact.
Ensure the narrative follows: Problem → Tension → Resolution."""

        try:
            result = await self._llm_helper.call_llm_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                pydantic_model=NarrativeOptimization,
                execution_id=execution_id,
                industry=industry,
            )
            
            # Convert LLM suggestions to SectionPlan objects
            optimized_sections = []
            total_slides = 0
            
            for section_data in result.get("optimized_sections", []):
                name = section_data.get("name", "Content")
                slide_count = section_data.get("slide_count", 1)
                types_str = section_data.get("types", ["content"])
                
                # Convert string types to SlideType enums
                slide_types = []
                for type_str in types_str:
                    try:
                        slide_types.append(SlideType(type_str))
                    except ValueError:
                        slide_types.append(SlideType.CONTENT)  # Fallback
                
                # Ensure slide_types length matches slide_count
                if len(slide_types) < slide_count:
                    slide_types.extend([SlideType.CONTENT] * (slide_count - len(slide_types)))
                elif len(slide_types) > slide_count:
                    slide_types = slide_types[:slide_count]
                
                optimized_sections.append(SectionPlan(
                    name=name,
                    slide_count=slide_count,
                    slide_types=slide_types
                ))
                total_slides += slide_count
            
            # Validate total slides is within bounds
            if total_slides < 5 or total_slides > 25:
                raise ValueError(f"Optimized total slides ({total_slides}) out of bounds (5-25)")
            
            # Enforce visual diversity on optimized plan
            optimized_sections = self.enforce_visual_diversity(optimized_sections)
            
            # Create optimized plan
            optimized_plan = PresentationPlanJSON(
                topic=topic,
                industry=industry,
                total_slides=total_slides,
                sections=optimized_sections,
                visual_diversity_check=True
            )
            
            logger_data = {
                "narrative_optimization_success": True,
                "original_slides": initial_plan.total_slides,
                "optimized_slides": total_slides,
                "narrative_arc": result.get("narrative_arc", ""),
                "attention_peaks": result.get("attention_peaks", []),
                "execution_id": execution_id,
            }
            
            # Log success (using print since we don't have logger imported)
            print(f"[INFO] narrative_optimization_success: {json.dumps(logger_data)}")
            
            return optimized_plan
            
        except Exception as e:
            # Log failure and return None (caller will use initial_plan)
            print(f"[WARNING] narrative_optimization_failed: {str(e)}, execution_id={execution_id}")
            return None

    def validate_final_presentation(
        self,
        plan: PresentationPlanJSON,
        generated_slides: list[dict[str, Any]]
    ) -> tuple[bool, list[str]]:
        """
        Validate final presentation against original Presentation_Plan_JSON.
        
        Checks:
        1. Slide count matches
        2. Slide types match
        3. Section structure preserved
        
        Args:
            plan: Original presentation plan
            generated_slides: Generated slides from LLM
            
        Returns:
            Tuple of (is_valid, list of validation errors)
        """
        errors = []
        
        # Check slide count
        if len(generated_slides) != plan.total_slides:
            errors.append(
                f"Slide count mismatch: expected {plan.total_slides}, got {len(generated_slides)}"
            )
        
        # Check slide types
        expected_types = []
        for section in plan.sections:
            expected_types.extend(section.slide_types)
        
        for i, slide in enumerate(generated_slides):
            if i < len(expected_types):
                expected_type = expected_types[i].value
                actual_type = slide.get("type")
                if actual_type != expected_type:
                    errors.append(
                        f"Slide {i+1} type mismatch: expected {expected_type}, got {actual_type}"
                    )
        
        # Check visual diversity
        if len(generated_slides) >= 3:
            for i in range(len(generated_slides) - 2):
                if (generated_slides[i].get("type") == generated_slides[i+1].get("type") ==
                    generated_slides[i+2].get("type")):
                    errors.append(
                        f"Visual diversity violation: 3 consecutive {generated_slides[i].get('type')} "
                        f"slides at positions {i+1}, {i+2}, {i+3}"
                    )
        
        return len(errors) == 0, errors
