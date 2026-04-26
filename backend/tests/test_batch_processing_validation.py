"""
Test batch processing validation and fallback to individual processing.

This test verifies that the batch processing system correctly detects incomplete
responses and falls back to individual processing when slides are missing
enhancements (icon_name, highlight_text, speaker_notes).
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.optimized_visual_refinement import OptimizedVisualRefinementService


class TestBatchProcessingValidation:
    """Test batch processing validation and fallback logic."""

    @pytest.fixture
    def service(self):
        """Create OptimizedVisualRefinementService instance."""
        return OptimizedVisualRefinementService()

    @pytest.fixture
    def sample_slides(self):
        """Sample slides for testing."""
        return [
            {
                "slide_id": "slide-1",
                "slide_number": 1,
                "type": "content",
                "title": "First Slide",
                "content": {"bullets": ["Point 1", "Point 2"]},
            },
            {
                "slide_id": "slide-2", 
                "slide_number": 2,
                "type": "content",
                "title": "Second Slide",
                "content": {"bullets": ["Point A", "Point B"]},
            },
        ]

    @pytest.mark.asyncio
    async def test_batch_processing_complete_response(self, service, sample_slides):
        """Test batch processing with complete responses (no fallback needed)."""
        execution_id = "test-exec-1"
        
        # Mock complete batch responses
        with patch('app.services.optimized_visual_refinement.batch_processor') as mock_processor:
            mock_processor.batch_select_icons = AsyncMock(return_value={
                "slide-1": "TrendingUp",
                "slide-2": "BarChart"
            })
            mock_processor.batch_generate_highlights = AsyncMock(return_value={
                "slide-1": "Key insight revealed",
                "slide-2": "Critical data point"
            })
            mock_processor.batch_generate_speaker_notes = AsyncMock(return_value={
                "slide-1": "This slide shows...",
                "slide-2": "Here we see..."
            })
            
            result = await service._batch_refine_slides(sample_slides, execution_id)
            
            # Verify all slides have enhancements
            assert len(result) == 2
            assert result[0]["content"]["icon_name"] == "TrendingUp"
            assert result[0]["content"]["highlight_text"] == "Key insight revealed"
            assert result[0]["speaker_notes"] == "This slide shows..."
            assert result[1]["content"]["icon_name"] == "BarChart"
            assert result[1]["content"]["highlight_text"] == "Critical data point"
            assert result[1]["speaker_notes"] == "Here we see..."

    @pytest.mark.asyncio
    async def test_batch_processing_incomplete_response_fallback(self, service, sample_slides):
        """Test batch processing with incomplete response triggers fallback."""
        execution_id = "test-exec-2"
        
        # Mock incomplete batch responses (missing slide-2 enhancements)
        with patch('app.services.optimized_visual_refinement.batch_processor') as mock_processor, \
             patch.object(service, '_individual_refine_slides') as mock_individual:
            
            # Batch responses missing slide-2
            mock_processor.batch_select_icons = AsyncMock(return_value={
                "slide-1": "TrendingUp"
                # slide-2 missing - simulates token truncation
            })
            mock_processor.batch_generate_highlights = AsyncMock(return_value={
                "slide-1": "Key insight revealed"
                # slide-2 missing - simulates token truncation
            })
            mock_processor.batch_generate_speaker_notes = AsyncMock(return_value={
                "slide-1": "This slide shows..."
                # slide-2 missing - simulates token truncation
            })
            
            # Mock individual processing fallback
            mock_individual.return_value = [
                {
                    **sample_slides[0],
                    "content": {
                        **sample_slides[0]["content"],
                        "icon_name": "FileText",
                        "highlight_text": "Individual processing result"
                    },
                    "speaker_notes": "Individual speaker notes"
                },
                {
                    **sample_slides[1],
                    "content": {
                        **sample_slides[1]["content"],
                        "icon_name": "BarChart",
                        "highlight_text": "Individual processing result 2"
                    },
                    "speaker_notes": "Individual speaker notes 2"
                }
            ]
            
            result = await service._batch_refine_slides(sample_slides, execution_id)
            
            # Verify fallback was triggered
            mock_individual.assert_called_once_with(sample_slides, execution_id)
            
            # Verify result from individual processing
            assert len(result) == 2
            assert result[0]["content"]["icon_name"] == "FileText"
            assert result[1]["content"]["icon_name"] == "BarChart"

    @pytest.mark.asyncio
    async def test_batch_processing_partial_missing_fallback(self, service, sample_slides):
        """Test fallback when only some enhancements are missing."""
        execution_id = "test-exec-3"
        
        with patch('app.services.optimized_visual_refinement.batch_processor') as mock_processor, \
             patch.object(service, '_individual_refine_slides') as mock_individual:
            
            # Icons complete, but highlights missing slide-2
            mock_processor.batch_select_icons = AsyncMock(return_value={
                "slide-1": "TrendingUp",
                "slide-2": "BarChart"
            })
            mock_processor.batch_generate_highlights = AsyncMock(return_value={
                "slide-1": "Key insight revealed"
                # slide-2 missing highlights
            })
            mock_processor.batch_generate_speaker_notes = AsyncMock(return_value={
                "slide-1": "This slide shows...",
                "slide-2": "Here we see..."
            })
            
            mock_individual.return_value = sample_slides
            
            await service._batch_refine_slides(sample_slides, execution_id)
            
            # Should still trigger fallback due to missing highlights
            mock_individual.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_size_reduced_to_two(self, service, sample_slides):
        """Test that batch size is reduced to 2 to prevent token truncation."""
        # Add more slides to test batching
        extended_slides = sample_slides + [
            {
                "slide_id": "slide-3",
                "slide_number": 3,
                "type": "content", 
                "title": "Third Slide",
                "content": {"bullets": ["Point X", "Point Y"]},
            },
            {
                "slide_id": "slide-4",
                "slide_number": 4,
                "type": "content",
                "title": "Fourth Slide", 
                "content": {"bullets": ["Point M", "Point N"]},
            },
        ]
        
        execution_id = "test-exec-4"
        
        with patch('app.services.optimized_visual_refinement.batch_processor') as mock_processor:
            # Mock responses for all slides
            mock_processor.batch_select_icons = AsyncMock(return_value={
                f"slide-{i}": f"Icon{i}" for i in range(1, 5)
            })
            mock_processor.batch_generate_highlights = AsyncMock(return_value={
                f"slide-{i}": f"Highlight {i}" for i in range(1, 5)
            })
            mock_processor.batch_generate_speaker_notes = AsyncMock(return_value={
                f"slide-{i}": f"Notes {i}" for i in range(1, 5)
            })
            
            result = await service._batch_refine_slides(extended_slides, execution_id)
            
            # Should process in 2 batches of 2 slides each
            assert mock_processor.batch_select_icons.call_count == 2
            assert mock_processor.batch_generate_highlights.call_count == 2
            assert mock_processor.batch_generate_speaker_notes.call_count == 2
            
            # Verify all slides processed
            assert len(result) == 4
            for i, slide in enumerate(result, 1):
                assert slide["content"]["icon_name"] == f"Icon{i}"
                assert slide["content"]["highlight_text"] == f"Highlight {i}"
                assert slide["speaker_notes"] == f"Notes {i}"

    @pytest.mark.asyncio
    async def test_slide_completeness_validation(self, service):
        """Test the new slide completeness validation method."""
        from app.agents.validation import validation_agent
        
        # Test slide with missing enhancements
        incomplete_data = {
            "schema_version": "1.0.0",
            "presentation_id": "test-123",
            "total_slides": 2,
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "content",
                    "title": "Test Slide",
                    "content": {
                        "bullets": ["Point 1", "Point 2"]
                        # Missing icon_name, highlight_text
                    },
                    "visual_hint": "bullet-left"
                    # Missing speaker_notes
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "chart",
                    "title": "Chart Slide",
                    "content": {
                        # Missing chart_data, icon_name, highlight_text
                    },
                    "visual_hint": "split-chart-right"
                }
            ]
        }
        
        validated_data, errors = validation_agent.validate_slide_completeness_before_rendering(incomplete_data)
        
        # Should have errors for missing enhancements
        error_fields = [error.field for error in errors]
        assert "slides[0].content.icon_name" in error_fields
        assert "slides[0].content.highlight_text" in error_fields
        assert "slides[0].speaker_notes" in error_fields
        assert "slides[1].content.chart_data" in error_fields
        
        # Should have fallback values added
        slide1 = validated_data["slides"][0]
        slide2 = validated_data["slides"][1]
        
        assert slide1["content"]["icon_name"] == "FileText"
        assert "Key insight" in slide1["content"]["highlight_text"]
        assert slide1["speaker_notes"] is not None
        
        assert slide2["content"]["chart_data"] is not None
        assert len(slide2["content"]["chart_data"]) > 0
        assert slide2["content"]["chart_type"] == "bar"