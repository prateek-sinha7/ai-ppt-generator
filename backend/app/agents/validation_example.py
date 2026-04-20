"""
Example usage of the Validation Agent.

This script demonstrates:
1. Basic validation of valid Slide_JSON
2. Validation with auto-correction
3. Content constraint application
4. Handling validation errors
"""

import json
from uuid import uuid4

from app.agents.validation import validation_agent


def example_1_valid_slide_json():
    """Example 1: Validate a valid Slide_JSON."""
    print("\n=== Example 1: Valid Slide_JSON ===\n")
    
    data = {
        "schema_version": "1.0.0",
        "presentation_id": str(uuid4()),
        "total_slides": 2,
        "slides": [
            {
                "slide_id": str(uuid4()),
                "slide_number": 1,
                "type": "title",
                "title": "Healthcare Market Analysis",
                "content": {},
                "visual_hint": "centered",
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25
                },
                "metadata": {
                    "generated_at": "2024-01-01T00:00:00",
                    "provider_used": "claude",
                    "quality_score": 8.5
                }
            },
            {
                "slide_id": str(uuid4()),
                "slide_number": 2,
                "type": "content",
                "title": "Key Findings",
                "content": {
                    "bullets": [
                        "Market growing at 15% annually",
                        "Digital health adoption accelerating",
                        "Regulatory landscape evolving"
                    ]
                },
                "visual_hint": "bullet-left",
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25
                },
                "metadata": {
                    "generated_at": "2024-01-01T00:00:00",
                    "provider_used": "claude",
                    "quality_score": 8.5
                }
            }
        ]
    }
    
    result = validation_agent.validate(data, execution_id="example-1")
    
    print(f"Valid: {result.is_valid}")
    print(f"Errors: {len(result.errors)}")
    print(f"Corrections applied: {result.corrections_applied}")
    
    if result.is_valid:
        print("\n✓ Validation passed!")
    else:
        print("\n✗ Validation failed:")
        for error in result.errors:
            print(f"  - {error.field}: {error.message}")


def example_2_auto_correction():
    """Example 2: Validate with auto-correction."""
    print("\n=== Example 2: Auto-Correction ===\n")
    
    # Problematic data with missing fields and wrong types
    data = {
        "slides": [
            {
                "type": "title_slide",  # Wrong format
                "title": "This is a very long title that exceeds the maximum word count limit",
                "content": {},
                "visual_hint": "center"  # Wrong format
            },
            {
                "type": "content",
                "title": "Content Slide",
                "content": {
                    "bullets": [
                        "Bullet 1",
                        "Bullet 2",
                        "Bullet 3"
                    ]
                },
                "visual_hint": "bullets"  # Wrong format
            }
        ]
    }
    
    print("Original data issues:")
    print("  - Missing schema_version")
    print("  - Missing presentation_id")
    print("  - Missing total_slides")
    print("  - Wrong slide type format: 'title_slide'")
    print("  - Wrong visual hint formats: 'center', 'bullets'")
    print("  - Title exceeds 8 words")
    
    result = validation_agent.validate(data, execution_id="example-2", apply_corrections=True)
    
    print(f"\nValid: {result.is_valid}")
    print(f"Corrections applied: {result.corrections_applied}")
    
    if result.corrected_data:
        print("\nCorrected data:")
        print(f"  - schema_version: {result.corrected_data.get('schema_version')}")
        print(f"  - presentation_id: {result.corrected_data.get('presentation_id')[:8]}...")
        print(f"  - total_slides: {result.corrected_data.get('total_slides')}")
        print(f"  - Slide 1 type: {result.corrected_data['slides'][0]['type']}")
        print(f"  - Slide 1 visual_hint: {result.corrected_data['slides'][0]['visual_hint']}")
        print(f"  - Slide 1 title: {result.corrected_data['slides'][0]['title']}")
        print(f"  - Slide 2 visual_hint: {result.corrected_data['slides'][1]['visual_hint']}")


