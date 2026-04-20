"""
Example usage of Storyboarding Agent and Presentation Compiler.

This demonstrates how to use the agents in the presentation generation pipeline.
"""

import asyncio
import json
from typing import Any

from .storyboarding import StoryboardingAgent
from .conflict_resolution import ConflictResolutionEngine
from .presentation_compiler import PresentationCompiler


def example_storyboarding_agent():
    """Example: Using Storyboarding Agent directly."""
    print("=" * 80)
    print("Example 1: Storyboarding Agent")
    print("=" * 80)
    
    agent = StoryboardingAgent()
    
    # Generate presentation plan
    topic = "Healthcare Market Analysis and Growth Opportunities"
    industry = "healthcare"
    
    print(f"\nTopic: {topic}")
    print(f"Industry: {industry}")
    
    plan = agent.generate_presentation_plan(topic, industry)
    
    print(f"\nGenerated Plan:")
    print(f"  Total Slides: {plan.total_slides}")
    print(f"  Sections: {len(plan.sections)}")
    print(f"\nSection Breakdown:")
    
    for section in plan.sections:
        types_str = ", ".join([t.value for t in section.slide_types])
        print(f"  - {section.name}: {section.slide_count} slides ({types_str})")
    
    # Validate visual diversity
    all_types = []
    for section in plan.sections:
        all_types.extend([t.value for t in section.slide_types])
    
    print(f"\nSlide Type Sequence: {' → '.join(all_types)}")
    
    # Check for violations
    violations = 0
    for i in range(len(all_types) - 2):
        if all_types[i] == all_types[i+1] == all_types[i+2]:
            violations += 1
    
    print(f"Visual Diversity Violations: {violations}")
    
    return plan


def example_conflict_resolution():
    """Example: Using Conflict Resolution Engine."""
    print("\n" + "=" * 80)
    print("Example 2: Conflict Resolution Engine")
    print("=" * 80)
    
    engine = ConflictResolutionEngine()
    
    # Create a plan
    plan = {
        "plan_id": "example-plan",
        "topic": "Test Topic",
        "industry": "technology",
        "total_slides": 3,
        "sections": [
            {
                "name": "Title",
                "slide_count": 1,
                "slide_types": ["title"]
            },
            {
                "name": "Content",
                "slide_count": 2,
                "slide_types": ["content", "chart"]
            }
        ]
    }
    
    # Simulate LLM output with conflicts
    llm_output = {
        "slides": [
            {
                "slide_id": "1",
                "slide_number": 1,
                "type": "content",  # WRONG: should be "title"
                "visual_hint": "bullet-left",  # WRONG: should be "centered"
                "title": "Introduction",
                "content": {"bullets": ["Point 1", "Point 2"]}
            },
            {
                "slide_id": "2",
                "slide_number": 2,
                "type": "table",  # WRONG: should be "content"
                "visual_hint": "split-table-left",
                "title": "Analysis",
                "content": {"bullets": ["Analysis point"]}
            },
            {
                "slide_id": "3",
                "slide_number": 3,
                "type": "chart",  # CORRECT
                "visual_hint": "split-chart-right",  # CORRECT
                "title": "Data",
                "content": {"chart_data": {}}
            }
        ]
    }
    
    print("\nOriginal LLM Output:")
    for slide in llm_output["slides"]:
        print(f"  Slide {slide['slide_number']}: type={slide['type']}, hint={slide['visual_hint']}")
    
    # Resolve conflicts
    corrected, conflicts = engine.validate_and_resolve(plan, llm_output)
    
    print(f"\nConflicts Detected: {len(conflicts)}")
    for conflict in conflicts:
        print(f"  - {conflict.conflict_type.value}: "
              f"Storyboard={conflict.storyboard_value}, LLM={conflict.llm_value}")
    
    print("\nCorrected Output:")
    for slide in corrected["slides"]:
        print(f"  Slide {slide['slide_number']}: type={slide['type']}, hint={slide['visual_hint']}")
    
    # Get summary
    summary = engine.get_conflict_summary()
    print(f"\nConflict Summary:")
    print(f"  Total Conflicts: {summary['total_conflicts']}")
    print(f"  By Type: {summary['conflicts_by_type']}")


async def example_presentation_compiler():
    """Example: Using Presentation Compiler."""
    print("\n" + "=" * 80)
    print("Example 3: Presentation Compiler")
    print("=" * 80)
    
    compiler = PresentationCompiler()
    
    # Mock functions for agents
    async def mock_industry_classifier(topic: str) -> dict[str, Any]:
        return {
            "industry": "healthcare",
            "confidence": 0.95,
            "sub_sector": "clinical research",
            "target_audience": "executives"
        }
    
    async def mock_llm_generator(
        topic: str,
        industry: str,
        presentation_plan: dict[str, Any],
        detected_context: dict[str, Any]
    ) -> dict[str, Any]:
        # Generate mock slides based on plan
        slides = []
        slide_num = 1
        
        for section in presentation_plan["sections"]:
            for slide_type in section["slide_types"]:
                slides.append({
                    "slide_id": f"slide-{slide_num}",
                    "slide_number": slide_num,
                    "type": slide_type,
                    "title": f"{section['name']} Slide {slide_num}",
                    "content": {"bullets": ["Content point 1", "Content point 2"]},
                    "visual_hint": "bullet-left"
                })
                slide_num += 1
        
        return {"slides": slides}
    
    async def mock_validator(
        slides: list[dict[str, Any]],
        presentation_plan: dict[str, Any]
    ) -> dict[str, Any]:
        return {"slides": slides, "validation_passed": True}
    
    async def mock_quality_scorer(presentation: dict[str, Any]) -> dict[str, Any]:
        return {
            "quality_score": 8.5,
            "dimensions": {
                "content_depth": 8.0,
                "visual_appeal": 9.0,
                "structure_coherence": 8.5,
                "data_accuracy": 8.5,
                "clarity": 9.0
            }
        }
    
    # Compile presentation
    topic = "Healthcare Innovation and Digital Transformation"
    compilation_id = "example-compilation-001"
    
    print(f"\nCompiling presentation...")
    print(f"Topic: {topic}")
    
    report = await compiler.compile(
        topic=topic,
        compilation_id=compilation_id,
        industry_classifier_fn=mock_industry_classifier,
        llm_generator_fn=mock_llm_generator,
        validator_fn=mock_validator,
        quality_scorer_fn=mock_quality_scorer
    )
    
    print(f"\nCompilation Report:")
    print(f"  Compilation ID: {report.compilation_id}")
    print(f"  Industry: {report.industry}")
    print(f"  Total Duration: {report.total_duration_ms:.2f}ms")
    print(f"  Conflicts Detected: {report.conflicts_detected}")
    
    print(f"\nPhase Results:")
    for phase_result in report.phases:
        status_icon = "✓" if phase_result.status.value == "completed" else "✗"
        duration = f"{phase_result.duration_ms:.2f}ms" if phase_result.duration_ms else "N/A"
        print(f"  {status_icon} {phase_result.phase.value}: {phase_result.status.value} ({duration})")
    
    if report.final_output:
        slides = report.final_output.get("slides", [])
        print(f"\nFinal Output:")
        print(f"  Total Slides: {len(slides)}")
        print(f"  Quality Score: {report.final_output.get('quality_score')}")


def main():
    """Run all examples."""
    # Example 1: Storyboarding Agent
    plan = example_storyboarding_agent()
    
    # Example 2: Conflict Resolution
    example_conflict_resolution()
    
    # Example 3: Presentation Compiler
    asyncio.run(example_presentation_compiler())
    
    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
