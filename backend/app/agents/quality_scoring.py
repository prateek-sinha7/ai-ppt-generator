"""
Quality Scoring Agent - Multi-dimensional quality assessment with measurable metrics.

This agent evaluates presentations across five dimensions:
- Content Depth (25%)
- Visual Appeal (20%)
- Structure Coherence (25%)
- Data Accuracy (15%)
- Clarity (15%)

The agent implements comprehensive quality scoring logic with:
- Composite Quality_Score calculation as weighted average
- Whitespace ratio and content density scoring
- Narrative coherence validation against consulting storytelling structure
- Improvement recommendations per dimension
- LLM-powered specific, actionable recommendations (Phase 4)
- Feedback_Loop trigger when score < 8
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

from app.agents.llm_helpers import LLMEnhancementHelper

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants and Configuration
# ---------------------------------------------------------------------------

# Dimension weights (must sum to 1.0)
WEIGHT_CONTENT_DEPTH = 0.25
WEIGHT_VISUAL_APPEAL = 0.20
WEIGHT_STRUCTURE_COHERENCE = 0.25
WEIGHT_DATA_ACCURACY = 0.15
WEIGHT_CLARITY = 0.15

# Quality thresholds
QUALITY_THRESHOLD_FEEDBACK_LOOP = 8.0
MAX_FEEDBACK_RETRIES = 2

# Content constraints
MAX_CONTENT_DENSITY = 0.75
MIN_WHITESPACE_RATIO = 0.25
MAX_TITLE_WORDS = 8
MAX_BULLETS = 4
MAX_WORDS_PER_BULLET = 8

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


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ScoreDimension(str, Enum):
    """Quality scoring dimensions."""
    CONTENT_DEPTH = "content_depth"
    VISUAL_APPEAL = "visual_appeal"
    STRUCTURE_COHERENCE = "structure_coherence"
    DATA_ACCURACY = "data_accuracy"
    CLARITY = "clarity"


class SlideType(str, Enum):
    """Allowed slide types."""
    TITLE = "title"
    CONTENT = "content"
    CHART = "chart"
    TABLE = "table"
    COMPARISON = "comparison"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    """Score for a single dimension."""
    dimension: ScoreDimension
    score: float  # 1-10
    weight: float
    weighted_score: float
    recommendations: List[str]
    details: Dict[str, Any]


class QualityScoreResult(BaseModel):
    """Complete quality scoring result."""
    score_id: str = Field(default_factory=lambda: str(uuid4()))
    presentation_id: str
    execution_id: Optional[str] = None
    
    # Dimension scores
    content_depth: float = Field(ge=1.0, le=10.0)
    visual_appeal: float = Field(ge=1.0, le=10.0)
    structure_coherence: float = Field(ge=1.0, le=10.0)
    data_accuracy: float = Field(ge=1.0, le=10.0)
    clarity: float = Field(ge=1.0, le=10.0)
    
    # Composite score
    composite_score: float = Field(ge=1.0, le=10.0)
    
    # Recommendations per dimension
    recommendations: Dict[str, List[str]]
    
    # Metadata
    requires_feedback_loop: bool
    scoring_details: Dict[str, Any]
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "score_id": self.score_id,
            "presentation_id": self.presentation_id,
            "execution_id": self.execution_id,
            "content_depth": self.content_depth,
            "visual_appeal": self.visual_appeal,
            "structure_coherence": self.structure_coherence,
            "data_accuracy": self.data_accuracy,
            "clarity": self.clarity,
            "composite_score": self.composite_score,
            "recommendations": self.recommendations,
            "requires_feedback_loop": self.requires_feedback_loop,
            "scoring_details": self.scoring_details,
            "created_at": self.created_at
        }


# ---------------------------------------------------------------------------
# LLM Output Models for Phase 4
# ---------------------------------------------------------------------------

class LLMRecommendations(BaseModel):
    """LLM-generated specific, actionable recommendations."""
    content_improvements: List[str] = Field(
        default_factory=list,
        description="Slide-specific content improvements with slide numbers"
    )
    visual_improvements: List[str] = Field(
        default_factory=list,
        description="Visual enhancements with specific icon/chart suggestions"
    )
    data_improvements: List[str] = Field(
        default_factory=list,
        description="Data quality improvements with specific examples"
    )
    priority_fixes: List[str] = Field(
        default_factory=list,
        description="Top 3-5 priority fixes ranked by impact"
    )


# ---------------------------------------------------------------------------
# Quality Scoring Agent
# ---------------------------------------------------------------------------

class QualityScoringAgent(LLMEnhancementHelper):
    """
    Quality Scoring Agent - Multi-dimensional quality assessment.
    
    Key responsibilities:
    1. Score content depth (25% weight)
    2. Score visual appeal (20% weight)
    3. Score structure coherence (25% weight)
    4. Score data accuracy (15% weight)
    5. Score clarity (15% weight)
    6. Calculate composite weighted average
    7. Generate improvement recommendations
    8. Generate LLM-powered specific recommendations (Phase 4)
    9. Trigger feedback loop if score < 8
    """
    
    def __init__(self):
        """Initialize the Quality Scoring Agent."""
        super().__init__()
        self.dimension_weights = {
            ScoreDimension.CONTENT_DEPTH: WEIGHT_CONTENT_DEPTH,
            ScoreDimension.VISUAL_APPEAL: WEIGHT_VISUAL_APPEAL,
            ScoreDimension.STRUCTURE_COHERENCE: WEIGHT_STRUCTURE_COHERENCE,
            ScoreDimension.DATA_ACCURACY: WEIGHT_DATA_ACCURACY,
            ScoreDimension.CLARITY: WEIGHT_CLARITY,
        }

    @staticmethod
    def _get_slide_type(slide: Dict[str, Any]) -> str:
        """
        Resolve the correct slide type.
        The LLM returns slide_type (e.g. 'chart') but the validation agent
        may have stored type='content'. Always prefer slide_type when present.
        Falls back to visual_hint inference.
        """
        _type_map = {
            "title": "title", "title_slide": "title",
            "content": "content", "content_slide": "content",
            "chart": "chart", "chart_slide": "chart",
            "table": "table", "table_slide": "table",
            "comparison": "comparison", "comparison_slide": "comparison",
        }
        _hint_map = {
            "centered": "title",
            "split-chart-right": "chart",
            "split-table-left": "table",
            "two-column": "comparison",
            "bullet-left": "content",
            "highlight-metric": "content",
        }
        # Prefer slide_type (LLM output) over type (may be wrong)
        raw = slide.get("slide_type") or slide.get("type") or ""
        resolved = _type_map.get(str(raw).lower(), "")
        if not resolved or resolved == "content":
            # Try visual_hint as tiebreaker
            hint_resolved = _hint_map.get(slide.get("visual_hint", ""), "")
            if hint_resolved and hint_resolved != "content":
                return hint_resolved
        return resolved or "content"
    
    def score_content_depth(self, slides: List[Dict[str, Any]]) -> DimensionScore:
        """
        Score content depth dimension (25% weight).
        
        Evaluates:
        - Presence of substantive content (not just titles)
        - Depth of bullet points and explanations
        - Use of supporting data and evidence
        - Coverage of topic aspects
        
        Args:
            slides: List of slide dictionaries
            
        Returns:
            DimensionScore for content depth
        """
        score = 10.0
        recommendations = []
        details = {}
        
        # Count content-bearing slides
        content_slides = [s for s in slides if self._get_slide_type(s) in ["content", "chart", "table", "comparison"]]
        content_ratio = len(content_slides) / len(slides) if slides else 0
        details["content_slides"] = len(content_slides)
        details["content_ratio"] = content_ratio
        
        # Penalize if too few content slides
        if content_ratio < 0.6:
            score -= 2.0
            recommendations.append("Increase substantive content slides (currently {:.0%})".format(content_ratio))
        
        # Evaluate bullet depth
        total_bullets = 0
        empty_content_slides = 0
        
        for slide in content_slides:
            content = slide.get("content", {})
            bullets = content.get("bullets", [])
            total_bullets += len(bullets)
            
            if not bullets and not content.get("chart_data") and not content.get("table_data"):
                empty_content_slides += 1
        
        avg_bullets = total_bullets / len(content_slides) if content_slides else 0
        details["avg_bullets_per_slide"] = avg_bullets
        details["empty_content_slides"] = empty_content_slides
        
        # Penalize empty content slides
        if empty_content_slides > 0:
            score -= min(3.0, empty_content_slides * 0.5)
            recommendations.append(f"Add content to {empty_content_slides} empty slides")
        
        # Penalize if average bullets too low
        if avg_bullets < 2.0:
            score -= 1.5
            recommendations.append("Increase content depth with more bullet points")
        
        # Check for data-backed evidence
        data_slides = [s for s in slides if self._get_slide_type(s) in ["chart", "table"]]
        data_ratio = len(data_slides) / len(slides) if slides else 0
        details["data_slides"] = len(data_slides)
        details["data_ratio"] = data_ratio
        
        if data_ratio < 0.15:
            score -= 1.0
            recommendations.append("Add more data-backed evidence (charts/tables)")
        
        # Ensure score stays in bounds
        score = max(1.0, min(10.0, score))
        
        return DimensionScore(
            dimension=ScoreDimension.CONTENT_DEPTH,
            score=score,
            weight=WEIGHT_CONTENT_DEPTH,
            weighted_score=score * WEIGHT_CONTENT_DEPTH,
            recommendations=recommendations,
            details=details
        )
    
    def score_visual_appeal(self, slides: List[Dict[str, Any]]) -> DimensionScore:
        """
        Score visual appeal dimension (20% weight).
        
        Evaluates:
        - Visual diversity (mix of slide types)
        - Whitespace ratio and content density
        - Use of visual elements (icons, highlights)
        - Layout variety
        
        Args:
            slides: List of slide dictionaries
            
        Returns:
            DimensionScore for visual appeal
        """
        score = 10.0
        recommendations = []
        details = {}
        
        # Check visual diversity
        slide_types = [self._get_slide_type(s) for s in slides]
        unique_types = set(slide_types)
        type_diversity = len(unique_types) / 5.0  # 5 possible types
        details["unique_slide_types"] = len(unique_types)
        details["type_diversity"] = type_diversity
        
        if type_diversity < 0.4:
            score -= 2.0
            recommendations.append("Increase visual diversity with more slide type variety")
        
        # Check for consecutive same-type slides (max 2)
        max_consecutive = 1
        current_consecutive = 1
        for i in range(1, len(slide_types)):
            if slide_types[i] == slide_types[i-1]:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        
        details["max_consecutive_same_type"] = max_consecutive
        if max_consecutive > 2:
            score -= 1.5
            recommendations.append(f"Reduce consecutive same-type slides (found {max_consecutive} in a row)")
        
        # Check whitespace and density
        density_violations = 0
        whitespace_violations = 0
        
        for slide in slides:
            layout_constraints = slide.get("layout_constraints", {})
            max_density = layout_constraints.get("max_content_density", MAX_CONTENT_DENSITY)
            min_whitespace = layout_constraints.get("min_whitespace_ratio", MIN_WHITESPACE_RATIO)
            
            # Estimate content density from bullet count
            content = slide.get("content", {})
            bullets = content.get("bullets", [])
            estimated_density = min(1.0, len(bullets) / MAX_BULLETS)
            
            if estimated_density > max_density:
                density_violations += 1
            if (1.0 - estimated_density) < min_whitespace:
                whitespace_violations += 1
        
        details["density_violations"] = density_violations
        details["whitespace_violations"] = whitespace_violations
        
        if density_violations > 0:
            score -= min(2.0, density_violations * 0.5)
            recommendations.append(f"Reduce content density on {density_violations} slides")
        
        if whitespace_violations > 0:
            score -= min(1.5, whitespace_violations * 0.3)
            recommendations.append(f"Increase whitespace on {whitespace_violations} slides")
        
        # Check for visual elements
        slides_with_icons = sum(1 for s in slides if s.get("content", {}).get("icon_name"))
        slides_with_highlights = sum(1 for s in slides if s.get("content", {}).get("highlight_text"))
        visual_element_ratio = (slides_with_icons + slides_with_highlights) / len(slides) if slides else 0
        
        details["slides_with_icons"] = slides_with_icons
        details["slides_with_highlights"] = slides_with_highlights
        details["visual_element_ratio"] = visual_element_ratio
        
        if visual_element_ratio < 0.2:
            score -= 1.0
            recommendations.append("Add more visual elements (icons, highlights) for engagement")
        
        # Ensure score stays in bounds
        score = max(1.0, min(10.0, score))
        
        return DimensionScore(
            dimension=ScoreDimension.VISUAL_APPEAL,
            score=score,
            weight=WEIGHT_VISUAL_APPEAL,
            weighted_score=score * WEIGHT_VISUAL_APPEAL,
            recommendations=recommendations,
            details=details
        )
    
    def score_structure_coherence(self, slides: List[Dict[str, Any]]) -> DimensionScore:
        """
        Score structure coherence dimension (25% weight).
        
        Evaluates:
        - Narrative coherence against consulting storytelling structure
        - Logical flow between slides
        - Section organization
        - Presence of required sections
        
        Args:
            slides: List of slide dictionaries
            
        Returns:
            DimensionScore for structure coherence
        """
        score = 10.0
        recommendations = []
        details = {}
        
        # Extract slide titles for section detection
        titles = [s.get("title", "").lower() for s in slides]
        
        # Check for required sections
        found_sections = []
        missing_sections = []
        
        for required_section in REQUIRED_SECTIONS:
            section_found = any(required_section.lower() in title for title in titles)
            if section_found:
                found_sections.append(required_section)
            else:
                missing_sections.append(required_section)
        
        details["found_sections"] = found_sections
        details["missing_sections"] = missing_sections
        section_coverage = len(found_sections) / len(REQUIRED_SECTIONS)
        details["section_coverage"] = section_coverage
        
        # Penalize missing sections
        if section_coverage < 1.0:
            penalty = (1.0 - section_coverage) * 4.0
            score -= penalty
            recommendations.append(
                f"Add missing sections: {', '.join(missing_sections)}"
            )
        
        # Check section order (should follow consulting structure)
        section_order_score = 10.0
        expected_order = REQUIRED_SECTIONS
        found_order = []
        
        for title in titles:
            for section in expected_order:
                if section.lower() in title and section not in found_order:
                    found_order.append(section)
                    break
        
        # Calculate order correctness
        order_violations = 0
        for i in range(len(found_order) - 1):
            expected_idx = expected_order.index(found_order[i])
            next_idx = expected_order.index(found_order[i+1])
            if next_idx < expected_idx:
                order_violations += 1
        
        details["found_order"] = found_order
        details["order_violations"] = order_violations
        
        if order_violations > 0:
            score -= min(2.0, order_violations * 0.5)
            recommendations.append(
                f"Reorder sections to follow consulting structure: {' → '.join(expected_order)}"
            )
        
        # Check for logical flow (title slide first, conclusion last)
        if slides:
            first_slide_type = self._get_slide_type(slides[0])
            last_slide_type = self._get_slide_type(slides[-1])
            
            if first_slide_type != "title":
                score -= 1.0
                recommendations.append("First slide should be a title slide")
            
            if "conclusion" not in slides[-1].get("title", "").lower():
                score -= 0.5
                recommendations.append("Last slide should be a conclusion")
        
        # Ensure score stays in bounds
        score = max(1.0, min(10.0, score))
        
        return DimensionScore(
            dimension=ScoreDimension.STRUCTURE_COHERENCE,
            score=score,
            weight=WEIGHT_STRUCTURE_COHERENCE,
            weighted_score=score * WEIGHT_STRUCTURE_COHERENCE,
            recommendations=recommendations,
            details=details
        )
    
    def score_data_accuracy(self, slides: List[Dict[str, Any]]) -> DimensionScore:
        """
        Score data accuracy dimension (15% weight).
        
        Evaluates:
        - Presence of data in chart/table slides
        - Data structure validity
        - Consistency of data across slides
        - Appropriate use of data visualizations
        
        Args:
            slides: List of slide dictionaries
            
        Returns:
            DimensionScore for data accuracy
        """
        score = 10.0
        recommendations = []
        details = {}
        
        # Check chart slides have chart_data
        chart_slides = [s for s in slides if self._get_slide_type(s) == "chart"]
        charts_with_data = sum(
            1 for s in chart_slides 
            if s.get("content", {}).get("chart_data")
        )
        
        details["chart_slides"] = len(chart_slides)
        details["charts_with_data"] = charts_with_data
        
        if chart_slides and charts_with_data < len(chart_slides):
            missing = len(chart_slides) - charts_with_data
            score -= min(3.0, missing * 1.0)
            recommendations.append(f"Add chart data to {missing} chart slides")
        
        # Check table slides have table_data
        table_slides = [s for s in slides if self._get_slide_type(s) == "table"]
        tables_with_data = sum(
            1 for s in table_slides 
            if s.get("content", {}).get("table_data")
        )
        
        details["table_slides"] = len(table_slides)
        details["tables_with_data"] = tables_with_data
        
        if table_slides and tables_with_data < len(table_slides):
            missing = len(table_slides) - tables_with_data
            score -= min(3.0, missing * 1.0)
            recommendations.append(f"Add table data to {missing} table slides")
        
        # Check comparison slides have comparison_data
        comparison_slides = [s for s in slides if self._get_slide_type(s) == "comparison"]
        comparisons_with_data = sum(
            1 for s in comparison_slides 
            if s.get("content", {}).get("comparison_data")
        )
        
        details["comparison_slides"] = len(comparison_slides)
        details["comparisons_with_data"] = comparisons_with_data
        
        if comparison_slides and comparisons_with_data < len(comparison_slides):
            missing = len(comparison_slides) - comparisons_with_data
            score -= min(2.0, missing * 0.5)
            recommendations.append(f"Add comparison data to {missing} comparison slides")
        
        # Check for appropriate chart types
        for slide in chart_slides:
            content = slide.get("content", {})
            chart_data = content.get("chart_data")
            chart_type = content.get("chart_type")  # chart_type is a sibling of chart_data, not inside it
            
            if not chart_type:
                score -= 0.5
                recommendations.append("Specify chart_type for all chart slides")
                break
        
        # Ensure score stays in bounds
        score = max(1.0, min(10.0, score))
        
        return DimensionScore(
            dimension=ScoreDimension.DATA_ACCURACY,
            score=score,
            weight=WEIGHT_DATA_ACCURACY,
            weighted_score=score * WEIGHT_DATA_ACCURACY,
            recommendations=recommendations,
            details=details
        )
    
    def score_clarity(self, slides: List[Dict[str, Any]]) -> DimensionScore:
        """
        Score clarity dimension (15% weight).
        
        Evaluates:
        - Title clarity and conciseness (max 8 words)
        - Bullet point clarity (max 8 words each)
        - Appropriate bullet count (max 4 per slide)
        - Clear and actionable language
        
        Args:
            slides: List of slide dictionaries
            
        Returns:
            DimensionScore for clarity
        """
        score = 10.0
        recommendations = []
        details = {}
        
        # Check title word counts
        long_titles = 0
        total_title_words = 0
        
        for slide in slides:
            title = slide.get("title", "")
            word_count = len(title.split())
            total_title_words += word_count
            
            if word_count > MAX_TITLE_WORDS:
                long_titles += 1
        
        avg_title_words = total_title_words / len(slides) if slides else 0
        details["long_titles"] = long_titles
        details["avg_title_words"] = avg_title_words
        
        if long_titles > 0:
            score -= min(2.0, long_titles * 0.3)
            recommendations.append(f"Shorten {long_titles} titles to max {MAX_TITLE_WORDS} words")
        
        # Check bullet counts and word counts
        slides_with_too_many_bullets = 0
        long_bullets = 0
        total_bullets = 0
        
        for slide in slides:
            bullets = slide.get("content", {}).get("bullets", [])
            total_bullets += len(bullets)
            
            if len(bullets) > MAX_BULLETS:
                slides_with_too_many_bullets += 1
            
            for bullet in bullets:
                word_count = len(bullet.split())
                if word_count > MAX_WORDS_PER_BULLET:
                    long_bullets += 1
        
        details["slides_with_too_many_bullets"] = slides_with_too_many_bullets
        details["long_bullets"] = long_bullets
        details["total_bullets"] = total_bullets
        
        if slides_with_too_many_bullets > 0:
            score -= min(2.0, slides_with_too_many_bullets * 0.5)
            recommendations.append(
                f"Reduce bullet count on {slides_with_too_many_bullets} slides to max {MAX_BULLETS}"
            )
        
        if long_bullets > 0:
            score -= min(2.0, long_bullets * 0.2)
            recommendations.append(
                f"Shorten {long_bullets} bullets to max {MAX_WORDS_PER_BULLET} words"
            )
        
        # Check for clear language (avoid jargon overload)
        jargon_indicators = ["synergy", "leverage", "paradigm", "utilize", "facilitate"]
        jargon_count = 0
        
        for slide in slides:
            title = slide.get("title", "").lower()
            bullets = slide.get("content", {}).get("bullets", [])
            
            for indicator in jargon_indicators:
                if indicator in title:
                    jargon_count += 1
                for bullet in bullets:
                    if indicator in bullet.lower():
                        jargon_count += 1
        
        details["jargon_count"] = jargon_count
        
        if jargon_count > 5:
            score -= 1.0
            recommendations.append("Reduce jargon and use clearer language")
        
        # Ensure score stays in bounds
        score = max(1.0, min(10.0, score))
        
        return DimensionScore(
            dimension=ScoreDimension.CLARITY,
            score=score,
            weight=WEIGHT_CLARITY,
            weighted_score=score * WEIGHT_CLARITY,
            recommendations=recommendations,
            details=details
        )
    
    def calculate_composite_score(self, dimension_scores: List[DimensionScore]) -> float:
        """
        Calculate composite quality score as weighted average.
        
        Formula: Σ(dimension_score * weight)
        
        Args:
            dimension_scores: List of dimension scores
            
        Returns:
            Composite score (1-10)
        """
        composite = sum(ds.weighted_score for ds in dimension_scores)
        
        # Ensure score stays in bounds
        composite = max(1.0, min(10.0, composite))
        
        logger.info(
            "composite_score_calculated",
            composite_score=composite,
            dimension_scores={
                ds.dimension.value: ds.score 
                for ds in dimension_scores
            }
        )
        
        return composite
    
    def generate_recommendations(
        self,
        dimension_scores: List[DimensionScore]
    ) -> Dict[str, List[str]]:
        """
        Generate improvement recommendations per dimension.
        
        Args:
            dimension_scores: List of dimension scores
            
        Returns:
            Dictionary mapping dimension to recommendations
        """
        recommendations = {}
        
        for ds in dimension_scores:
            if ds.recommendations:
                recommendations[ds.dimension.value] = ds.recommendations
        
        return recommendations
    
    def should_trigger_feedback_loop(
        self,
        composite_score: float,
        retry_count: int = 0
    ) -> bool:
        """
        Determine if feedback loop should be triggered.
        
        Triggers when:
        - Composite score < 8.0
        - Retry count < MAX_FEEDBACK_RETRIES
        
        Args:
            composite_score: Composite quality score
            retry_count: Current retry count
            
        Returns:
            True if feedback loop should be triggered
        """
        should_trigger = (
            composite_score < QUALITY_THRESHOLD_FEEDBACK_LOOP and
            retry_count < MAX_FEEDBACK_RETRIES
        )
        
        if should_trigger:
            logger.info(
                "feedback_loop_triggered",
                composite_score=composite_score,
                threshold=QUALITY_THRESHOLD_FEEDBACK_LOOP,
                retry_count=retry_count,
                max_retries=MAX_FEEDBACK_RETRIES
            )
        
        return should_trigger
    
    async def generate_llm_recommendations(
        self,
        slides: List[Dict[str, Any]],
        dimension_scores: List[DimensionScore],
        execution_id: str,
    ) -> Dict[str, List[str]]:
        """
        Use LLM to generate SPECIFIC, ACTIONABLE recommendations.
        
        Phase 4 Enhancement: Goes beyond formula-based scoring to provide:
        - Slide-specific improvements (e.g., "Slide 3: Add market share data")
        - Content gaps (e.g., "Missing competitive analysis")
        - Visual enhancements (e.g., "Slide 5: Icon should be 'Shield' not 'Users'")
        
        Args:
            slides: List of slide dictionaries
            dimension_scores: List of dimension scores with formula-based recommendations
            execution_id: Execution ID for tracing
            
        Returns:
            Dictionary with content_improvements, visual_improvements, data_improvements, priority_fixes
        """
        logger.info(
            "llm_recommendations_started",
            execution_id=execution_id,
            slide_count=len(slides),
        )
        
        # Build slide summary for LLM
        slide_summaries = []
        for i, slide in enumerate(slides, 1):
            slide_type = self._get_slide_type(slide)
            title = slide.get("title", "")
            content = slide.get("content", {})
            bullets = content.get("bullets", [])
            has_chart = bool(content.get("chart_data"))
            has_table = bool(content.get("table_data"))
            icon = content.get("icon_name", "")
            
            summary = f"Slide {i} ({slide_type}): '{title}'"
            if bullets:
                summary += f" | {len(bullets)} bullets"
            if has_chart:
                chart_type = content.get("chart_type", "unknown")
                summary += f" | Chart: {chart_type}"
            if has_table:
                summary += " | Table"
            if icon:
                summary += f" | Icon: {icon}"
            
            slide_summaries.append(summary)
        
        # Build dimension score summary
        score_summary = []
        for ds in dimension_scores:
            score_summary.append(
                f"{ds.dimension.value}: {ds.score:.1f}/10 - {', '.join(ds.recommendations) if ds.recommendations else 'No issues'}"
            )
        
        system_prompt = """You are a presentation quality expert specializing in consulting-style presentations.
