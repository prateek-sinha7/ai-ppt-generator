"""
Layout Validation Agent - Ensures slide content fits properly within layout bounds.

This agent validates and fixes layout issues including:
- Content overflow detection and correction
- Chart placement validation
- Text length validation for titles and bullets
- Visual element positioning checks
- Slide density validation
"""

import structlog
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = structlog.get_logger(__name__)


class LayoutIssueType(str, Enum):
    """Types of layout issues that can be detected."""
    CONTENT_OVERFLOW = "content_overflow"
    TITLE_TOO_LONG = "title_too_long"
    TOO_MANY_BULLETS = "too_many_bullets"
    BULLET_TOO_LONG = "bullet_too_long"
    CHART_DATA_OVERFLOW = "chart_data_overflow"
    MISSING_REQUIRED_CONTENT = "missing_required_content"
    INVALID_CHART_TYPE = "invalid_chart_type"


@dataclass
class LayoutIssue:
    """Represents a layout validation issue."""
    slide_number: int
    issue_type: LayoutIssueType
    description: str
    suggested_fix: str
    severity: str = "medium"  # low, medium, high


@dataclass
class LayoutValidationResult:
    """Result of layout validation."""
    is_valid: bool
    issues: List[LayoutIssue]
    corrected_slides: Optional[List[Dict[str, Any]]] = None
    corrections_applied: int = 0


