"""
Tests for Research Agent

Tests cover:
- Topic analysis with LLM
- Cached data fallback
- Timeout and retry logic
- Research findings storage
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.agents.research import (
    ResearchAgent,
    ResearchFindings,
    CACHED_INDUSTRY_DATA,
)


@pytest.fixture
def research_agent():
    """Create a Research Agent instance"""
    return ResearchAgent()


@pytest.fixture
def sample_topic():
    """Sample presentation topic"""
    return "Digital transformation strategy for healthcare providers"


@pytest.fixture
def sample_industry():
    """Sample industry"""
    return "healthcare"


@pytest.fixture
def sample_execution_id():
    """Sample execution ID"""
    return "test-execution-123"


class TestResearchAgent:
    """Test suite for Research Agent"""
    
    def test_get_cached_data_exact_match(self, research_agent):
        """Test cached data retrieval with exact industry match"""
        cached = research_agent._get_cached_data("healthcare")
        
        assert "sections" in cached
        assert "insights" in cached
        assert len(cached["sections"]) >= 6
        assert "risks" in cached["insights"]
        assert "opportunities" in cached["insights"]
        assert "terminology" in cached["insights"]
    
    def test_get_cached_data_partial_match(self, research_agent):
        """Test cached data retrieval with partial industry match"""
        cached = research_agent._get_cached_data("health care")
        
        assert "sections" in cached
        assert "insights" in cached
    
    def test_get_cached_data_default_fallback(self, research_agent):
        """Test cached data fallback to default for unknown industry"""
        cached = research_agent._get_cached_data("unknown_industry")
        
        assert cached == CACHED_INDUSTRY_DATA["default"]
        assert "sections" in cached
        assert len(cached["sections"]) >= 6
    
    def test_build_research_prompt(self, research_agent, sample_topic, sample_industry):
        """Test research prompt generation"""
        system_prompt, user_prompt = research_agent._build_research_prompt(
            topic=sample_topic,
            industry=sample_industry,
            sub_sector="clinical research",
            target_audience="executives",
        )
        
        assert sample_industry in system_prompt
        assert "executives" in system_prompt
        assert sample_topic in user_prompt
        assert "clinical research" in user_prompt
        assert "JSON" in system_prompt
    
    def test_build_research_prompt_different_audiences(self, research_agent, sample_topic, sample_industry):
        """Test prompt generation for different audiences"""
        audiences = ["executives", "analysts", "technical", "general"]
        
        for audience in audiences:
            system_prompt, user_prompt = research_agent._build_research_prompt(
                topic=sample_topic,
                industry=sample_industry,
                target_audience=audience,
            )
            
            assert audience in system_prompt
            assert sample_industry in system_prompt
    
    @pytest.mark.asyncio
    async def test_analyze_topic_cached_fallback(
        self,
        research_agent,
        sample_topic,
        sample_industry,
        sample_execution_id,
    ):
        """Test topic analysis with cached data fallback (simulating LLM failure)"""
        # Mock LLM to always fail
        with patch('app.agents.research.provider_factory.call_with_failover') as mock_llm:
            mock_llm.side_effect = Exception("LLM unavailable")
            
            findings = await research_agent.analyze_topic(
                topic=sample_topic,
                industry=sample_industry,
                execution_id=sample_execution_id,
            )
            
            # Verify findings structure
            assert isinstance(findings, ResearchFindings)
            assert findings.topic == sample_topic
            assert findings.industry == sample_industry
            assert findings.method == "cached"
            assert len(findings.sections) >= 6
            assert len(findings.sections) <= 10
            assert len(findings.risks) >= 3
            assert len(findings.opportunities) >= 3
            assert len(findings.terminology) >= 5
            assert findings.execution_id == sample_execution_id
    
    @pytest.mark.asyncio
    async def test_analyze_topic_timeout_retry(
        self,
        research_agent,
        sample_topic,
        sample_industry,
        sample_execution_id,
    ):
        """Test timeout and retry logic"""
        # Mock LLM to timeout on first 2 attempts, then succeed
        call_count = 0
        
        async def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:
                raise asyncio.TimeoutError("Timeout")
            
            # Return successful result on 3rd attempt
            return {
                "sections": [
                    "Section 1", "Section 2", "Section 3",
                    "Section 4", "Section 5", "Section 6"
                ],
                "insights": {
                    "risks": ["Risk 1", "Risk 2", "Risk 3"],
                    "opportunities": ["Opp 1", "Opp 2", "Opp 3"],
                    "terminology": ["Term 1", "Term 2", "Term 3", "Term 4", "Term 5"]
                },
                "context_summary": "Test summary"
            }
        
        with patch('app.agents.research.provider_factory.call_with_failover', new=mock_call):
            with patch('asyncio.wait_for', side_effect=lambda coro, timeout: coro):
                findings = await research_agent.analyze_topic(
                    topic=sample_topic,
                    industry=sample_industry,
                    execution_id=sample_execution_id,
                )
                
                # Should succeed on 3rd attempt
                assert findings.method == "llm"
                assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_analyze_topic_max_retries_exceeded(
        self,
        research_agent,
        sample_topic,
        sample_industry,
        sample_execution_id,
    ):
        """Test fallback to cached data after max retries"""
        # Mock LLM to always timeout
        with patch('app.agents.research.provider_factory.call_with_failover') as mock_llm:
            mock_llm.side_effect = asyncio.TimeoutError("Timeout")
            
            with patch('asyncio.sleep'):  # Skip actual sleep delays
                findings = await research_agent.analyze_topic(
                    topic=sample_topic,
                    industry=sample_industry,
                    execution_id=sample_execution_id,
                )
                
                # Should fallback to cached data
                assert findings.method == "cached"
                assert mock_llm.call_count == research_agent.MAX_RETRIES
    
    def test_research_findings_to_dict(self, sample_topic, sample_industry, sample_execution_id):
        """Test ResearchFindings serialization"""
        findings = ResearchFindings(
            topic=sample_topic,
            industry=sample_industry,
            sections=["Section 1", "Section 2", "Section 3", "Section 4", "Section 5", "Section 6"],
            risks=["Risk 1", "Risk 2", "Risk 3"],
            opportunities=["Opp 1", "Opp 2", "Opp 3"],
            terminology=["Term 1", "Term 2", "Term 3", "Term 4", "Term 5"],
            context_summary="Test summary",
            method="llm",
            execution_id=sample_execution_id,
            created_at=datetime.utcnow().isoformat(),
        )
        
        findings_dict = findings.to_dict()
        
        assert findings_dict["topic"] == sample_topic
        assert findings_dict["industry"] == sample_industry
        assert findings_dict["method"] == "llm"
        assert len(findings_dict["sections"]) == 6
        assert len(findings_dict["risks"]) == 3
        assert len(findings_dict["opportunities"]) == 3
        assert len(findings_dict["terminology"]) == 5
    
    def test_cached_industry_data_structure(self):
        """Test that all cached industry data has required structure"""
        for industry, data in CACHED_INDUSTRY_DATA.items():
            assert "sections" in data, f"{industry} missing sections"
            assert "insights" in data, f"{industry} missing insights"
            
            assert len(data["sections"]) >= 6, f"{industry} has < 6 sections"
            assert len(data["sections"]) <= 10, f"{industry} has > 10 sections"
            
            insights = data["insights"]
            assert "risks" in insights, f"{industry} missing risks"
            assert "opportunities" in insights, f"{industry} missing opportunities"
            assert "terminology" in insights, f"{industry} missing terminology"
            
            assert len(insights["risks"]) >= 3, f"{industry} has < 3 risks"
            assert len(insights["opportunities"]) >= 3, f"{industry} has < 3 opportunities"
            assert len(insights["terminology"]) >= 5, f"{industry} has < 5 terminology items"
    
    @pytest.mark.asyncio
    async def test_store_findings(
        self,
        research_agent,
        sample_topic,
        sample_industry,
        sample_execution_id,
    ):
        """Test research findings storage"""
        findings = ResearchFindings(
            topic=sample_topic,
            industry=sample_industry,
            sections=["Section 1", "Section 2", "Section 3", "Section 4", "Section 5", "Section 6"],
            risks=["Risk 1", "Risk 2", "Risk 3"],
            opportunities=["Opp 1", "Opp 2", "Opp 3"],
            terminology=["Term 1", "Term 2", "Term 3", "Term 4", "Term 5"],
            context_summary="Test summary",
            method="llm",
            execution_id=sample_execution_id,
            created_at=datetime.utcnow().isoformat(),
        )
        
        # Mock database operations
        with patch('app.agents.research.get_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value.__aiter__.return_value = [mock_db]
            
            mock_execution = MagicMock()
            mock_db.execute.return_value.scalar_one_or_none.return_value = mock_execution
            
            await research_agent.store_findings(
                findings=findings,
                execution_id=sample_execution_id,
            )
            
            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
