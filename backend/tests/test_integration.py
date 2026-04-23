"""
Integration Tests (Task 33)

Comprehensive integration and contract tests covering:
- 33.1: End-to-end pipeline integration test (topic → Slide_JSON)
- 33.2: Slide_JSON schema contract tests (all slide types, both schema versions)
- 33.3: API contract tests (all endpoints with OpenAPI validation)
- 33.4: Provider failover integration tests (mocked provider failures)
- 33.5: Visual regression snapshot tests (5 slide types × 3 themes)
- 33.6: Multi-tenant data isolation tests (no cross-tenant leakage)
- 33.7: Cost ceiling enforcement tests (max 4 LLM calls)
- 33.8: Test coverage validation (minimum 80%)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents.pipeline_orchestrator import (
    AgentName,
    PipelineContext,
    PipelineOrchestrator,
    pipeline_orchestrator,
)
from app.db.models import (
    AgentState,
    Presentation,
    PipelineExecution,
    PresentationStatus,
    ProviderUsage,
    QualityScore,
    Tenant,
    User,
)
from app.db.session import async_session_maker


# ---------------------------------------------------------------------------
# 33.1: End-to-end pipeline integration test
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    """
    End-to-end pipeline integration test: topic input → complete Slide_JSON output.
    
    Validates the full multi-agent pipeline executes successfully and produces
    valid Slide_JSON conforming to the schema.
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_execution_produces_valid_slide_json(self):
        """
        GIVEN a valid topic string
        WHEN the full pipeline executes
        THEN it produces complete Slide_JSON with all required fields
        """
        topic = "AI in Healthcare: Clinical Decision Support Systems"
        presentation_id = str(uuid.uuid4())

        # Create presentation record
        async with async_session_maker() as db:
            tenant = Tenant(name="Test Tenant")
            db.add(tenant)
            await db.flush()

            user = User(
                email="test@example.com",
                hashed_password="dummy",
                tenant_id=tenant.id,
                role="member",
            )
            db.add(user)
            await db.flush()

            presentation = Presentation(
                presentation_id=uuid.UUID(presentation_id),
                user_id=user.id,
                tenant_id=tenant.id,
                topic=topic,
                status=PresentationStatus.queued,
            )
            db.add(presentation)
            await db.commit()

        # Mock all agents to return valid data
        with patch("app.agents.industry_classifier.industry_classifier") as mock_ic, \
             patch("app.agents.storyboarding.StoryboardingAgent") as mock_sb, \
             patch("app.agents.research.research_agent") as mock_research, \
             patch("app.agents.data_enrichment.data_enrichment_agent") as mock_enrich, \
             patch("app.agents.prompt_engineering.prompt_engineering_agent") as mock_prompt, \
             patch("app.agents.validation.validation_agent") as mock_validation, \
             patch("app.agents.quality_scoring.quality_scoring_agent") as mock_quality, \
             patch("app.services.llm_provider.provider_factory") as mock_provider:

            # Mock industry classifier
            mock_ic_result = MagicMock()
            mock_ic_result.industry = "healthcare"
            mock_ic_result.confidence = 0.95
            mock_ic_result.sub_sector = "clinical decision support"
            mock_ic_result.target_audience = "executives"
            mock_ic_result.selected_template_id = None
            mock_ic_result.selected_template_name = "Healthcare Executive Briefing"
            mock_ic_result.theme = "corporate"
            mock_ic_result.compliance_context = ["HIPAA", "FDA"]
            mock_ic_result.classification_method = "semantic"
            mock_ic.classify = AsyncMock(return_value=mock_ic_result)

            # Mock storyboarding
            mock_sb_instance = MagicMock()
            mock_sb_plan = MagicMock()
            mock_sb_plan.model_dump.return_value = {
                "total_slides": 7,
                "sections": [
                    {"section_name": "Title", "slide_count": 1, "slide_types": ["title"]},
                    {"section_name": "Problem", "slide_count": 2, "slide_types": ["content", "chart"]},
                    {"section_name": "Solution", "slide_count": 2, "slide_types": ["content", "table"]},
                    {"section_name": "Conclusion", "slide_count": 2, "slide_types": ["comparison", "content"]},
                ],
            }
            mock_sb_instance.generate_presentation_plan.return_value = mock_sb_plan
            mock_sb.return_value = mock_sb_instance

            # Mock research
            mock_research_result = MagicMock()
            mock_research_result.to_dict.return_value = {
                "sections": [
                    {"title": "Clinical AI Overview", "insights": ["AI improves diagnosis accuracy"]},
                    {"title": "Market Analysis", "insights": ["$5B market by 2025"]},
                ],
                "risks": ["Data privacy concerns", "Regulatory compliance"],
                "opportunities": ["Improved patient outcomes", "Cost reduction"],
            }
            mock_research.analyze_topic = AsyncMock(return_value=mock_research_result)

            # Mock data enrichment
            mock_enrich_result = MagicMock()
            mock_enrich_result.to_dict.return_value = {
                "datasets": [
                    {
                        "chart_type": "bar",
                        "data": [{"label": "2023", "value": 3.2}, {"label": "2024", "value": 4.1}],
                    }
                ],
                "metrics": {"accuracy_improvement": "15%", "cost_reduction": "20%"},
            }
            mock_enrich.enrich_data = AsyncMock(return_value=mock_enrich_result)

            # Mock prompt engineering
            mock_prompt_result = MagicMock()
            mock_prompt_result.to_dict.return_value = {
                "system_prompt": "You are a presentation expert...",
                "user_prompt": "Generate slides about AI in Healthcare...",
            }
            mock_prompt_result.prompt_id = str(uuid.uuid4())
            mock_prompt_result.version = "1.0.0"
            mock_prompt_result.metadata = {}
            mock_prompt.generate_prompt.return_value = mock_prompt_result

            # Mock LLM provider
            mock_llm_response = MagicMock()
            mock_llm_response.content = json.dumps({
                "schema_version": "1.0.0",
                "presentation_id": presentation_id,
                "total_slides": 7,
                "slides": [
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 1,
                        "type": "title",
                        "title": "AI in Healthcare",
                        "content": {"subtitle": "Clinical Decision Support Systems"},
                        "visual_hint": "centered",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.5},
                    },
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 2,
                        "type": "content",
                        "title": "The Challenge",
                        "content": {"bullets": ["Complex diagnoses", "Time constraints", "Data overload", "Error rates"]},
                        "visual_hint": "bullet-left",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.5},
                    },
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 3,
                        "type": "chart",
                        "title": "Market Growth",
                        "content": {
                            "chart_data": {"labels": ["2023", "2024", "2025"], "values": [3.2, 4.1, 5.0]},
                            "chart_type": "bar",
                        },
                        "visual_hint": "split-chart-right",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.5},
                    },
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 4,
                        "type": "content",
                        "title": "AI Solution",
                        "content": {"bullets": ["Real-time analysis", "Pattern recognition", "Decision support", "Outcome prediction"]},
                        "visual_hint": "bullet-left",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.5},
                    },
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 5,
                        "type": "table",
                        "title": "Performance Metrics",
                        "content": {
                            "table_data": {
                                "headers": ["Metric", "Before AI", "After AI"],
                                "rows": [
                                    ["Accuracy", "85%", "95%"],
                                    ["Time", "45 min", "15 min"],
                                ],
                            }
                        },
                        "visual_hint": "split-table-left",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.5},
                    },
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 6,
                        "type": "comparison",
                        "title": "Traditional vs AI",
                        "content": {
                            "comparison_data": {
                                "left": {"title": "Traditional", "points": ["Manual review", "Slow process"]},
                                "right": {"title": "AI-Powered", "points": ["Automated analysis", "Real-time results"]},
                            }
                        },
                        "visual_hint": "two-column",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.5},
                    },
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 7,
                        "type": "content",
                        "title": "Next Steps",
                        "content": {"bullets": ["Pilot program", "Training", "Integration", "Evaluation"]},
                        "visual_hint": "bullet-left",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.5},
                    },
                ],
            })

            async def mock_llm_call(func):
                return await func(AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)))

            mock_provider.call_with_failover = AsyncMock(side_effect=mock_llm_call)
            mock_provider.primary_provider = MagicMock(value="claude")

            # Mock validation
            mock_validation_result = MagicMock()
            mock_validation_result.corrected_data = json.loads(mock_llm_response.content)
            mock_validation.validate.return_value = mock_validation_result

            # Mock quality scoring
            mock_quality_result = MagicMock()
            mock_quality_result.to_dict.return_value = {
                "composite_score": 8.7,
                "content_depth": 8.5,
                "visual_appeal": 9.0,
                "structure_coherence": 8.8,
                "data_accuracy": 8.5,
                "clarity": 8.7,
                "recommendations": [],
            }
            mock_quality_result.composite_score = 8.7
            mock_quality_result.content_depth = 8.5
            mock_quality_result.visual_appeal = 9.0
            mock_quality_result.structure_coherence = 8.8
            mock_quality_result.data_accuracy = 8.5
            mock_quality_result.clarity = 8.7
            mock_quality_result.recommendations = []
            mock_quality_result.requires_feedback_loop = False
            mock_quality.score_presentation.return_value = mock_quality_result

            # Execute pipeline
            orchestrator = PipelineOrchestrator()
            context = await orchestrator.run(
                presentation_id=presentation_id,
                topic=topic,
                resume_from_checkpoint=False,
            )

        # Verify pipeline completed successfully
        assert context.failed_agent is None
        assert context.error_message is None
        assert len(context.completed_agents) == 8  # All 8 agents

        # Verify Slide_JSON structure
        assert context.validated_slides is not None
        slides_data = context.validated_slides
        assert slides_data["schema_version"] == "1.0.0"
        assert slides_data["total_slides"] == 7
        assert len(slides_data["slides"]) == 7

        # Verify all slide types are present
        slide_types = {slide["type"] for slide in slides_data["slides"]}
        assert "title" in slide_types
        assert "content" in slide_types
        assert "chart" in slide_types
        assert "table" in slide_types
        assert "comparison" in slide_types

        # Verify each slide has required fields
        for slide in slides_data["slides"]:
            assert "slide_id" in slide
            assert "slide_number" in slide
            assert "type" in slide
            assert "title" in slide
            assert "content" in slide
            assert "visual_hint" in slide
            assert "layout_constraints" in slide
            assert "metadata" in slide

        # Verify detected context
        assert context.detected_context is not None
        assert context.detected_context["industry"] == "healthcare"
        assert context.detected_context["confidence"] == 0.95

        # Verify quality score
        assert context.quality_result is not None
        assert context.quality_result["composite_score"] >= 8.0

        # Verify database persistence
        async with async_session_maker() as db:
            stmt = select(Presentation).where(Presentation.presentation_id == uuid.UUID(presentation_id))
            result = await db.execute(stmt)
            pres = result.scalar_one()

            assert pres.status == PresentationStatus.completed
            assert pres.total_slides == 7
            assert pres.slides is not None
            assert len(pres.slides) == 7
            assert pres.detected_industry == "healthcare"
            assert pres.quality_score >= 8.0

    @pytest.mark.asyncio
    async def test_pipeline_persists_state_at_each_agent_transition(self):
        """
        GIVEN a pipeline execution
        WHEN each agent completes
        THEN its state is persisted atomically to agent_states table
        """
        topic = "Blockchain in Supply Chain Management"
        presentation_id = str(uuid.uuid4())

        async with async_session_maker() as db:
            tenant = Tenant(name="Test Tenant")
            db.add(tenant)
            await db.flush()

            user = User(
                email="test2@example.com",
                hashed_password="dummy",
                tenant_id=tenant.id,
                role="member",
            )
            db.add(user)
            await db.flush()

            presentation = Presentation(
                presentation_id=uuid.UUID(presentation_id),
                user_id=user.id,
                tenant_id=tenant.id,
                topic=topic,
                status=PresentationStatus.queued,
            )
            db.add(presentation)
            await db.commit()

        # Mock agents with minimal valid responses
        with patch("app.agents.industry_classifier.industry_classifier") as mock_ic, \
             patch("app.agents.storyboarding.StoryboardingAgent") as mock_sb, \
             patch("app.agents.research.research_agent") as mock_research, \
             patch("app.agents.data_enrichment.data_enrichment_agent") as mock_enrich, \
             patch("app.agents.prompt_engineering.prompt_engineering_agent") as mock_prompt, \
             patch("app.agents.validation.validation_agent") as mock_validation, \
             patch("app.agents.quality_scoring.quality_scoring_agent") as mock_quality, \
             patch("app.services.llm_provider.provider_factory") as mock_provider:

            # Setup minimal mocks
            mock_ic_result = MagicMock()
            mock_ic_result.industry = "technology"
            mock_ic_result.confidence = 0.90
            mock_ic_result.sub_sector = "blockchain"
            mock_ic_result.target_audience = "technical"
            mock_ic_result.selected_template_id = None
            mock_ic_result.selected_template_name = "Technology Briefing"
            mock_ic_result.theme = "dark_modern"
            mock_ic_result.compliance_context = []
            mock_ic_result.classification_method = "keyword"
            mock_ic.classify = AsyncMock(return_value=mock_ic_result)

            mock_sb_instance = MagicMock()
            mock_sb_plan = MagicMock()
            mock_sb_plan.model_dump.return_value = {"total_slides": 5, "sections": []}
            mock_sb_instance.generate_presentation_plan.return_value = mock_sb_plan
            mock_sb.return_value = mock_sb_instance

            mock_research_result = MagicMock()
            mock_research_result.to_dict.return_value = {"sections": [], "risks": [], "opportunities": []}
            mock_research.analyze_topic = AsyncMock(return_value=mock_research_result)

            mock_enrich_result = MagicMock()
            mock_enrich_result.to_dict.return_value = {"datasets": [], "metrics": {}}
            mock_enrich.enrich_data = AsyncMock(return_value=mock_enrich_result)

            mock_prompt_result = MagicMock()
            mock_prompt_result.to_dict.return_value = {"system_prompt": "test", "user_prompt": "test"}
            mock_prompt_result.prompt_id = str(uuid.uuid4())
            mock_prompt_result.version = "1.0.0"
            mock_prompt_result.metadata = {}
            mock_prompt.generate_prompt.return_value = mock_prompt_result

            mock_llm_response = MagicMock()
            mock_llm_response.content = json.dumps({
                "schema_version": "1.0.0",
                "presentation_id": presentation_id,
                "total_slides": 5,
                "slides": [
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": i + 1,
                        "type": "content",
                        "title": f"Slide {i + 1}",
                        "content": {"bullets": ["Point 1", "Point 2"]},
                        "visual_hint": "bullet-left",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.0},
                    }
                    for i in range(5)
                ],
            })

            async def mock_llm_call(func):
                return await func(AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)))

            mock_provider.call_with_failover = AsyncMock(side_effect=mock_llm_call)
            mock_provider.primary_provider = MagicMock(value="claude")

            mock_validation_result = MagicMock()
            mock_validation_result.corrected_data = json.loads(mock_llm_response.content)
            mock_validation.validate.return_value = mock_validation_result

            mock_quality_result = MagicMock()
            mock_quality_result.to_dict.return_value = {
                "composite_score": 8.5,
                "content_depth": 8.0,
                "visual_appeal": 8.5,
                "structure_coherence": 8.5,
                "data_accuracy": 8.5,
                "clarity": 9.0,
                "recommendations": [],
            }
            mock_quality_result.composite_score = 8.5
            mock_quality_result.content_depth = 8.0
            mock_quality_result.visual_appeal = 8.5
            mock_quality_result.structure_coherence = 8.5
            mock_quality_result.data_accuracy = 8.5
            mock_quality_result.clarity = 9.0
            mock_quality_result.recommendations = []
            mock_quality_result.requires_feedback_loop = False
            mock_quality.score_presentation.return_value = mock_quality_result

            # Execute pipeline
            orchestrator = PipelineOrchestrator()
            context = await orchestrator.run(
                presentation_id=presentation_id,
                topic=topic,
                resume_from_checkpoint=False,
            )

        # Verify agent states were persisted
        async with async_session_maker() as db:
            stmt = select(PipelineExecution).where(PipelineExecution.presentation_id == uuid.UUID(presentation_id))
            result = await db.execute(stmt)
            execution = result.scalar_one()

            # Check agent_states for each agent
            for agent_name in AgentName:
                stmt = select(AgentState).where(
                    AgentState.execution_id == str(execution.id),
                    AgentState.agent_name == agent_name.value,
                )
                result = await db.execute(stmt)
                agent_state = result.scalar_one_or_none()

                # All agents should have persisted state
                assert agent_state is not None, f"Agent {agent_name.value} state not persisted"
                assert agent_state.state is not None
                assert isinstance(agent_state.state, dict)

    @pytest.mark.asyncio
    async def test_pipeline_completes_within_120_seconds(self):
        """
        GIVEN a standard presentation request
        WHEN the pipeline executes
        THEN it completes within 120 seconds (Req 4.5)
        """
        import time

        topic = "Digital Transformation in Retail"
        presentation_id = str(uuid.uuid4())

        async with async_session_maker() as db:
            tenant = Tenant(name="Test Tenant")
            db.add(tenant)
            await db.flush()

            user = User(
                email="test3@example.com",
                hashed_password="dummy",
                tenant_id=tenant.id,
                role="member",
            )
            db.add(user)
            await db.flush()

            presentation = Presentation(
                presentation_id=uuid.UUID(presentation_id),
                user_id=user.id,
                tenant_id=tenant.id,
                topic=topic,
                status=PresentationStatus.queued,
            )
            db.add(presentation)
            await db.commit()

        # Mock all agents with fast responses
        with patch("app.agents.industry_classifier.industry_classifier") as mock_ic, \
             patch("app.agents.storyboarding.StoryboardingAgent") as mock_sb, \
             patch("app.agents.research.research_agent") as mock_research, \
             patch("app.agents.data_enrichment.data_enrichment_agent") as mock_enrich, \
             patch("app.agents.prompt_engineering.prompt_engineering_agent") as mock_prompt, \
             patch("app.agents.validation.validation_agent") as mock_validation, \
             patch("app.agents.quality_scoring.quality_scoring_agent") as mock_quality, \
             patch("app.services.llm_provider.provider_factory") as mock_provider:

            # Setup fast mocks (all return immediately)
            mock_ic_result = MagicMock()
            mock_ic_result.industry = "retail"
            mock_ic_result.confidence = 0.88
            mock_ic_result.sub_sector = "e-commerce"
            mock_ic_result.target_audience = "executives"
            mock_ic_result.selected_template_id = None
            mock_ic_result.selected_template_name = "Retail Briefing"
            mock_ic_result.theme = "professional"
            mock_ic_result.compliance_context = []
            mock_ic_result.classification_method = "semantic"
            mock_ic.classify = AsyncMock(return_value=mock_ic_result)

            mock_sb_instance = MagicMock()
            mock_sb_plan = MagicMock()
            mock_sb_plan.model_dump.return_value = {"total_slides": 6, "sections": []}
            mock_sb_instance.generate_presentation_plan.return_value = mock_sb_plan
            mock_sb.return_value = mock_sb_instance

            mock_research_result = MagicMock()
            mock_research_result.to_dict.return_value = {"sections": [], "risks": [], "opportunities": []}
            mock_research.analyze_topic = AsyncMock(return_value=mock_research_result)

            mock_enrich_result = MagicMock()
            mock_enrich_result.to_dict.return_value = {"datasets": [], "metrics": {}}
            mock_enrich.enrich_data = AsyncMock(return_value=mock_enrich_result)

            mock_prompt_result = MagicMock()
            mock_prompt_result.to_dict.return_value = {"system_prompt": "test", "user_prompt": "test"}
            mock_prompt_result.prompt_id = str(uuid.uuid4())
            mock_prompt_result.version = "1.0.0"
            mock_prompt_result.metadata = {}
            mock_prompt.generate_prompt.return_value = mock_prompt_result

            mock_llm_response = MagicMock()
            mock_llm_response.content = json.dumps({
                "schema_version": "1.0.0",
                "presentation_id": presentation_id,
                "total_slides": 6,
                "slides": [
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": i + 1,
                        "type": "content",
                        "title": f"Slide {i + 1}",
                        "content": {"bullets": ["Point 1"]},
                        "visual_hint": "bullet-left",
                        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.0},
                    }
                    for i in range(6)
                ],
            })

            async def mock_llm_call(func):
                return await func(AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)))

            mock_provider.call_with_failover = AsyncMock(side_effect=mock_llm_call)
            mock_provider.primary_provider = MagicMock(value="claude")

            mock_validation_result = MagicMock()
            mock_validation_result.corrected_data = json.loads(mock_llm_response.content)
            mock_validation.validate.return_value = mock_validation_result

            mock_quality_result = MagicMock()
            mock_quality_result.to_dict.return_value = {
                "composite_score": 8.2,
                "content_depth": 8.0,
                "visual_appeal": 8.5,
                "structure_coherence": 8.0,
                "data_accuracy": 8.0,
                "clarity": 8.5,
                "recommendations": [],
            }
            mock_quality_result.composite_score = 8.2
            mock_quality_result.content_depth = 8.0
            mock_quality_result.visual_appeal = 8.5
            mock_quality_result.structure_coherence = 8.0
            mock_quality_result.data_accuracy = 8.0
            mock_quality_result.clarity = 8.5
            mock_quality_result.recommendations = []
            mock_quality_result.requires_feedback_loop = False
            mock_quality.score_presentation.return_value = mock_quality_result

            # Measure execution time
            start_time = time.monotonic()
            orchestrator = PipelineOrchestrator()
            context = await orchestrator.run(
                presentation_id=presentation_id,
                topic=topic,
                resume_from_checkpoint=False,
            )
            elapsed = time.monotonic() - start_time

        # Verify completion time
        assert elapsed < 120.0, f"Pipeline took {elapsed:.2f}s, exceeds 120s budget"
        assert context.failed_agent is None
        assert len(context.completed_agents) == 8


# ---------------------------------------------------------------------------
# Helper to continue in next file due to length
# ---------------------------------------------------------------------------