def example_3_content_constraints():
    """Example 3: Content constraint application with slide splitting."""
    print("\n=== Example 3: Content Constraints & Slide Splitting ===\n")
    
    data = {
        "schema_version": "1.0.0",
        "presentation_id": str(uuid4()),
        "total_slides": 1,
        "slides": [
            {
                "slide_id": str(uuid4()),
                "slide_number": 1,
                "type": "content",
                "title": "Key Points",
                "content": {
                    "bullets": [
                        "This is the first bullet point with some content",
                        "This is the second bullet point with more details",
                        "This is the third bullet point explaining something",
                        "This is the fourth bullet point with information",
                        "This is the fifth bullet point that will overflow",
                        "This is the sixth bullet point that will also overflow"
                    ]
                },
                "visual_hint": "bullet-left",
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25
                },
                "metadata": {
                    "generated_at": "2024-01-01T00:00:00",
                    "provider_used": "claude",
                    "quality_score": 8.5
                }
            }
        ]
    }
    
    print("Original data:")
    print(f"  - Total slides: {data['total_slides']}")
    print(f"  - Bullets in slide 1: {len(data['slides'][0]['content']['bullets'])}")
    
    result = validation_agent.validate(data, execution_id="example-3", apply_corrections=True)
    
    print(f"\nAfter validation:")
    print(f"  - Valid: {result.is_valid}")
    print(f"  - Corrections applied: {result.corrections_applied}")
    
    if result.corrected_data:
        print(f"  - Total slides: {result.corrected_data['total_slides']}")
        print(f"  - Bullets in slide 1: {len(result.corrected_data['slides'][0]['content']['bullets'])}")
        
        if result.corrected_data['total_slides'] > 1:
            print(f"  - Bullets in slide 2 (overflow): {len(result.corrected_data['slides'][1]['content']['bullets'])}")
            print(f"  - Slide 2 title: {result.corrected_data['slides'][1]['title']}")
            print("\n✓ Slide automatically split due to bullet overflow!")


def example_4_validation_errors():
    """Example 4: Handling validation errors."""
    print("\n=== Example 4: Validation Errors ===\n")
    
    # Data with unfixable errors
    data = {
        "schema_version": "1.0.0",
        "presentation_id": str(uuid4()),
        "total_slides": 1,
        "slides": [
            {
                "slide_id": str(uuid4()),
                "slide_number": 1,
                "type": "invalid_type",  # Invalid enum value
                "title": "Test",
                "content": {},
                "visual_hint": "invalid_hint",  # Invalid enum value
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25
                },
                "metadata": {
                    "generated_at": "2024-01-01T00:00:00",
                    "provider_used": "test",
                    "quality_score": 8.5
                }
            }
        ]
    }
    
    result = validation_agent.validate(data, execution_id="example-4", apply_corrections=True)
    
    print(f"Valid: {result.is_valid}")
    print(f"Errors: {len(result.errors)}")
    
    if result.errors:
        print("\nValidation errors:")
        for error in result.errors:
            status = "✓ Auto-corrected" if error.auto_corrected else "✗ Not corrected"
            print(f"  [{status}] {error.field}: {error.message}")


def example_5_round_trip():
    """Example 5: Round-trip validation."""
    print("\n=== Example 5: Round-Trip Validation ===\n")
    
    data = {
        "schema_version": "1.0.0",
        "presentation_id": str(uuid4()),
        "total_slides": 1,
        "slides": [
            {
                "slide_id": str(uuid4()),
                "slide_number": 1,
                "type": "title",
                "title": "Test",
                "content": {},
                "visual_hint": "centered",
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25
                },
                "metadata": {
                    "generated_at": "2024-01-01T00:00:00",
                    "provider_used": "test",
                    "quality_score": 8.5
                }
            }
        ]
    }
    
    # Test round-trip property
    is_consistent = validation_agent.validate_round_trip(data)
    
    print(f"Round-trip consistent: {is_consistent}")
    
    if is_consistent:
        print("✓ parse(format(parse(x))) == parse(x)")
    else:
        print("✗ Round-trip property violated")


if __name__ == "__main__":
    print("=" * 60)
    print("Validation Agent Examples")
    print("=" * 60)
    
    example_1_valid_slide_json()
    example_2_auto_correction()
    example_3_content_constraints()
    example_4_validation_errors()
    example_5_round_trip()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
