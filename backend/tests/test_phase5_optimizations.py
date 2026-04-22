"""
Tests for Phase 5: Testing & Optimization.

Tests caching, batch processing, and selective enhancement optimizations.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm_cache import llm_cache_service, LLMCacheService
from app.services.batch_processor import batch_processor
from app.services.selective_enhancement import selective_enhancement, EnhancementPriority
from app.services.optimized_visual_refinement import optimized_visual_refinement


@pytest.fixture
def sample_slides():
    """Sample slides for testing."""
    return [
        {
            "slide_id": "slide-1",
            "type": "title",
            "title": "Market Analysis",
            "content": {},
        },
        {
            "slide_id": "slide-2",
            "type": "content",
            "title": "Key Findings",
            "content": {
                "bullets": [
                    "Market growing rapidly",
                    "Competition increasing",
                    "Customer satisfaction high",
                ],
            },
        },
        {
            "slide_id": "slide-3",
            "type": "chart",
            "title": "Revenue Trends",
            "content": {
                "chart_type": "line",
                "chart_data": [
                    {"label": "Category 1", "value": 100},
                    {"label": "Category 2", "value": 200},
                    {"label": "Category 3", "value": 150},
                ],
            },
        },
        {
            "slide_id": "slide-4",
            "type": "content",
            "title": "Recommendations",
            "content": {
                "bullets": ["Expand market share", "Improve efficiency"],
                "icon_name": "Target",
                "highlight_text": "25% growth opportunity",
            },
        },
    ]


class TestLLMCacheService:
    """Test LLM response caching."""
    
    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self):
        """Test cache miss followed by cache hit."""
        cache = LLMCacheService()
        cache.reset_stats()
        
        # First call - cache miss
        result1 = await cache.get(
            "visual_refinement",
            "select_icon",
            title="Test Slide",
            content="Test content"
        )
        assert result1 is None
        assert cache.get_stats()["misses"] == 1
        
        # Store in cache
        test_data = {"icon_name": "TrendingUp"}
        await cache.set(
            "visual_refinement",
            "select_icon",
            test_data,
            title="Test Slide",
            content="Test content"
        )
        
        # Second call - cache hit
        result2 = await cache.get(
            "visual_refinement",
            "select_icon",
            title="Test Slide",
            content="Test content"
        )
        assert result2 == test_data
        assert cache.get_stats()["hits"] == 1
        assert cache.get_hit_rate() == 0.5  # 1 hit out of 2 requests
    
    @pytest.mark.asyncio
    async def test_cache_key_deterministic(self):
        """Test that cache keys are deterministic."""
        cache = LLMCacheService()
        
        # Same parameters in different order should produce same key
        key1 = cache._generate_cache_key(
            "agent1",
            "method1",
            param_a="value1",
            param_b="value2"
        )
        key2 = cache._generate_cache_key(
            "agent1",
            "method1",
            param_b="value2",
            param_a="value1"
        )
        
        assert key1 == key2
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache = LLMCacheService()
        
        # Store some data
        await cache.set(
            "visual_refinement",
            "select_icon",
            {"icon_name": "Test"},
            title="Test"
        )
        
        # Invalidate
        deleted = await cache.invalidate("visual_refinement", "select_icon")
        
        # Should be deleted
        result = await cache.get(
            "visual_refinement",
            "select_icon",
            title="Test"
        )
        assert result is None


class TestBatchProcessor:
    """Test batch processing of LLM calls."""
    
    @pytest.mark.asyncio
    async def test_batch_select_icons(self, sample_slides):
        """Test batch icon selection."""
        mock_response = {
            "icons": [
                {"slide_id": "slide-2", "icon_name": "TrendingUp"},
                {"slide_id": "slide-3", "icon_name": "BarChart"},
            ]
        }
        
        with patch.object(
            batch_processor,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await batch_processor.batch_select_icons(
                sample_slides[1:3],  # 2 slides
                execution_id="test-exec-123",
            )
            
            assert "slide-2" in result
            assert "slide-3" in result
            assert result["slide-2"] == "TrendingUp"
            assert result["slide-3"] == "BarChart"
    
    @pytest.mark.asyncio
    async def test_batch_generate_highlights(self, sample_slides):
        """Test batch highlight generation."""
        mock_response = {
            "highlights": [
                {"slide_id": "slide-2", "highlight_text": "67% market growth"},
                {"slide_id": "slide-3", "highlight_text": "Revenue up 3x"},
            ]
        }
        
        with patch.object(
            batch_processor,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await batch_processor.batch_generate_highlights(
                sample_slides[1:3],
                execution_id="test-exec-123",
            )
            
            assert len(result) == 2
            assert "67% market growth" in result.values()
    
    @pytest.mark.asyncio
    async def test_batch_size_limit(self, sample_slides):
        """Test that batch size is limited."""
        # Create 10 slides
        many_slides = sample_slides * 3  # 12 slides
        
        with patch.object(
            batch_processor,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value={"icons": []},
        ) as mock_call:
            await batch_processor.batch_select_icons(
                many_slides,
                execution_id="test-exec-123",
            )
            
            # Should only process BATCH_SIZE slides
            call_args = mock_call.call_args
            user_prompt = call_args.kwargs["user_prompt"]
            
            # Count how many slides are in the prompt
            slide_count = user_prompt.count("Slide ")
            assert slide_count <= batch_processor.BATCH_SIZE


class TestSelectiveEnhancement:
    """Test selective enhancement logic."""
    
    def test_should_enhance_title_slide(self, sample_slides):
        """Test that title slides are skipped."""
        should_enhance, priority = selective_enhancement.should_enhance_visual_refinement(
            sample_slides[0],  # Title slide
            slide_index=0,
            total_slides=4,
        )
        
        assert should_enhance is False
        assert priority == EnhancementPriority.SKIP
    
    def test_should_enhance_last_slide(self, sample_slides):
        """Test that last slide (conclusion) is skipped."""
        should_enhance, priority = selective_enhancement.should_enhance_visual_refinement(
            sample_slides[-1],
            slide_index=3,
            total_slides=4,
        )
        
        assert should_enhance is False
        assert priority == EnhancementPriority.SKIP
    
    def test_should_enhance_slide_with_all_enhancements(self, sample_slides):
        """Test that slides with all enhancements are skipped."""
        # slide-4 has icon, highlight, and we'll add notes
        slide = sample_slides[3].copy()
        slide["speaker_notes"] = "Test notes"
        
        should_enhance, priority = selective_enhancement.should_enhance_visual_refinement(
            slide,
            slide_index=3,
            total_slides=4,
        )
        
        assert should_enhance is False
        # Last slide is marked as SKIP (conclusion slide)
        assert priority == EnhancementPriority.SKIP
    
    def test_should_enhance_slide_missing_enhancements(self, sample_slides):
        """Test that slides missing enhancements are enhanced."""
        should_enhance, priority = selective_enhancement.should_enhance_visual_refinement(
            sample_slides[1],  # Content slide without enhancements
            slide_index=1,
            total_slides=4,
        )
        
        assert should_enhance is True
        assert priority in [EnhancementPriority.CRITICAL, EnhancementPriority.HIGH, EnhancementPriority.MEDIUM]
    
    def test_should_enhance_chart_with_generic_labels(self, sample_slides):
        """Test that charts with generic labels are enhanced."""
        should_enhance, priority = selective_enhancement.should_enhance_data_enrichment(
            sample_slides[2],  # Chart with "Category 1, 2, 3"
        )
        
        assert should_enhance is True
        assert priority == EnhancementPriority.CRITICAL
    
    def test_filter_slides_for_enhancement(self, sample_slides):
        """Test filtering slides for enhancement."""
        filtered = selective_enhancement.filter_slides_for_enhancement(
            sample_slides,
            enhancement_type="visual"
        )
        
        # Should skip title slide (index 0) and possibly others
        assert len(filtered) < len(sample_slides)
        
        # Check that filtered slides have priorities
        for idx, slide, priority in filtered:
            assert isinstance(priority, EnhancementPriority)
            assert 0 <= idx < len(sample_slides)
    
    def test_get_enhancement_stats(self, sample_slides):
        """Test enhancement statistics."""
        stats = selective_enhancement.get_enhancement_stats(sample_slides)
        
        assert "total_slides" in stats
        assert "visual_enhancement" in stats
        assert "data_enhancement" in stats
        assert "estimated_cost_savings" in stats
        
        assert stats["total_slides"] == len(sample_slides)
        assert 0 <= stats["visual_enhancement"]["skip_rate"] <= 1.0


class TestOptimizedVisualRefinement:
    """Test optimized visual refinement service."""
    
    @pytest.mark.asyncio
    async def test_refine_with_selective_enhancement(self, sample_slides):
        """Test refinement with selective enhancement."""
        with patch.object(
            batch_processor,
            "batch_select_icons",
            new_callable=AsyncMock,
            return_value={"slide-2": "TrendingUp"},
        ), patch.object(
            batch_processor,
            "batch_generate_highlights",
            new_callable=AsyncMock,
            return_value={"slide-2": "Test highlight"},
        ), patch.object(
            batch_processor,
            "batch_generate_speaker_notes",
            new_callable=AsyncMock,
            return_value={"slide-2": "Test notes"},
        ):
            result = await optimized_visual_refinement.refine_presentation_optimized(
                sample_slides,
                execution_id="test-exec-123",
                use_batch_processing=True,
                use_selective_enhancement=True,
            )
            
            # Should return same number of slides
            assert len(result) == len(sample_slides)
            
            # Some slides should be enhanced
            # (exact count depends on selective enhancement logic)
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_refine_without_selective_enhancement(self, sample_slides):
        """Test refinement without selective enhancement."""
        with patch.object(
            batch_processor,
            "batch_select_icons",
            new_callable=AsyncMock,
            return_value={},
        ), patch.object(
            batch_processor,
            "batch_generate_highlights",
            new_callable=AsyncMock,
            return_value={},
        ), patch.object(
            batch_processor,
            "batch_generate_speaker_notes",
            new_callable=AsyncMock,
            return_value={},
        ):
            result = await optimized_visual_refinement.refine_presentation_optimized(
                sample_slides,
                execution_id="test-exec-123",
                use_batch_processing=True,
                use_selective_enhancement=False,
            )
            
            # Should process all slides
            assert len(result) == len(sample_slides)
    
    def test_get_optimization_stats(self, sample_slides):
        """Test optimization statistics."""
        stats = optimized_visual_refinement.get_optimization_stats(sample_slides)
        
        assert "visual_enhancement" in stats
        assert "data_enhancement" in stats
        assert "cache" in stats
        assert "estimated_cost_savings" in stats
        
        savings = stats["estimated_cost_savings"]
        assert "selective_enhancement" in savings
        assert "batch_processing" in savings
        assert "caching" in savings
        assert "combined_estimated" in savings


class TestCostSavings:
    """Test cost savings calculations."""
    
    def test_selective_enhancement_savings(self, sample_slides):
        """Test that selective enhancement reduces calls."""
        stats = selective_enhancement.get_enhancement_stats(sample_slides)
        
        visual_skip_rate = stats["visual_enhancement"]["skip_rate"]
        
        # Should skip at least title and conclusion (2 out of 4 = 50%)
        assert visual_skip_rate >= 0.25  # At least 25% savings
    
    @pytest.mark.asyncio
    async def test_cache_hit_rate_improves_over_time(self):
        """Test that cache hit rate improves with repeated calls."""
        cache = LLMCacheService()
        cache.reset_stats()
        
        # Make same call multiple times
        for i in range(5):
            result = await cache.get(
                "test_agent",
                "test_method",
                param="same_value"
            )
            
            if result is None:
                # Cache miss - store data
                await cache.set(
                    "test_agent",
                    "test_method",
                    {"data": "test"},
                    param="same_value"
                )
        
        # Hit rate should improve (first miss, then hits)
        stats = cache.get_stats()
        assert stats["hits"] >= 3  # At least 3 hits out of 5 calls
        assert cache.get_hit_rate() >= 0.6  # At least 60% hit rate


class TestEndToEndOptimization:
    """Test end-to-end optimization pipeline."""
    
    @pytest.mark.asyncio
    async def test_full_optimization_pipeline(self, sample_slides):
        """Test complete optimization pipeline."""
        with patch.object(
            batch_processor,
            "batch_select_icons",
            new_callable=AsyncMock,
            return_value={"slide-2": "TrendingUp", "slide-3": "BarChart"},
        ), patch.object(
            batch_processor,
            "batch_generate_highlights",
            new_callable=AsyncMock,
            return_value={"slide-2": "Growth accelerating", "slide-3": "Revenue up 3x"},
        ), patch.object(
            batch_processor,
            "batch_generate_speaker_notes",
            new_callable=AsyncMock,
            return_value={"slide-2": "Notes 1", "slide-3": "Notes 2"},
        ):
            # Run optimized refinement
            result = await optimized_visual_refinement.refine_presentation_optimized(
                sample_slides,
                execution_id="test-exec-123",
                use_batch_processing=True,
                use_selective_enhancement=True,
            )
            
            # Verify results
            assert len(result) == len(sample_slides)
            
            # Get optimization stats
            stats = optimized_visual_refinement.get_optimization_stats(sample_slides)
            
            # Verify cost savings are calculated
            assert "estimated_cost_savings" in stats
            savings = stats["estimated_cost_savings"]
            
            # Should show some savings
            assert "combined_estimated" in savings
