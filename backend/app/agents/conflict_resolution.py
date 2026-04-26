"""
Conflict Resolution Engine - Enforces Storyboarding Agent authority.

This engine ensures that Storyboarding Agent decisions ALWAYS override
LLM structural suggestions. The precedence hierarchy is:

1. Slide count and types: Storyboarding Agent has absolute authority
2. Content structure within slides: Storyboarding Agent defines framework, LLM fills content
3. Visual layout decisions: Storyboarding Agent determines layout, LLM provides content
4. Narrative flow: Storyboarding Agent controls sequence, LLM enhances storytelling

When LLM attempts to modify slide structure, the engine rejects changes and logs conflicts.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """Types of conflicts between Storyboarding and LLM decisions."""
    SLIDE_COUNT_MISMATCH = "slide_count_mismatch"
    SLIDE_TYPE_MISMATCH = "slide_type_mismatch"
    SECTION_STRUCTURE_VIOLATION = "section_structure_violation"
    VISUAL_HINT_OVERRIDE = "visual_hint_override"
    NARRATIVE_FLOW_VIOLATION = "narrative_flow_violation"


class ConflictResolution(str, Enum):
    """Resolution actions for conflicts."""
    ENFORCE_STORYBOARD = "enforce_storyboard"
    REJECT_LLM_CHANGE = "reject_llm_change"
    LOG_AND_CONTINUE = "log_and_continue"


class ConflictEvent(BaseModel):
    """Record of a conflict event."""
    conflict_type: ConflictType
    resolution: ConflictResolution
    storyboard_value: Any
    llm_value: Any
    slide_index: int | None = None
    message: str
    timestamp: str


class ConflictResolutionEngine:
    """
    Conflict Resolution Engine - Enforces Storyboarding Agent authority.
    
    This engine implements the strict precedence hierarchy where Storyboarding
    Agent decisions ALWAYS override LLM structural suggestions.
    
    Key responsibilities:
    1. Validate LLM output against Presentation_Plan_JSON
    2. Detect structural conflicts
    3. Enforce Storyboarding decisions
    4. Log all conflict events
    5. Reject unauthorized structural changes
    """

    def __init__(self):
        """Initialize the Conflict Resolution Engine."""
        self.conflict_log: list[ConflictEvent] = []

    def validate_and_resolve(
        self,
        presentation_plan: dict[str, Any],
        llm_output: dict[str, Any]
    ) -> tuple[dict[str, Any], list[ConflictEvent]]:
        """
        Validate LLM output against presentation plan and resolve conflicts.
        
        This is the main entry point for conflict resolution.
        
        Args:
            presentation_plan: Original Presentation_Plan_JSON from Storyboarding Agent
            llm_output: Generated content from LLM
            
        Returns:
            Tuple of (corrected_output, conflict_events)
        """
        self.conflict_log = []
        corrected_output = llm_output.copy()
        
        # Rule 1: Enforce slide count
        corrected_output = self._enforce_slide_count(
            presentation_plan,
            corrected_output
        )
        
        # Rule 2: Enforce slide types
        corrected_output = self._enforce_slide_types(
            presentation_plan,
            corrected_output
        )
        
        # Rule 3: Enforce visual hints
        corrected_output = self._enforce_visual_hints(
            presentation_plan,
            corrected_output
        )
        
        # Rule 4: Enforce section structure
        corrected_output = self._enforce_section_structure(
            presentation_plan,
            corrected_output
        )
        
        # Rule 5: Enforce narrative flow
        corrected_output = self._enforce_narrative_flow(
            presentation_plan,
            corrected_output
        )
        
        return corrected_output, self.conflict_log

    def _enforce_slide_count(
        self,
        plan: dict[str, Any],
        output: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enforce slide count from presentation plan.
        
        Storyboarding Agent has absolute authority over slide count.
        
        Args:
            plan: Presentation plan
            output: LLM output
            
        Returns:
            Corrected output with enforced slide count
        """
        expected_count = plan.get("total_slides")
        actual_slides = output.get("slides", [])
        actual_count = len(actual_slides)
        
        if actual_count != expected_count:
            # Log conflict
            conflict = ConflictEvent(
                conflict_type=ConflictType.SLIDE_COUNT_MISMATCH,
                resolution=ConflictResolution.ENFORCE_STORYBOARD,
                storyboard_value=expected_count,
                llm_value=actual_count,
                message=f"LLM generated {actual_count} slides, but Storyboarding Agent "
                        f"specified {expected_count}. Enforcing Storyboarding decision.",
                timestamp=datetime.utcnow().isoformat()
            )
            self.conflict_log.append(conflict)
            logger.warning(f"Conflict detected: {conflict.message}")
            
            # Enforce: truncate or pad slides
            if actual_count > expected_count:
                logger.warning(
                    "slides_truncated_by_conflict_resolution",
                    original_count=actual_count,
                    truncated_to=expected_count,
                    removed_slides=[s.get("slide_number", i) for i, s in enumerate(actual_slides[expected_count:], expected_count + 1)]
                )
                output["slides"] = actual_slides[:expected_count]
            elif actual_count < expected_count:
                # Pad with placeholder slides
                logger.info(
                    "slides_padded_by_conflict_resolution",
                    original_count=actual_count,
                    padded_to=expected_count,
                    added_slides=list(range(actual_count + 1, expected_count + 1))
                )
                for i in range(expected_count - actual_count):
                    output["slides"].append({
                        "slide_id": f"placeholder_{i}",
                        "slide_number": actual_count + i + 1,
                        "type": "content",
                        "title": "Additional Content",
                        "content": {"bullets": ["Content to be generated"]},
                        "visual_hint": "bullet-left"
                    })
        
        return output

    def _enforce_slide_types(
        self,
        plan: dict[str, Any],
        output: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enforce slide types from presentation plan.
        
        Storyboarding Agent has absolute authority over slide types.
        
        Args:
            plan: Presentation plan
            output: LLM output
            
        Returns:
            Corrected output with enforced slide types
        """
        # Build expected types from sections
        expected_types = []
        for section in plan.get("sections", []):
            expected_types.extend(section.get("slide_types", []))
        
        slides = output.get("slides", [])
        
        for i, slide in enumerate(slides):
            if i < len(expected_types):
                expected_type = expected_types[i]
                actual_type = slide.get("type")
                
                if actual_type != expected_type:
                    # Log conflict
                    conflict = ConflictEvent(
                        conflict_type=ConflictType.SLIDE_TYPE_MISMATCH,
                        resolution=ConflictResolution.ENFORCE_STORYBOARD,
                        storyboard_value=expected_type,
                        llm_value=actual_type,
                        slide_index=i,
                        message=f"Slide {i+1}: LLM used type '{actual_type}', but Storyboarding "
                                f"Agent specified '{expected_type}'. Enforcing Storyboarding decision.",
                        timestamp=datetime.utcnow().isoformat()
                    )
                    self.conflict_log.append(conflict)
                    logger.warning(f"Conflict detected: {conflict.message}")
                    
                    # Enforce: override type
                    slide["type"] = expected_type
        
        return output

    def _enforce_visual_hints(
        self,
        plan: dict[str, Any],
        output: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enforce visual hints based on slide types.
        
        Storyboarding Agent determines layout through slide types.
        
        Args:
            plan: Presentation plan
            output: LLM output
            
        Returns:
            Corrected output with enforced visual hints
        """
        # Type to visual hint mapping
        type_to_hint = {
            "title": "centered",
            "content": "bullet-left",
            "chart": "split-chart-right",
            "table": "split-table-left",
            "comparison": "two-column",
        }
        
        slides = output.get("slides", [])
        
        for i, slide in enumerate(slides):
            slide_type = slide.get("type")
            expected_hint = type_to_hint.get(slide_type, "bullet-left")
            actual_hint = slide.get("visual_hint")
            
            if actual_hint != expected_hint:
                # Log conflict
                conflict = ConflictEvent(
                    conflict_type=ConflictType.VISUAL_HINT_OVERRIDE,
                    resolution=ConflictResolution.ENFORCE_STORYBOARD,
                    storyboard_value=expected_hint,
                    llm_value=actual_hint,
                    slide_index=i,
                    message=f"Slide {i+1}: LLM used visual_hint '{actual_hint}', but type "
                            f"'{slide_type}' requires '{expected_hint}'. Enforcing Storyboarding decision.",
                    timestamp=datetime.utcnow().isoformat()
                )
                self.conflict_log.append(conflict)
                logger.warning(f"Conflict detected: {conflict.message}")
                
                # Enforce: override visual hint
                slide["visual_hint"] = expected_hint
        
        return output

    def _enforce_section_structure(
        self,
        plan: dict[str, Any],
        output: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enforce section structure from presentation plan.
        
        Storyboarding Agent controls section boundaries and mapping.
        
        Args:
            plan: Presentation plan
            output: LLM output
            
        Returns:
            Corrected output with enforced section structure
        """
        sections = plan.get("sections", [])
        slides = output.get("slides", [])
        
        # Assign section metadata to slides based on plan
        slide_index = 0
        for section in sections:
            section_name = section.get("name")
            section_slide_count = section.get("slide_count", 0)
            
            for _ in range(section_slide_count):
                if slide_index < len(slides):
                    # Add section metadata if not present or incorrect
                    current_section = slides[slide_index].get("metadata", {}).get("section")
                    if current_section != section_name:
                        if "metadata" not in slides[slide_index]:
                            slides[slide_index]["metadata"] = {}
                        slides[slide_index]["metadata"]["section"] = section_name
                        
                        if current_section:
                            # Log conflict
                            conflict = ConflictEvent(
                                conflict_type=ConflictType.SECTION_STRUCTURE_VIOLATION,
                                resolution=ConflictResolution.ENFORCE_STORYBOARD,
                                storyboard_value=section_name,
                                llm_value=current_section,
                                slide_index=slide_index,
                                message=f"Slide {slide_index+1}: LLM assigned to section '{current_section}', "
                                        f"but Storyboarding Agent specified '{section_name}'. "
                                        f"Enforcing Storyboarding decision.",
                                timestamp=datetime.utcnow().isoformat()
                            )
                            self.conflict_log.append(conflict)
                            logger.warning(f"Conflict detected: {conflict.message}")
                    
                    slide_index += 1
        
        return output

    def _enforce_narrative_flow(
        self,
        plan: dict[str, Any],
        output: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enforce narrative flow from presentation plan.
        
        Storyboarding Agent controls sequence and progression.
        
        Args:
            plan: Presentation plan
            output: LLM output
            
        Returns:
            Corrected output with enforced narrative flow
        """
        slides = output.get("slides", [])
        
        # Ensure slides are in correct order
        for i, slide in enumerate(slides):
            expected_number = i + 1
            actual_number = slide.get("slide_number")
            
            if actual_number != expected_number:
                # Log conflict
                conflict = ConflictEvent(
                    conflict_type=ConflictType.NARRATIVE_FLOW_VIOLATION,
                    resolution=ConflictResolution.ENFORCE_STORYBOARD,
                    storyboard_value=expected_number,
                    llm_value=actual_number,
                    slide_index=i,
                    message=f"Slide at position {i}: LLM assigned slide_number {actual_number}, "
                            f"but should be {expected_number}. Enforcing Storyboarding decision.",
                    timestamp=datetime.utcnow().isoformat()
                )
                self.conflict_log.append(conflict)
                logger.warning(f"Conflict detected: {conflict.message}")
                
                # Enforce: correct slide number
                slide["slide_number"] = expected_number
        
        return output

    def get_conflict_summary(self) -> dict[str, Any]:
        """
        Get summary of all conflicts detected and resolved.
        
        Returns:
            Dictionary with conflict statistics and details
        """
        conflict_counts = {}
        for conflict in self.conflict_log:
            conflict_type = conflict.conflict_type.value
            conflict_counts[conflict_type] = conflict_counts.get(conflict_type, 0) + 1
        
        return {
            "total_conflicts": len(self.conflict_log),
            "conflicts_by_type": conflict_counts,
            "all_conflicts": [c.model_dump() for c in self.conflict_log]
        }

    def has_conflicts(self) -> bool:
        """Check if any conflicts were detected."""
        return len(self.conflict_log) > 0
