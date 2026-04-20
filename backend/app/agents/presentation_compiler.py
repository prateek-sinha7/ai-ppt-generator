"""
Presentation Compiler - Coordinates all agents in sequential phases.

The compiler orchestrates the complete presentation generation pipeline:
Phase 0: Industry Classification (Industry_Classifier_Agent)
Phase 1: Analysis (Topic complexity analysis)
Phase 2: Planning (Storyboarding Agent)
Phase 3: Generation (LLM Provider Service)
Phase 4: Optimization (Design Intelligence Layer)
Phase 5: Validation (Validation Agent)
Phase 6: Quality Assessment (Quality Scoring Agent)

The compiler ensures proper sequencing, state management, and conflict resolution.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel

from .conflict_resolution import ConflictResolutionEngine
from .storyboarding import StoryboardingAgent, PresentationPlanJSON

logger = logging.getLogger(__name__)


class CompilationPhase(str, Enum):
    """Compilation phases in order."""
    INDUSTRY_CLASSIFICATION = "industry_classification"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    GENERATION = "generation"
    OPTIMIZATION = "optimization"
    VALIDATION = "validation"
    QUALITY_ASSESSMENT = "quality_assessment"


class PhaseStatus(str, Enum):
    """Status of a compilation phase."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PhaseResult(BaseModel):
    """Result of a compilation phase."""
    phase: CompilationPhase
    status: PhaseStatus
    output: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: float | None = None
    started_at: str | None = None
    completed_at: str | None = None


class CompilationReport(BaseModel):
    """Complete compilation report."""
    compilation_id: str
    topic: str
    industry: str | None = None
    total_duration_ms: float
    phases: list[PhaseResult]
    final_output: dict[str, Any] | None = None
    conflicts_detected: int = 0
    conflict_summary: dict[str, Any] | None = None
    started_at: str
    completed_at: str