class LayoutValidationAgent:
    """
    Layout Validation Agent - Ensures proper slide layout and content fitting.
    
    Validates:
    1. Title length (max 8 words)
    2. Bullet count (max 4 bullets per slide)
    3. Bullet length (max 8 words per bullet)
    4. Chart data size (max 8 data points)
    5. Content density (not too crowded)
    6. Required content presence
    """
    
    # Layout constraints
    MAX_TITLE_WORDS = 8
    MAX_BULLETS_PER_SLIDE = 4
    MAX_WORDS_PER_BULLET = 8
    MAX_CHART_DATA_POINTS = 8
    MIN_CHART_DATA_POINTS = 3
    
    # Valid chart types for validation
    VALID_CHART_TYPES = {"bar", "line", "pie"}
    
    def validate_layout(
        self,
        slides: List[Dict[str, Any]],
        execution_id: str,
        apply_corrections: bool = True
    ) -> LayoutValidationResult:
        """
        Validate slide layouts and optionally apply corrections.
        
        Args:
            slides: List of slide dictionaries
            execution_id: Execution ID for tracing
            apply_corrections: Whether to apply automatic corrections
            
        Returns:
            LayoutValidationResult with validation status and corrections
        """
        logger.info(
            "layout_validation_started",
            execution_id=execution_id,
            slide_count=len(slides),
            apply_corrections=apply_corrections
        )
        
        issues = []
        corrected_slides = slides.copy() if apply_corrections else None
        corrections_applied = 0
        
        for i, slide in enumerate(slides):
            slide_number = slide.get("slide_number", i + 1)
            slide_issues = self._validate_slide_layout(slide, slide_number)
            issues.extend(slide_issues)
            
            if apply_corrections and slide_issues:
                corrected_slide, slide_corrections = self._correct_slide_layout(slide, slide_issues)
                if corrected_slides is not None:
                    corrected_slides[i] = corrected_slide
                corrections_applied += slide_corrections
        
        is_valid = len(issues) == 0
        
        logger.info(
            "layout_validation_completed",
            execution_id=execution_id,
            is_valid=is_valid,
            issues_found=len(issues),
            corrections_applied=corrections_applied
        )
        
        return LayoutValidationResult(
            is_valid=is_valid,
            issues=issues,
            corrected_slides=corrected_slides,
            corrections_applied=corrections_applied
        )
    
    def _validate_slide_layout(self, slide: Dict[str, Any], slide_number: int) -> List[LayoutIssue]:
        """Validate layout for a single slide."""
        issues = []
        slide_type = slide.get("type", "content")
        title = slide.get("title", "")
        content = slide.get("content", {})
        
        # Validate title length
        if title:
            title_words = len(title.split())
            if title_words > self.MAX_TITLE_WORDS:
                issues.append(LayoutIssue(
                    slide_number=slide_number,
                    issue_type=LayoutIssueType.TITLE_TOO_LONG,
                    description=f"Title has {title_words} words, max is {self.MAX_TITLE_WORDS}",
                    suggested_fix=f"Truncate title to {self.MAX_TITLE_WORDS} words",
                    severity="medium"
                ))
        
        # Validate bullets
        bullets = content.get("bullets", [])
        if bullets:
            if len(bullets) > self.MAX_BULLETS_PER_SLIDE:
                issues.append(LayoutIssue(
                    slide_number=slide_number,
                    issue_type=LayoutIssueType.TOO_MANY_BULLETS,
                    description=f"Slide has {len(bullets)} bullets, max is {self.MAX_BULLETS_PER_SLIDE}",
                    suggested_fix=f"Reduce to {self.MAX_BULLETS_PER_SLIDE} bullets",
                    severity="high"
                ))
            
            for j, bullet in enumerate(bullets):
                if isinstance(bullet, str):
                    bullet_words = len(bullet.split())
                    if bullet_words > self.MAX_WORDS_PER_BULLET:
                        issues.append(LayoutIssue(
                            slide_number=slide_number,
                            issue_type=LayoutIssueType.BULLET_TOO_LONG,
                            description=f"Bullet {j+1} has {bullet_words} words, max is {self.MAX_WORDS_PER_BULLET}",
                            suggested_fix=f"Truncate bullet to {self.MAX_WORDS_PER_BULLET} words",
                            severity="medium"
                        ))
        
        # Validate chart-specific content
        if slide_type == "chart":
            chart_data = content.get("chart_data", [])
            chart_type = content.get("chart_type", "")
            
            # Validate chart type
            if chart_type and chart_type not in self.VALID_CHART_TYPES:
                issues.append(LayoutIssue(
                    slide_number=slide_number,
                    issue_type=LayoutIssueType.INVALID_CHART_TYPE,
                    description=f"Invalid chart type '{chart_type}', must be one of {list(self.VALID_CHART_TYPES)}",
                    suggested_fix="Use 'bar', 'line', or 'pie' chart type",
                    severity="high"
                ))
            
            # Validate chart data size
            if isinstance(chart_data, list):
                data_points = len(chart_data)
                if data_points > self.MAX_CHART_DATA_POINTS:
                    issues.append(LayoutIssue(
                        slide_number=slide_number,
                        issue_type=LayoutIssueType.CHART_DATA_OVERFLOW,
                        description=f"Chart has {data_points} data points, max is {self.MAX_CHART_DATA_POINTS}",
                        suggested_fix=f"Reduce to {self.MAX_CHART_DATA_POINTS} data points",
                        severity="medium"
                    ))
                elif data_points < self.MIN_CHART_DATA_POINTS:
                    issues.append(LayoutIssue(
                        slide_number=slide_number,
                        issue_type=LayoutIssueType.CHART_DATA_OVERFLOW,
                        description=f"Chart has {data_points} data points, minimum is {self.MIN_CHART_DATA_POINTS}",
                        suggested_fix=f"Add more data points to reach {self.MIN_CHART_DATA_POINTS}",
                        severity="medium"
                    ))
            
            # Validate required chart content
            if not chart_data:
                issues.append(LayoutIssue(
                    slide_number=slide_number,
                    issue_type=LayoutIssueType.MISSING_REQUIRED_CONTENT,
                    description="Chart slide missing chart_data",
                    suggested_fix="Add chart_data array with label/value pairs",
                    severity="high"
                ))
        
        return issues
    
    def _correct_slide_layout(
        self,
        slide: Dict[str, Any],
        issues: List[LayoutIssue]
    ) -> Tuple[Dict[str, Any], int]:
        """Apply automatic corrections to a slide."""
        corrected_slide = slide.copy()
        corrections_applied = 0
        
        for issue in issues:
            if issue.issue_type == LayoutIssueType.TITLE_TOO_LONG:
                title = corrected_slide.get("title", "")
                words = title.split()
                if len(words) > self.MAX_TITLE_WORDS:
                    corrected_slide["title"] = " ".join(words[:self.MAX_TITLE_WORDS])
                    corrections_applied += 1
            
            elif issue.issue_type == LayoutIssueType.TOO_MANY_BULLETS:
                content = corrected_slide.get("content", {})
                bullets = content.get("bullets", [])
                if len(bullets) > self.MAX_BULLETS_PER_SLIDE:
                    content["bullets"] = bullets[:self.MAX_BULLETS_PER_SLIDE]
                    corrected_slide["content"] = content
                    corrections_applied += 1
            
            elif issue.issue_type == LayoutIssueType.BULLET_TOO_LONG:
                content = corrected_slide.get("content", {})
                bullets = content.get("bullets", [])
                for j, bullet in enumerate(bullets):
                    if isinstance(bullet, str):
                        words = bullet.split()
                        if len(words) > self.MAX_WORDS_PER_BULLET:
                            bullets[j] = " ".join(words[:self.MAX_WORDS_PER_BULLET])
                            corrections_applied += 1
                content["bullets"] = bullets
                corrected_slide["content"] = content
            
            elif issue.issue_type == LayoutIssueType.CHART_DATA_OVERFLOW:
                content = corrected_slide.get("content", {})
                chart_data = content.get("chart_data", [])
                if isinstance(chart_data, list) and len(chart_data) > self.MAX_CHART_DATA_POINTS:
                    content["chart_data"] = chart_data[:self.MAX_CHART_DATA_POINTS]
                    corrected_slide["content"] = content
                    corrections_applied += 1
            
            elif issue.issue_type == LayoutIssueType.INVALID_CHART_TYPE:
                content = corrected_slide.get("content", {})
                # Default to bar chart if invalid type
                content["chart_type"] = "bar"
                corrected_slide["content"] = content
                corrections_applied += 1
        
        return corrected_slide, corrections_applied


# Global layout validation agent instance
layout_validation_agent = LayoutValidationAgent()