"""
Example usage of the Quality Scoring Agent.

This demonstrates how to use the quality scoring agent to evaluate
presentation quality across five dimensions and trigger feedback loops.
"""

from quality_scoring import quality_scoring_agent


def example_high_quality_presentation():
    """Example of a high-quality presentation that should score well."""
    
    presentation_id = "pres-123"
    execution_id = "exec-456"
    
    slides = [
        {
            "slide_id": "slide-1",
            "slide_number": 1,
            "type": "title",
            "title": "Healthcare Digital Transformation",
            "content": {},
            "visual_hint": "centered"
        },
        {
            "slide_id": "slide-2",
            "slide_number": 2,
            "type": "content",
            "title": "Agenda Overview",
            "content": {
                "bullets": [
                    "Current challenges",
                    "Market analysis",
                    "Strategic recommendations",
                    "Implementation roadmap"
                ]
            },
            "visual_hint": "bullet-left",
            "layout_constraints": {
                "max_content_density": 0.75,
                "min_whitespace_ratio": 0.25
            }
        },
        {
            "slide_id": "slide-3",
            "slide_number": 3,
            "type": "content",
            "title": "Problem Statement",
            "content": {
                "bullets": [
                    "Legacy systems limit growth",
                    "Patient data fragmented",
                    "Compliance risks increasing"
                ],
                "icon_name": "alert-circle"
            },
            "visual_hint": "bullet-left"
        },
        {
            "slide_id": "slide-4",
            "slide_number": 4,
            "type": "chart",
            "title": "Market Analysis Trends",
            "content": {
                "chart_data": {
                    "chart_type": "line",
                    "data": [
                        {"year": 2021, "value": 100},
                        {"year": 2022, "value": 125},
                        {"year": 2023, "value": 160}
                    ]
                }
            },
            "visual_hint": "split-chart-right"
        },
        {
            "slide_id": "slide-5",
            "slide_number": 5,
            "type": "table",
            "title": "Evidence Supporting Change",
            "content": {
                "table_data": {
                    "headers": ["Metric", "Current", "Target"],
                    "rows": [
                        ["Efficiency", "65%", "90%"],
                        ["Satisfaction", "72%", "95%"]
                    ]
                }
            },
            "visual_hint": "split-table-left"
        },
        {
            "slide_id": "slide-6",
            "slide_number": 6,
            "type": "comparison",
            "title": "Recommendations Comparison",
            "content": {
                "comparison_data": {
                    "left": {
                        "title": "Option A",
                        "points": ["Fast implementation", "Lower cost"]
                    },
                    "right": {
                        "title": "Option B",
                        "points": ["Comprehensive solution", "Long-term value"]
                    }
                }
            },
            "visual_hint": "two-column"
        },
        {
            "slide_id": "slide-7",
            "slide_number": 7,
            "type": "content",
            "title": "Conclusion and Next Steps",
            "content": {
                "bullets": [
                    "Begin pilot program",
                    "Secure stakeholder buy-in",
                    "Launch in Q2"
                ],
                "highlight_text": "Expected ROI: 250%"
            },
            "visual_hint": "bullet-left"
        }
    ]
    
    # Score the presentation
    result = quality_scoring_agent.score_presentation(
        presentation_id=presentation_id,
        slides=slides,
        execution_id=execution_id,
        retry_count=0
    )
    
    print("=== High Quality Presentation Scoring ===")
    print(f"Composite Score: {result.composite_score:.2f}/10")
    print(f"\nDimension Scores:")
    print(f"  Content Depth: {result.content_depth:.2f}/10")
    print(f"  Visual Appeal: {result.visual_appeal:.2f}/10")
    print(f"  Structure Coherence: {result.structure_coherence:.2f}/10")
    print(f"  Data Accuracy: {result.data_accuracy:.2f}/10")
    print(f"  Clarity: {result.clarity:.2f}/10")
    print(f"\nRequires Feedback Loop: {result.requires_feedback_loop}")
    
    if result.recommendations:
        print(f"\nRecommendations:")
        for dimension, recs in result.recommendations.items():
            print(f"  {dimension}:")
            for rec in recs:
                print(f"    - {rec}")
    
    return result