class PresentationCompiler:
    """
    Presentation Compiler - Orchestrates multi-agent pipeline.
    
    The compiler coordinates all agents in sequential phases, ensuring:
    1. Proper phase ordering and dependencies
    2. State management between phases
    3. Conflict resolution (Storyboarding authority)
    4. Error handling and recovery
    5. Performance tracking and reporting
    
    Key responsibilities:
    - Execute phases in correct order
    - Pass context between phases
    - Enforce Storyboarding Agent authority
    - Generate compilation reports
    - Handle phase failures gracefully
    """

    def __init__(self):
        """Initialize the Presentation Compiler."""
        self.storyboarding_agent = StoryboardingAgent()
        self.conflict_engine = ConflictResolutionEngine()
        self.current_phase: CompilationPhase | None = None
        self.phase_results: list[PhaseResult] = []

    async def compile(
        self,
        topic: str,
        compilation_id: str,
        detected_context: dict[str, Any] | None = None,
        industry_classifier_fn: Callable | None = None,
        llm_generator_fn: Callable | None = None,
        validator_fn: Callable | None = None,
        quality_scorer_fn: Callable | None = None,
    ) -> CompilationReport:
        """
        Compile a complete presentation through all phases.
        
        This is the main entry point for presentation generation.
        
        Args:
            topic: Presentation topic
            compilation_id: Unique compilation identifier
            detected_context: Optional pre-detected industry context
            industry_classifier_fn: Optional industry classifier function
            llm_generator_fn: Optional LLM generator function
            validator_fn: Optional validator function
            quality_scorer_fn: Optional quality scorer function
            
        Returns:
            Complete CompilationReport
        """
        start_time = datetime.utcnow()
        self.phase_results = []
        
        try:
            # Phase 0: Industry Classification
            if detected_context is None and industry_classifier_fn:
                detected_context = await self._run_phase(
                    CompilationPhase.INDUSTRY_CLASSIFICATION,
                    industry_classifier_fn,
                    {"topic": topic}
                )
            
            industry = detected_context.get("industry", "general") if detected_context else "general"
            
            # Phase 1: Analysis (Topic complexity)
            analysis_result = await self._run_phase(
                CompilationPhase.ANALYSIS,
                self._analyze_topic,
                {"topic": topic, "industry": industry}
            )
            
            # Phase 2: Planning (Storyboarding)
            planning_result = await self._run_phase(
                CompilationPhase.PLANNING,
                self._plan_presentation,
                {
                    "topic": topic,
                    "industry": industry,
                    "complexity": analysis_result.get("complexity"),
                    "detected_context": detected_context
                }
            )
            
            presentation_plan = planning_result.get("presentation_plan")
            
            # Phase 3: Generation (LLM)
            if llm_generator_fn:
                generation_result = await self._run_phase(
                    CompilationPhase.GENERATION,
                    llm_generator_fn,
                    {
                        "topic": topic,
                        "industry": industry,
                        "presentation_plan": presentation_plan,
                        "detected_context": detected_context
                    }
                )
            else:
                generation_result = {"slides": []}
            
            # Phase 4: Optimization (Design Intelligence)
            optimization_result = await self._run_phase(
                CompilationPhase.OPTIMIZATION,
                self._optimize_presentation,
                {
                    "slides": generation_result.get("slides", []),
                    "presentation_plan": presentation_plan
                }
            )
            
            # Phase 5: Validation (with Conflict Resolution)
            if validator_fn:
                validation_result = await self._run_phase(
                    CompilationPhase.VALIDATION,
                    validator_fn,
                    {
                        "slides": optimization_result.get("slides", []),
                        "presentation_plan": presentation_plan
                    }
                )
            else:
                validation_result = optimization_result
            
            # Apply conflict resolution
            corrected_output, conflicts = self.conflict_engine.validate_and_resolve(
                presentation_plan,
                validation_result
            )
            
            # Phase 6: Quality Assessment
            if quality_scorer_fn:
                quality_result = await self._run_phase(
                    CompilationPhase.QUALITY_ASSESSMENT,
                    quality_scorer_fn,
                    {"presentation": corrected_output}
                )
            else:
                quality_result = {"quality_score": 8.0}
            
            # Build final output
            final_output = {
                **corrected_output,
                "quality_score": quality_result.get("quality_score"),
                "presentation_plan": presentation_plan,
                "detected_context": detected_context
            }
            
            # Generate report
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return CompilationReport(
                compilation_id=compilation_id,
                topic=topic,
                industry=industry,
                total_duration_ms=duration_ms,
                phases=self.phase_results,
                final_output=final_output,
                conflicts_detected=len(conflicts),
                conflict_summary=self.conflict_engine.get_conflict_summary(),
                started_at=start_time.isoformat(),
                completed_at=end_time.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Compilation failed: {str(e)}", exc_info=True)
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            return CompilationReport(
                compilation_id=compilation_id,
                topic=topic,
                industry=detected_context.get("industry") if detected_context else None,
                total_duration_ms=duration_ms,
                phases=self.phase_results,
                final_output=None,
                started_at=start_time.isoformat(),
                completed_at=end_time.isoformat()
            )

    async def _run_phase(
        self,
        phase: CompilationPhase,
        phase_fn: Callable,
        inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Run a single compilation phase.
        
        Args:
            phase: Phase to run
            phase_fn: Function to execute for this phase
            inputs: Input data for the phase
            
        Returns:
            Phase output data
        """
        self.current_phase = phase
        start_time = datetime.utcnow()
        
        logger.info(f"Starting phase: {phase.value}")
        
        try:
            # Execute phase
            if hasattr(phase_fn, '__call__'):
                if hasattr(phase_fn, '__self__'):
                    # Bound method
                    output = phase_fn(**inputs)
                else:
                    # Async function
                    import inspect
                    if inspect.iscoroutinefunction(phase_fn):
                        output = await phase_fn(**inputs)
                    else:
                        output = phase_fn(**inputs)
            else:
                output = {}
            
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            # Record result
            result = PhaseResult(
                phase=phase,
                status=PhaseStatus.COMPLETED,
                output=output,
                duration_ms=duration_ms,
                started_at=start_time.isoformat(),
                completed_at=end_time.isoformat()
            )
            self.phase_results.append(result)
            
            logger.info(f"Completed phase: {phase.value} in {duration_ms:.2f}ms")
            
            return output
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            # Record failure
            result = PhaseResult(
                phase=phase,
                status=PhaseStatus.FAILED,
                error=str(e),
                duration_ms=duration_ms,
                started_at=start_time.isoformat(),
                completed_at=end_time.isoformat()
            )
            self.phase_results.append(result)
            
            logger.error(f"Phase {phase.value} failed: {str(e)}", exc_info=True)
            raise

    def _analyze_topic(self, topic: str, industry: str) -> dict[str, Any]:
        """
        Phase 1: Analyze topic complexity.
        
        Args:
            topic: Presentation topic
            industry: Detected industry
            
        Returns:
            Analysis results including complexity
        """
        complexity = self.storyboarding_agent.analyze_topic_complexity(topic, industry)
        
        return {
            "complexity": complexity.value,
            "word_count": len(topic.split()),
            "industry": industry
        }

    def _plan_presentation(
        self,
        topic: str,
        industry: str,
        complexity: str,
        detected_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Phase 2: Plan presentation structure (Storyboarding).
        
        Args:
            topic: Presentation topic
            industry: Detected industry
            complexity: Topic complexity
            detected_context: Detected context with template info
            
        Returns:
            Planning results including Presentation_Plan_JSON
        """
        # Extract template info if available
        template_structure = None
        template_slide_count = None
        
        if detected_context:
            template_structure = detected_context.get("template_structure")
            template_slide_count = detected_context.get("template_slide_count")
        
        # Generate presentation plan
        plan = self.storyboarding_agent.generate_presentation_plan(
            topic=topic,
            industry=industry,
            template_structure=template_structure,
            template_slide_count=template_slide_count
        )
        
        return {
            "presentation_plan": plan.model_dump(),
            "total_slides": plan.total_slides,
            "sections": [s.model_dump() for s in plan.sections]
        }

    def _optimize_presentation(
        self,
        slides: list[dict[str, Any]],
        presentation_plan: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Phase 4: Optimize presentation (Design Intelligence).
        
        Performs:
        - Content density checks
        - Slide splitting if needed
        - Visual diversity rebalancing
        
        Args:
            slides: Generated slides
            presentation_plan: Original presentation plan
            
        Returns:
            Optimized slides
        """
        optimized_slides = []
        
        for slide in slides:
            # Check content density
            density = self._calculate_content_density(slide)
            
            if density > 0.75:
                # Split overcrowded slide
                split_slides = self._split_slide(slide)
                optimized_slides.extend(split_slides)
            else:
                optimized_slides.append(slide)
        
        # Ensure visual diversity
        optimized_slides = self._rebalance_visual_diversity(optimized_slides)
        
        return {
            "slides": optimized_slides,
            "optimization_applied": True
        }

    def _calculate_content_density(self, slide: dict[str, Any]) -> float:
        """
        Calculate content density for a slide.
        
        Args:
            slide: Slide data
            
        Returns:
            Density ratio (0.0 - 1.0)
        """
        content = slide.get("content", {})
        
        # Count content elements
        bullets = content.get("bullets", [])
        has_chart = content.get("chart_data") is not None
        has_table = content.get("table_data") is not None
        
        # Simple density calculation
        density = 0.0
        density += len(bullets) * 0.15  # Each bullet adds 15%
        if has_chart:
            density += 0.4
        if has_table:
            density += 0.4
        
        return min(density, 1.0)

    def _split_slide(self, slide: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Split an overcrowded slide into multiple slides.
        
        Args:
            slide: Slide to split
            
        Returns:
            List of split slides
        """
        content = slide.get("content", {})
        bullets = content.get("bullets", [])
        
        if len(bullets) <= 4:
            return [slide]
        
        # Split bullets
        mid = len(bullets) // 2
        
        slide_a = slide.copy()
        slide_a["content"] = {**content, "bullets": bullets[:mid]}
        
        slide_b = slide.copy()
        slide_b["title"] = f"{slide['title']} (cont.)"
        slide_b["content"] = {**content, "bullets": bullets[mid:]}
        
        return [slide_a, slide_b]

    def _rebalance_visual_diversity(
        self,
        slides: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Rebalance visual diversity if needed.
        
        Ensures no more than 2 consecutive slides of same type.
        
        Args:
            slides: Slides to rebalance
            
        Returns:
            Rebalanced slides
        """
        if len(slides) < 3:
            return slides
        
        # Check for violations
        for i in range(len(slides) - 2):
            if (slides[i].get("type") == slides[i+1].get("type") ==
                slides[i+2].get("type")):
                # Violation detected - change third slide type
                current_type = slides[i].get("type")
                
                # Choose different type
                alternative_types = ["content", "chart", "table", "comparison"]
                alternative_types = [t for t in alternative_types if t != current_type]
                
                if alternative_types:
                    slides[i+2]["type"] = alternative_types[0]
                    # Update visual hint accordingly
                    type_to_hint = {
                        "content": "bullet-left",
                        "chart": "split-chart-right",
                        "table": "split-table-left",
                        "comparison": "two-column"
                    }
                    slides[i+2]["visual_hint"] = type_to_hint.get(
                        alternative_types[0],
                        "bullet-left"
                    )
        
        return slides

    def get_phase_status(self, phase: CompilationPhase) -> PhaseResult | None:
        """
        Get status of a specific phase.
        
        Args:
            phase: Phase to check
            
        Returns:
            PhaseResult if phase has been executed, None otherwise
        """
        for result in self.phase_results:
            if result.phase == phase:
                return result
        return None

    def get_current_phase(self) -> CompilationPhase | None:
        """Get currently executing phase."""
        return self.current_phase
