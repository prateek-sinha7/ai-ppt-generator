"""
Research Agent - Deep topic analysis and industry-specific insight generation.

This agent analyzes the presentation topic and generates:
- 6-10 logical sections appropriate for the detected industry
- Domain-specific insights, risks, and opportunities
- Business terminology and context for enterprise audiences
- Research findings stored in agent_states for subsequent agent consumption

The agent implements:
- 30-second timeout with 3 retries using exponential backoff (2s base)
- Fallback to cached industry data when all retries fail
- Comprehensive error handling and state management
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.services.llm_provider import provider_factory
from app.db.session import get_db
from app.db.models import AgentState, PipelineExecution


logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Cached Industry Data (Fallback)
# ---------------------------------------------------------------------------

CACHED_INDUSTRY_DATA = {
    "healthcare": {
        "sections": [
            "Clinical Overview",
            "Patient Impact",
            "Regulatory Compliance",
            "Treatment Protocols",
            "Risk Assessment",
            "Quality Metrics",
            "Implementation Strategy",
            "Outcomes & Evidence"
        ],
        "insights": {
            "risks": [
                "Patient safety concerns",
                "Regulatory compliance challenges",
                "Data privacy and HIPAA requirements",
                "Clinical trial delays"
            ],
            "opportunities": [
                "Improved patient outcomes",
                "Cost reduction through efficiency",
                "Enhanced care coordination",
                "Digital health innovation"
            ],
            "terminology": [
                "EHR", "clinical pathways", "patient-centered care",
                "evidence-based medicine", "quality indicators", "adverse events"
            ]
        }
    },
    "insurance": {
        "sections": [
            "Market Overview",
            "Risk Assessment",
            "Underwriting Analysis",
            "Claims Trends",
            "Actuarial Insights",
            "Regulatory Environment",
            "Strategic Recommendations",
            "Financial Projections"
        ],
        "insights": {
            "risks": [
                "Adverse selection",
                "Claims volatility",
                "Regulatory changes",
                "Market competition"
            ],
            "opportunities": [
                "Product innovation",
                "Risk pool optimization",
                "Digital transformation",
                "Customer retention"
            ],
            "terminology": [
                "loss ratio", "combined ratio", "premium adequacy",
                "reinsurance", "underwriting profit", "actuarial reserves"
            ]
        }
    },
    "finance": {
        "sections": [
            "Market Analysis",
            "Financial Performance",
            "Investment Strategy",
            "Risk Management",
            "Portfolio Optimization",
            "Regulatory Compliance",
            "Strategic Initiatives",
            "Future Outlook"
        ],
        "insights": {
            "risks": [
                "Market volatility",
                "Credit risk exposure",
                "Regulatory compliance",
                "Liquidity constraints"
            ],
            "opportunities": [
                "Portfolio diversification",
                "Digital banking innovation",
                "ESG investment growth",
                "Fintech partnerships"
            ],
            "terminology": [
                "ROE", "capital adequacy", "asset allocation",
                "risk-adjusted returns", "liquidity ratio", "credit spread"
            ]
        }
    },
    "technology": {
        "sections": [
            "Technology Landscape",
            "Product Strategy",
            "Market Opportunity",
            "Technical Architecture",
            "Implementation Roadmap",
            "Security & Compliance",
            "Performance Metrics",
            "Future Innovation"
        ],
        "insights": {
            "risks": [
                "Technical debt accumulation",
                "Cybersecurity threats",
                "Scalability challenges",
                "Talent acquisition"
            ],
            "opportunities": [
                "Cloud migration benefits",
                "AI/ML integration",
                "API monetization",
                "Platform expansion"
            ],
            "terminology": [
                "microservices", "API gateway", "DevOps",
                "CI/CD", "cloud-native", "containerization"
            ]
        }
    },
    "retail": {
        "sections": [
            "Market Trends",
            "Consumer Behavior",
            "Sales Performance",
            "Inventory Management",
            "Omnichannel Strategy",
            "Customer Experience",
            "Competitive Analysis",
            "Growth Opportunities"
        ],
        "insights": {
            "risks": [
                "Changing consumer preferences",
                "Supply chain disruptions",
                "E-commerce competition",
                "Margin pressure"
            ],
            "opportunities": [
                "Personalization at scale",
                "Omnichannel integration",
                "Loyalty program enhancement",
                "Sustainable practices"
            ],
            "terminology": [
                "SKU optimization", "conversion rate", "basket size",
                "customer lifetime value", "inventory turnover", "same-store sales"
            ]
        }
    },
    "default": {
        "sections": [
            "Executive Summary",
            "Current Situation",
            "Analysis & Insights",
            "Key Findings",
            "Strategic Options",
            "Recommendations",
            "Implementation Plan",
            "Next Steps"
        ],
        "insights": {
            "risks": [
                "Market uncertainty",
                "Competitive pressure",
                "Resource constraints",
                "Execution challenges"
            ],
            "opportunities": [
                "Market expansion",
                "Operational efficiency",
                "Innovation potential",
                "Strategic partnerships"
            ],
            "terminology": [
                "strategic initiative", "value proposition", "competitive advantage",
                "market positioning", "operational excellence", "stakeholder alignment"
            ]
        }
    }
}


# ---------------------------------------------------------------------------
# Pydantic Models for LLM Output
# ---------------------------------------------------------------------------

class ResearchInsights(BaseModel):
    """Structured insights from research analysis"""
    risks: List[str] = Field(description="Business risks and challenges", min_items=3, max_items=6)
    opportunities: List[str] = Field(description="Business opportunities and benefits", min_items=3, max_items=6)
    terminology: List[str] = Field(description="Domain-specific terminology", min_items=5, max_items=10)


class ResearchOutput(BaseModel):
    """Structured output from Research Agent LLM call"""
    sections: List[str] = Field(description="6-10 logical sections for the presentation", min_items=6, max_items=10)
    insights: ResearchInsights = Field(description="Business insights, risks, and opportunities")
    context_summary: str = Field(description="Brief summary of the research context (2-3 sentences)")


@dataclass
class ResearchFindings:
    """Complete research findings output"""
    topic: str
    industry: str
    sections: List[str]
    risks: List[str]
    opportunities: List[str]
    terminology: List[str]
    context_summary: str
    method: str  # "llm" or "cached"
    execution_id: str
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return asdict(self)


class ResearchAgent:
    """
    Research Agent - Deep topic analysis and industry-specific insight generation.
    
    Key responsibilities:
    1. Break topic into 6-10 logical sections
    2. Generate domain-specific insights (risks, opportunities, terminology)
    3. Implement 30-second timeout with 3 retries (2s exponential backoff)
    4. Fallback to cached industry data on failure
    5. Store findings in agent_states for subsequent agents
    """
    
    # Timeout and retry configuration
    TIMEOUT_SECONDS = 30
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 2.0
    
    def __init__(self):
        """Initialize the Research Agent"""
        pass
    
    def _get_cached_data(self, industry: str) -> Dict[str, Any]:
        """
        Get cached industry data for fallback.
        
        Args:
            industry: Detected industry
            
        Returns:
            Cached industry data dictionary
        """
        # Normalize industry name
        industry_lower = industry.lower()
        
        # Try exact match
        if industry_lower in CACHED_INDUSTRY_DATA:
            return CACHED_INDUSTRY_DATA[industry_lower]
        
        # Try partial match
        for cached_industry, data in CACHED_INDUSTRY_DATA.items():
            if cached_industry in industry_lower or industry_lower in cached_industry:
                logger.info(
                    "using_partial_match_cached_data",
                    industry=industry,
                    matched=cached_industry,
                )
                return data
        
        # Use default
        logger.info(
            "using_default_cached_data",
            industry=industry,
        )
        return CACHED_INDUSTRY_DATA["default"]
    
    def _build_research_prompt(
        self,
        topic: str,
        industry: str,
        sub_sector: Optional[str] = None,
        target_audience: str = "general",
    ) -> tuple[str, str]:
        """
        Build system and user prompts for research analysis.
        
        Args:
            topic: Presentation topic
            industry: Detected industry
            sub_sector: Optional sub-sector
            target_audience: Target audience (executives, analysts, technical, general)
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Audience-specific guidance
        audience_guidance = {
            "executives": "Focus on strategic implications, ROI, and high-level business impact.",
            "analysts": "Emphasize data-driven insights, metrics, and analytical frameworks.",
            "technical": "Include technical details, implementation considerations, and architecture.",
            "general": "Balance business and technical perspectives for a broad audience.",
        }
        
        audience_note = audience_guidance.get(target_audience, audience_guidance["general"])
        
        system_prompt = f"""You are an expert business research analyst specializing in {industry}.

Your task is to analyze a presentation topic and generate comprehensive research findings including:
1. 6-10 logical sections that structure the presentation flow
2. Business risks and challenges (3-6 items)
3. Business opportunities and benefits (3-6 items)
4. Domain-specific terminology (5-10 terms)
5. Brief context summary (2-3 sentences)

Target audience: {target_audience}
{audience_note}

Return your analysis as JSON with the following structure:
{{
  "sections": ["Section 1", "Section 2", ...],
  "insights": {{
    "risks": ["Risk 1", "Risk 2", ...],
    "opportunities": ["Opportunity 1", "Opportunity 2", ...],
    "terminology": ["Term 1", "Term 2", ...]
  }},
  "context_summary": "Brief summary of the research context"
}}

Ensure sections are:
- Logical and flow naturally
- Appropriate for {industry} presentations
- Suitable for consulting-style storytelling
- Between 6-10 sections total"""
        
        sub_sector_note = f" (specifically {sub_sector})" if sub_sector else ""
        
        user_prompt = f"""Analyze the following presentation topic for the {industry} industry{sub_sector_note}:

Topic: {topic}

Provide comprehensive research findings including logical sections, business insights, risks, opportunities, and domain-specific terminology.

Return your analysis as JSON."""
        
        return system_prompt, user_prompt
    
    async def _call_llm_with_timeout(
        self,
        topic: str,
        industry: str,
        execution_id: str,
        sub_sector: Optional[str] = None,
        target_audience: str = "general",
    ) -> ResearchOutput:
        """
        Call LLM with timeout and retry logic.
        
        Args:
            topic: Presentation topic
            industry: Detected industry
            execution_id: Execution ID for tracing
            sub_sector: Optional sub-sector
            target_audience: Target audience
            
        Returns:
            ResearchOutput from LLM
            
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
            Exception: If LLM call fails
        """
        system_prompt, user_prompt = self._build_research_prompt(
            topic, industry, sub_sector, target_audience
        )
        
        async def call_llm(client: BaseChatModel):
            parser = JsonOutputParser(pydantic_object=ResearchOutput)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            
            response = await client.ainvoke(messages)
            parsed = parser.parse(response.content)
            
            return parsed
        
        # Call with timeout
        result = await asyncio.wait_for(
            provider_factory.call_with_failover(
                call_llm,
                execution_id=execution_id,
                industry=industry,
            ),
            timeout=self.TIMEOUT_SECONDS,
        )
        
        return result
    
    async def analyze_topic(
        self,
        topic: str,
        industry: str,
        execution_id: str,
        sub_sector: Optional[str] = None,
        target_audience: str = "general",
    ) -> ResearchFindings:
        """
        Main research analysis method with retry and fallback logic.
        
        Implements:
        - 30-second timeout per attempt
        - 3 retries with exponential backoff (2s base)
        - Fallback to cached industry data on failure
        
        Args:
            topic: Presentation topic
            industry: Detected industry
            execution_id: Execution ID for tracing
            sub_sector: Optional sub-sector
            target_audience: Target audience
            
        Returns:
            ResearchFindings with complete analysis
        """
        logger.info(
            "research_analysis_started",
            topic=topic[:100],
            industry=industry,
            execution_id=execution_id,
        )
        
        start_time = datetime.utcnow()
        
        # Try LLM with retries
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(
                    "research_llm_attempt",
                    attempt=attempt + 1,
                    max_retries=self.MAX_RETRIES,
                    execution_id=execution_id,
                )
                
                result = await self._call_llm_with_timeout(
                    topic=topic,
                    industry=industry,
                    execution_id=execution_id,
                    sub_sector=sub_sector,
                    target_audience=target_audience,
                )
                
                # Success - create findings
                findings = ResearchFindings(
                    topic=topic,
                    industry=industry,
                    sections=result["sections"],
                    risks=result["insights"]["risks"],
                    opportunities=result["insights"]["opportunities"],
                    terminology=result["insights"]["terminology"],
                    context_summary=result["context_summary"],
                    method="llm",
                    execution_id=execution_id,
                    created_at=datetime.utcnow().isoformat(),
                )
                
                elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                logger.info(
                    "research_analysis_completed_llm",
                    sections_count=len(findings.sections),
                    risks_count=len(findings.risks),
                    opportunities_count=len(findings.opportunities),
                    elapsed_ms=elapsed_ms,
                    execution_id=execution_id,
                )
                
                return findings
                
            except asyncio.TimeoutError:
                logger.warning(
                    "research_llm_timeout",
                    attempt=attempt + 1,
                    timeout_seconds=self.TIMEOUT_SECONDS,
                    execution_id=execution_id,
                )
                
                # Exponential backoff before retry
                if attempt < self.MAX_RETRIES - 1:
                    backoff_seconds = self.BASE_BACKOFF_SECONDS * (2 ** attempt)
                    logger.info(
                        "research_retry_backoff",
                        backoff_seconds=backoff_seconds,
                        next_attempt=attempt + 2,
                    )
                    await asyncio.sleep(backoff_seconds)
                
            except Exception as e:
                logger.error(
                    "research_llm_error",
                    attempt=attempt + 1,
                    error=str(e),
                    execution_id=execution_id,
                )
                
                # Exponential backoff before retry
                if attempt < self.MAX_RETRIES - 1:
                    backoff_seconds = self.BASE_BACKOFF_SECONDS * (2 ** attempt)
                    logger.info(
                        "research_retry_backoff",
                        backoff_seconds=backoff_seconds,
                        next_attempt=attempt + 2,
                    )
                    await asyncio.sleep(backoff_seconds)
        
        # All retries failed - use cached data
        logger.warning(
            "research_llm_failed_using_cached_data",
            industry=industry,
            execution_id=execution_id,
        )
        
        cached_data = self._get_cached_data(industry)
        
        findings = ResearchFindings(
            topic=topic,
            industry=industry,
            sections=cached_data["sections"],
            risks=cached_data["insights"]["risks"],
            opportunities=cached_data["insights"]["opportunities"],
            terminology=cached_data["insights"]["terminology"],
            context_summary=f"Cached research data for {industry} industry. Topic: {topic[:100]}",
            method="cached",
            execution_id=execution_id,
            created_at=datetime.utcnow().isoformat(),
        )
        
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info(
            "research_analysis_completed_cached",
            sections_count=len(findings.sections),
            elapsed_ms=elapsed_ms,
            execution_id=execution_id,
        )
        
        return findings
    
    async def store_findings(
        self,
        findings: ResearchFindings,
        execution_id: str,
    ) -> None:
        """
        Store research findings in agent_states for subsequent agent consumption.
        
        Args:
            findings: Research findings to store
            execution_id: Pipeline execution ID
        """
        logger.info(
            "storing_research_findings",
            execution_id=execution_id,
        )
        
        try:
            async for db in get_db():
                # Find the pipeline execution
                from sqlalchemy import select
                
                stmt = select(PipelineExecution).where(
                    PipelineExecution.id == execution_id
                )
                result = await db.execute(stmt)
                execution = result.scalar_one_or_none()
                
                if not execution:
                    logger.error(
                        "pipeline_execution_not_found",
                        execution_id=execution_id,
                    )
                    return
                
                # Create agent state
                agent_state = AgentState(
                    execution_id=execution_id,
                    agent_name="research_agent",
                    state=findings.to_dict(),
                )
                
                db.add(agent_state)
                await db.commit()
                
                logger.info(
                    "research_findings_stored",
                    execution_id=execution_id,
                    agent_state_id=str(agent_state.id),
                )
                
                break  # Exit after first iteration
                
        except Exception as e:
            logger.error(
                "research_findings_storage_failed",
                execution_id=execution_id,
                error=str(e),
            )
            raise


# Global agent instance
research_agent = ResearchAgent()
