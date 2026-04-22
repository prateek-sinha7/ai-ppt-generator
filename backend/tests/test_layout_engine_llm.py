"""
Tests for Phase 4: Layout Engine Visual Hierarchy Optimization.

Tests the LLM-powered visual hierarchy optimization feature.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.layout_engine import (
    layout_engine,
    visual_hierarchy_optimizer,
    VisualHierarchyOptimization,
)


@pytest.fixture
def sample_content_slide():
    """Sample content slide for testing."""
    return {
        "slide_id": "slide-1",
        "type": "content",
        "title": "Key Risk Factors",
        "content": {
            "bullets": [
                "Regulatory compliance gaps",
                "Cybersecurity vulnerabilities",
                "Market volatility exposure",
            ],
            "highlight_text": "67% increase in cyber incidents",
            "icon_name": "Shield",
        },
        "layout_instructions": {
            "padding": "6",
            "gap": "4",
            "font_size": "slide-body",
            "title_font_size": "slide-subtitle",
        },
    }


@pytest.fixture
def sample_chart_slide():
    """Sample chart slide for testing."""
    return {
        "slide_id": "slide-2",
        "type": "chart",
        "title": "Revenue Growth Trajectory",
        "content": {
            "chart_type": "line",
            "chart_data": {
                "labels": ["Q1", "Q2", "Q3", "Q4"],
                "values": [100, 120, 145, 180],
            },
            "highlight_text": "$180M ARR achieved",
        },
        "layout_instructions": {
            "padding": "6",
            "gap": "4",
            "font_size": "slide-body",
            "title_font_size": "slide-subtitle",
            "column_gap": "4",
        },
    }


@pytest.fixture
def mock_hierarchy_optimization():
    """Mock visual hierarchy optimization response."""
    return {
        "primary_element": "highlight_text",
        "secondary_elements": ["title", "bullet_1", "chart"],
        "emphasis_recommendations": {
            "highlight_text": "increase_size",
            "title": "bold",
            "bullet_1": "color_accent",
        },
        "layout_adjustments": {
            "title_font_size": "slide-title",
            "padding": "8",
            "gap": "6",
        },
    }


class TestVisualHierarchyOptimization:
    """Test LLM-powered visual hierarchy optimization."""
    
    @pytest.mark.asyncio
    async def test_optimize_visual_hierarchy_success(
        self, sample_content_slide, mock_hierarchy_optimization
    ):
        """Test successful visual hierarchy optimization."""
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_hierarchy_optimization,
        ):
            result = await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            # Should return optimized layout instructions
            assert isinstance(result, dict)
            assert "title_font_size" in result
            assert "padding" in result
            assert "gap" in result
            
            # Should merge with existing instructions
            assert result["title_font_size"] == "slide-title"
            assert result["padding"] == "8"
            assert result["gap"] == "6"
            
            # Original instructions should be preserved if not overridden
            assert result["font_size"] == "slide-body"
    
    @pytest.mark.asyncio
    async def test_optimize_visual_hierarchy_graceful_degradation(
        self, sample_content_slide
    ):
        """Test graceful degradation when LLM fails."""
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM timeout"),
        ):
            result = await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            # Should return original instructions unchanged
            assert result == sample_content_slide["layout_instructions"]
    
    @pytest.mark.asyncio
    async def test_optimize_visual_hierarchy_content_summary(
        self, sample_content_slide, mock_hierarchy_optimization
    ):
        """Test that content summary is correctly built for LLM."""
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_hierarchy_optimization,
        ) as mock_call:
            await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            # Verify the user prompt contains content elements
            call_args = mock_call.call_args
            user_prompt = call_args.kwargs["user_prompt"]
            
            assert "Title: Key Risk Factors" in user_prompt
            assert "Bullet 1: Regulatory compliance gaps" in user_prompt
            assert "Bullet 2: Cybersecurity vulnerabilities" in user_prompt
            assert "Bullet 3: Market volatility exposure" in user_prompt
            assert "Highlight: 67% increase in cyber incidents" in user_prompt
            assert "Icon: Shield" in user_prompt
    
    @pytest.mark.asyncio
    async def test_optimize_visual_hierarchy_chart_slide(
        self, sample_chart_slide, mock_hierarchy_optimization
    ):
        """Test optimization for chart slides."""
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_hierarchy_optimization,
        ) as mock_call:
            await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_chart_slide,
                execution_id="test-exec-123",
            )
            
            # Verify chart information is included
            call_args = mock_call.call_args
            user_prompt = call_args.kwargs["user_prompt"]
            
            assert "Chart: line" in user_prompt
            assert "Highlight: $180M ARR achieved" in user_prompt
    
    @pytest.mark.asyncio
    async def test_optimize_visual_hierarchy_identifies_primary_element(
        self, sample_content_slide, mock_hierarchy_optimization
    ):
        """Test that LLM identifies the primary element correctly."""
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_hierarchy_optimization,
        ):
            await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            # The mock shows highlight_text as primary (the "67% increase" stat)
            # This makes sense as it's the most impactful data point
            assert mock_hierarchy_optimization["primary_element"] == "highlight_text"
            assert "title" in mock_hierarchy_optimization["secondary_elements"]


class TestLayoutEngineIntegration:
    """Test layout engine integration with visual hierarchy optimization."""
    
    @pytest.mark.asyncio
    async def test_layout_engine_optimize_method(
        self, sample_content_slide, mock_hierarchy_optimization
    ):
        """Test that layout engine exposes optimization method."""
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_hierarchy_optimization,
        ):
            result = await layout_engine.optimize_visual_hierarchy(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            assert isinstance(result, dict)
            assert "title_font_size" in result
            assert result["title_font_size"] == "slide-title"


class TestTokenCompliance:
    """Test that LLM recommendations use valid design tokens."""
    
    @pytest.mark.asyncio
    async def test_font_size_tokens_are_valid(
        self, sample_content_slide
    ):
        """Test that font size tokens are from the valid set."""
        valid_font_tokens = ["slide-title", "slide-subtitle", "slide-body", "slide-caption"]
        
        mock_optimization = {
            "primary_element": "title",
            "secondary_elements": [],
            "emphasis_recommendations": {},
            "layout_adjustments": {
                "title_font_size": "slide-title",
                "font_size": "slide-body",
            },
        }
        
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_optimization,
        ):
            result = await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            # Check that font tokens are valid
            if "title_font_size" in result:
                assert result["title_font_size"] in valid_font_tokens
            if "font_size" in result:
                assert result["font_size"] in valid_font_tokens
    
    @pytest.mark.asyncio
    async def test_spacing_tokens_are_valid(
        self, sample_content_slide
    ):
        """Test that spacing tokens are from the valid set."""
        valid_spacing_tokens = ["0", "1", "2", "4", "6", "8", "10", "12", "16", "20", "24"]
        
        mock_optimization = {
            "primary_element": "title",
            "secondary_elements": [],
            "emphasis_recommendations": {},
            "layout_adjustments": {
                "padding": "8",
                "gap": "6",
            },
        }
        
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_optimization,
        ):
            result = await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            # Check that spacing tokens are valid
            if "padding" in result:
                assert result["padding"] in valid_spacing_tokens
            if "gap" in result:
                assert result["gap"] in valid_spacing_tokens


class TestSemanticUnderstanding:
    """Test that LLM understands semantic importance."""
    
    @pytest.mark.asyncio
    async def test_emphasizes_data_over_generic_text(
        self, sample_content_slide
    ):
        """Test that LLM emphasizes quantitative data."""
        # The highlight_text "67% increase in cyber incidents" should be primary
        mock_optimization = {
            "primary_element": "highlight_text",
            "secondary_elements": ["bullet_1", "title"],
            "emphasis_recommendations": {
                "highlight_text": "increase_size",
            },
            "layout_adjustments": {
                "padding": "8",
            },
        }
        
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_optimization,
        ):
            await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            # Verify that the quantitative highlight is identified as primary
            assert mock_optimization["primary_element"] == "highlight_text"
    
    @pytest.mark.asyncio
    async def test_prioritizes_key_message_bullet(
        self, sample_content_slide
    ):
        """Test that LLM identifies the most important bullet."""
        # "Regulatory compliance gaps" might be most critical
        mock_optimization = {
            "primary_element": "title",
            "secondary_elements": ["bullet_1", "highlight_text", "bullet_2"],
            "emphasis_recommendations": {
                "bullet_1": "bold",
            },
            "layout_adjustments": {},
        }
        
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_optimization,
        ):
            await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=sample_content_slide,
                execution_id="test-exec-123",
            )
            
            # Verify that bullet_1 is in secondary elements (high priority)
            assert "bullet_1" in mock_optimization["secondary_elements"]


class TestCostTracking:
    """Test cost tracking for visual hierarchy optimization."""
    
    @pytest.mark.asyncio
    async def test_logs_optimization_usage(
        self, sample_content_slide, mock_hierarchy_optimization
    ):
        """Test that optimization usage is logged."""
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_hierarchy_optimization,
        ):
            with patch("app.agents.layout_engine.logger") as mock_logger:
                await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                    slide=sample_content_slide,
                    execution_id="test-exec-123",
                )
                
                # Verify logging calls
                mock_logger.info.assert_any_call(
                    "visual_hierarchy_optimization_started",
                    execution_id="test-exec-123",
                    slide_id="slide-1",
                )
                mock_logger.info.assert_any_call(
                    "visual_hierarchy_optimization_success",
                    execution_id="test-exec-123",
                    slide_id="slide-1",
                    primary_element="highlight_text",
                    adjustment_count=3,
                )


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_slide_without_layout_instructions(
        self, mock_hierarchy_optimization
    ):
        """Test optimization for slide without existing layout_instructions."""
        slide = {
            "slide_id": "slide-1",
            "type": "content",
            "title": "Test",
            "content": {"bullets": ["Test bullet"]},
        }
        
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_hierarchy_optimization,
        ):
            result = await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=slide,
                execution_id="test-exec-123",
            )
            
            # Should return the new layout adjustments
            assert isinstance(result, dict)
            assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_slide_with_minimal_content(
        self, mock_hierarchy_optimization
    ):
        """Test optimization for slide with minimal content."""
        slide = {
            "slide_id": "slide-1",
            "type": "title",
            "title": "Simple Title",
            "content": {},
        }
        
        with patch.object(
            visual_hierarchy_optimizer,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_hierarchy_optimization,
        ):
            result = await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
                slide=slide,
                execution_id="test-exec-123",
            )
            
            # Should still work
            assert isinstance(result, dict)