Your task is to provide SPECIFIC, ACTIONABLE recommendations for improving presentation quality.

Focus on:
1. Slide-specific improvements with slide numbers
2. Concrete examples (e.g., "Add market share data", not "improve content")
3. Visual mismatches (e.g., wrong icon for the message)
4. Data quality issues (e.g., generic labels like "Category 1, 2, 3")
5. Priority ranking (what matters most)

Be direct and specific. Every recommendation should reference a slide number and suggest a concrete action."""

        user_prompt = f"""Analyze this presentation and provide specific improvement recommendations.

SLIDE SUMMARY:
{chr(10).join(slide_summaries)}

DIMENSION SCORES:
{chr(10).join(score_summary)}

Provide recommendations in these categories:
1. content_improvements: Slide-specific content gaps or improvements
2. visual_improvements: Icon, chart type, or layout improvements
3. data_improvements: Data quality issues (generic labels, missing benchmarks)
4. priority_fixes: Top 3-5 most impactful fixes

Return JSON only."""

        try:
            result = await self.call_llm_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                pydantic_model=LLMRecommendations,
                execution_id=execution_id,
            )
            
            logger.info(
                "llm_recommendations_success",
                execution_id=execution_id,
                content_count=len(result.get("content_improvements", [])),
                visual_count=len(result.get("visual_improvements", [])),
                data_count=len(result.get("data_improvements", [])),
                priority_count=len(result.get("priority_fixes", [])),
            )
            
            return result
            
        except Exception as e:
            logger.warning(
                "llm_recommendations_failed_graceful_degradation",
                execution_id=execution_id,
                error=str(e),
            )
            # Graceful degradation: return formula-based recommendations
            return {
                "content_improvements": [],
                "visual_improvements": [],
                "data_improvements": [],
                "priority_fixes": ["LLM recommendations unavailable - see dimension scores"],
            }
    
    def score_presentation(
        self,
        presentation_id: str,
        slides: List[Dict[str, Any]],
        execution_id: Optional[str] = None,
        retry_count: int = 0,
        use_llm_recommendations: bool = True,
    ) -> QualityScoreResult:
        """
        Main scoring method - evaluates presentation across all dimensions.
        
        Implements:
        1. Score all 5 dimensions
        2. Calculate composite weighted average
        3. Generate recommendations per dimension
        4. Optionally generate LLM-powered specific recommendations (Phase 4)
        5. Determine if feedback loop is needed
        
        Args:
            presentation_id: Presentation ID
            slides: List of slide dictionaries
            execution_id: Optional execution ID for tracing
            retry_count: Current retry count for feedback loop
            use_llm_recommendations: Whether to generate LLM recommendations (default True)
            
        Returns:
            Complete QualityScoreResult
        """
        logger.info(
            "quality_scoring_started",
            presentation_id=presentation_id,
            execution_id=execution_id,
            slide_count=len(slides),
            retry_count=retry_count,
            use_llm_recommendations=use_llm_recommendations,
        )
        
        # Score all dimensions
        dimension_scores = [
            self.score_content_depth(slides),
            self.score_visual_appeal(slides),
            self.score_structure_coherence(slides),
            self.score_data_accuracy(slides),
            self.score_clarity(slides),
        ]
        
        # Calculate composite score
        composite_score = self.calculate_composite_score(dimension_scores)
        
        # Generate formula-based recommendations
        recommendations = self.generate_recommendations(dimension_scores)
        
        # Generate LLM-powered recommendations if enabled and execution_id provided
        if use_llm_recommendations and execution_id:
            import asyncio
            try:
                llm_recs = asyncio.run(
                    self.generate_llm_recommendations(
                        slides=slides,
                        dimension_scores=dimension_scores,
                        execution_id=execution_id,
                    )
                )
                # Merge LLM recommendations into the recommendations dict
                recommendations["llm_content_improvements"] = llm_recs.get("content_improvements", [])
                recommendations["llm_visual_improvements"] = llm_recs.get("visual_improvements", [])
                recommendations["llm_data_improvements"] = llm_recs.get("data_improvements", [])
                recommendations["llm_priority_fixes"] = llm_recs.get("priority_fixes", [])
            except Exception as e:
                logger.warning(
                    "llm_recommendations_skipped",
                    execution_id=execution_id,
                    error=str(e),
                )
        
        # Determine if feedback loop is needed
        requires_feedback_loop = self.should_trigger_feedback_loop(
            composite_score,
            retry_count
        )
        
        # Build scoring details
        scoring_details = {
            "dimensions": {
                ds.dimension.value: {
                    "score": ds.score,
                    "weight": ds.weight,
                    "weighted_score": ds.weighted_score,
                    "details": ds.details
                }
                for ds in dimension_scores
            },
            "retry_count": retry_count,
            "max_retries": MAX_FEEDBACK_RETRIES,
            "threshold": QUALITY_THRESHOLD_FEEDBACK_LOOP,
            "llm_recommendations_used": use_llm_recommendations and execution_id is not None,
        }
        
        # Create result
        result = QualityScoreResult(
            presentation_id=presentation_id,
            execution_id=execution_id,
            content_depth=next(ds.score for ds in dimension_scores if ds.dimension == ScoreDimension.CONTENT_DEPTH),
            visual_appeal=next(ds.score for ds in dimension_scores if ds.dimension == ScoreDimension.VISUAL_APPEAL),
            structure_coherence=next(ds.score for ds in dimension_scores if ds.dimension == ScoreDimension.STRUCTURE_COHERENCE),
            data_accuracy=next(ds.score for ds in dimension_scores if ds.dimension == ScoreDimension.DATA_ACCURACY),
            clarity=next(ds.score for ds in dimension_scores if ds.dimension == ScoreDimension.CLARITY),
            composite_score=composite_score,
            recommendations=recommendations,
            requires_feedback_loop=requires_feedback_loop,
            scoring_details=scoring_details
        )
        
        logger.info(
            "quality_scoring_completed",
            presentation_id=presentation_id,
            execution_id=execution_id,
            composite_score=composite_score,
            requires_feedback_loop=requires_feedback_loop,
            recommendation_count=sum(len(recs) for recs in recommendations.values())
        )
        
        return result


# Global agent instance
quality_scoring_agent = QualityScoringAgent()
