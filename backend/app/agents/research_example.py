"""
Example usage of the Research Agent

This demonstrates how to use the Research Agent in the multi-agent pipeline.
"""

import asyncio
from app.agents.research import research_agent


async def example_research_analysis():
    """
    Example: Analyze a healthcare topic with the Research Agent
    """
    
    # Input parameters
    topic = "Digital transformation strategy for healthcare providers"
    industry = "healthcare"
    execution_id = "example-execution-123"
    sub_sector = "clinical research"
    target_audience = "executives"
    
    print(f"Starting research analysis...")
    print(f"Topic: {topic}")
    print(f"Industry: {industry}")
    print(f"Sub-sector: {sub_sector}")
    print(f"Audience: {target_audience}")
    print("-" * 80)
    
    # Analyze topic
    findings = await research_agent.analyze_topic(
        topic=topic,
        industry=industry,
        execution_id=execution_id,
        sub_sector=sub_sector,
        target_audience=target_audience,
    )
    
    # Display results
    print(f"\nResearch Analysis Complete!")
    print(f"Method: {findings.method}")
    print(f"\nSections ({len(findings.sections)}):")
    for i, section in enumerate(findings.sections, 1):
        print(f"  {i}. {section}")
    
    print(f"\nRisks ({len(findings.risks)}):")
    for risk in findings.risks:
        print(f"  - {risk}")
    
    print(f"\nOpportunities ({len(findings.opportunities)}):")
    for opp in findings.opportunities:
        print(f"  - {opp}")
    
    print(f"\nTerminology ({len(findings.terminology)}):")
    for term in findings.terminology:
        print(f"  - {term}")
    
    print(f"\nContext Summary:")
    print(f"  {findings.context_summary}")
    
    # Store findings (in real usage)
    # await research_agent.store_findings(findings, execution_id)
    
    return findings


async def example_cached_fallback():
    """
    Example: Demonstrate cached data fallback
    
    This would happen when LLM calls fail after retries.
    """
    
    topic = "Insurance risk assessment framework"
    industry = "insurance"
    execution_id = "example-execution-456"
    
    print(f"\nExample: Cached Data Fallback")
    print(f"Topic: {topic}")
    print(f"Industry: {industry}")
    print("-" * 80)
    
    # In this example, if LLM is unavailable, the agent will use cached data
    findings = await research_agent.analyze_topic(
        topic=topic,
        industry=industry,
        execution_id=execution_id,
    )
    
    print(f"\nResearch Analysis Complete!")
    print(f"Method: {findings.method}")
    print(f"Sections: {len(findings.sections)}")
    print(f"Risks: {len(findings.risks)}")
    print(f"Opportunities: {len(findings.opportunities)}")
    
    return findings


async def example_different_industries():
    """
    Example: Research analysis across different industries
    """
    
    industries = [
        ("healthcare", "Patient care optimization strategy"),
        ("finance", "Investment portfolio diversification approach"),
        ("technology", "Cloud migration roadmap for enterprise"),
        ("retail", "Omnichannel customer experience enhancement"),
    ]
    
    print(f"\nExample: Multi-Industry Research Analysis")
    print("-" * 80)
    
    for industry, topic in industries:
        print(f"\nIndustry: {industry}")
        print(f"Topic: {topic}")
        
        findings = await research_agent.analyze_topic(
            topic=topic,
            industry=industry,
            execution_id=f"example-{industry}",
        )
        
        print(f"  Sections: {len(findings.sections)}")
        print(f"  Method: {findings.method}")
        print(f"  Sample section: {findings.sections[0]}")


if __name__ == "__main__":
    # Run examples
    print("=" * 80)
    print("Research Agent - Example Usage")
    print("=" * 80)
    
    # Example 1: Basic research analysis
    asyncio.run(example_research_analysis())
    
    # Example 2: Cached fallback
    # asyncio.run(example_cached_fallback())
    
    # Example 3: Multiple industries
    # asyncio.run(example_different_industries())