def example_low_quality_presentation():
    """Example of a low-quality presentation that should trigger feedback loop."""
    
    presentation_id = "pres-789"
    execution_id = "exec-012"
    
    slides = [
        {
            "slide_id": "slide-1",
            "slide_number": 1,
            "type": "content",  # Should be title
            "title": "This is a very long title that exceeds the maximum word count limit",
            "content": {
                "bullets": [
                    "This is a very long bullet point that exceeds the maximum word count",
                    "Another long bullet with too many words in it",
                    "Yet another bullet",
                    "Fourth bullet",
                    "Fifth bullet - too many!",
                    "Sixth bullet - way too many!"
                ]
            },
            "visual_hint": "bullet-left"
        },
        {
            "slide_id": "slide-2",
            "slide_number": 2,
            "type": "content",
            "title": "More Content",
            "content": {
                "bullets": []  # Empty content
            },
            "visual_hint": "bullet-left"
        },
        {
            "slide_id": "slide-3",
            "slide_number": 3,
            "type": "content",
            "title": "Even More Content",
            "content": {
                "bullets": ["Single bullet"]
            },
            "visual_hint": "bullet-left"
        },
        {
            "slide_id": "slide-4",
            "slide_number": 4,
            "type": "chart",
            "title": "Chart Without Data",
            "content": {},  # Missing chart_data
            "visual_hint": "split-chart-right"
        }
    ]
    
    # Score the presentation
    result = quality_scoring_agent.score_presentation(
        presentation_id=presentation_id,
        slides=slides,
        execution_id=execution_id,
        retry_count=0
    )
    
    print("\n\n=== Low Quality Presentation Scoring ===")
    print(f"Composite Score: {result.composite_score:.2f}/10")
    print(f"\nDimension Scores:")
    print(f"  Content Depth: {result.content_depth:.2f}/10")
    print(f"  Visual Appeal: {result.visual_appeal:.2f}/10")
    print(f"  Structure Coherence: {result.structure_coherence:.2f}/10")
    print(f"  Data Accuracy: {result.data_accuracy:.2f}/10")
    print(f"  Clarity: {result.clarity:.2f}/10")
    print(f"\nRequires Feedback Loop: {result.requires_feedback_loop}")
    
    if result.recommendations:
        print(f"\nRecommendations:")
        for dimension, recs in result.recommendations.items():
            print(f"  {dimension}:")
            for rec in recs:
                print(f"    - {rec}")
    
    return result


def example_feedback_loop_workflow():
    """Example of feedback loop workflow with retries."""
    
    presentation_id = "pres-feedback"
    execution_id = "exec-feedback"
    
    # Initial low-quality slides
    slides = [
        {
            "slide_id": "slide-1",
            "slide_number": 1,
            "type": "content",
            "title": "Basic Presentation",
            "content": {"bullets": ["Point one"]},
            "visual_hint": "bullet-left"
        }
    ]
    
    print("\n\n=== Feedback Loop Workflow ===")
    
    # Attempt 1
    print("\nAttempt 1 (Initial):")
    result1 = quality_scoring_agent.score_presentation(
        presentation_id=presentation_id,
        slides=slides,
        execution_id=execution_id,
        retry_count=0
    )
    print(f"  Score: {result1.composite_score:.2f}/10")
    print(f"  Feedback Loop Triggered: {result1.requires_feedback_loop}")
    
    # Attempt 2 (after improvements)
    if result1.requires_feedback_loop:
        print("\nAttempt 2 (After improvements):")
        result2 = quality_scoring_agent.score_presentation(
            presentation_id=presentation_id,
            slides=slides,
            execution_id=execution_id,
            retry_count=1
        )
        print(f"  Score: {result2.composite_score:.2f}/10")
        print(f"  Feedback Loop Triggered: {result2.requires_feedback_loop}")
    
    # Attempt 3 (max retries reached)
    if result1.requires_feedback_loop:
        print("\nAttempt 3 (Max retries):")
        result3 = quality_scoring_agent.score_presentation(
            presentation_id=presentation_id,
            slides=slides,
            execution_id=execution_id,
            retry_count=2
        )
        print(f"  Score: {result3.composite_score:.2f}/10")
        print(f"  Feedback Loop Triggered: {result3.requires_feedback_loop}")
        print(f"  Note: Max retries reached, delivering best available result")


if __name__ == "__main__":
    # Run examples
    example_high_quality_presentation()
    example_low_quality_presentation()
    example_feedback_loop_workflow()
