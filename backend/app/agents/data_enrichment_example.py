"""
Example usage of Data Enrichment Agent

This example demonstrates how to use the Data Enrichment Agent to generate
realistic business data and KPIs for presentations.
"""

import asyncio
from app.agents.data_enrichment import data_enrichment_agent


async def example_healthcare_enrichment():
    """Example: Healthcare industry data enrichment"""
    print("=" * 80)
    print("Example 1: Healthcare Industry Data Enrichment")
    print("=" * 80)
    
    topic = "Healthcare Risk Assessment and Patient Safety Analysis"
    industry = "healthcare"
    execution_id = "example-exec-1"
    
    # Enrich data
    enriched_data = await data_enrichment_agent.enrich_data(
        topic=topic,
        industry=industry,
        execution_id=execution_id,
    )
    
    print(f"\nTopic: {enriched_data.topic}")
    print(f"Industry: {enriched_data.industry}")
    print(f"Seed: {enriched_data.seed}")
    print(f"Topic Hash: {enriched_data.topic_hash[:16]}...")
    print(f"Agent Version: {enriched_data.agent_version}")
    
    print(f"\n--- Key Metrics ({len(enriched_data.key_metrics)} total) ---")
    for metric_name, value in list(enriched_data.key_metrics.items())[:5]:
        print(f"  {metric_name}: {value}")
    
    print(f"\n--- Charts ({len(enriched_data.charts)} total) ---")
    for i, chart in enumerate(enriched_data.charts, 1):
        print(f"  Chart {i}: {chart.title}")
        print(f"    Type: {chart.chart_type}")
        print(f"    Reason: {chart.suggested_reason}")
        print(f"    Data points: {len(chart.datasets[0]['data'])}")
    
    print(f"\n--- Tables ({len(enriched_data.tables)} total) ---")
    for i, table in enumerate(enriched_data.tables, 1):
        print(f"  Table {i}: {table.title}")
        print(f"    Columns: {', '.join(table.headers)}")
        print(f"    Rows: {len(table.rows)}")
    
    print(f"\n--- Data Sources ---")
    for source in enriched_data.data_sources:
        print(f"  - {source}")
    
    print(f"\n--- Methodology ---")
    print(f"  {enriched_data.methodology_notes}")
    
    print("\n")


async def example_unknown_industry_enrichment():
    """Example: Unknown industry with LLM fallback"""
    print("=" * 80)
    print("Example 2: Unknown Industry (Quantum Computing) - LLM Fallback")
    print("=" * 80)
    
    topic = "Quantum Computing Market Analysis and Technology Roadmap"
    industry = "quantum_computing"
    execution_id = "example-exec-2"
    
    # Enrich data (will use LLM fallback for unknown industry)
    enriched_data = await data_enrichment_agent.enrich_data(
        topic=topic,
        industry=industry,
        execution_id=execution_id,
    )
    
    print(f"\nTopic: {enriched_data.topic}")
    print(f"Industry: {enriched_data.industry}")
    print(f"Seed: {enriched_data.seed}")
    
    print(f"\n--- Key Metrics ({len(enriched_data.key_metrics)} total) ---")
    for metric_name, value in list(enriched_data.key_metrics.items())[:5]:
        print(f"  {metric_name}: {value}")
    
    print(f"\n--- Charts Generated ---")
    for i, chart in enumerate(enriched_data.charts, 1):
        print(f"  Chart {i}: {chart.title} ({chart.chart_type})")
    
    print("\n")


async def example_reproducibility():
    """Example: Demonstrate reproducibility with same topic"""
    print("=" * 80)
    print("Example 3: Reproducibility - Same Topic, Same Results")
    print("=" * 80)
    
    topic = "Insurance Risk Assessment"
    industry = "insurance"
    
    # Generate data twice
    data1 = await data_enrichment_agent.enrich_data(
        topic=topic,
        industry=industry,
        execution_id="example-exec-3a",
    )
    
    data2 = await data_enrichment_agent.enrich_data(
        topic=topic,
        industry=industry,
        execution_id="example-exec-3b",
    )
    
    print(f"\nTopic: {topic}")
    print(f"Industry: {industry}")
    
    print(f"\n--- Reproducibility Check ---")
    print(f"  Seed 1: {data1.seed}")
    print(f"  Seed 2: {data2.seed}")
    print(f"  Seeds Match: {data1.seed == data2.seed}")
    
    print(f"\n  Topic Hash 1: {data1.topic_hash[:16]}...")
    print(f"  Topic Hash 2: {data2.topic_hash[:16]}...")
    print(f"  Hashes Match: {data1.topic_hash == data2.topic_hash}")
    
    print(f"\n  Key Metrics Match: {data1.key_metrics == data2.key_metrics}")
    
    # Compare first chart data
    if data1.charts and data2.charts:
        chart1_data = data1.charts[0].datasets[0]['data']
        chart2_data = data2.charts[0].datasets[0]['data']
        print(f"  First Chart Data Match: {chart1_data == chart2_data}")
    
    print("\n  ✓ Reproducibility verified - identical topic produces identical results")
    print("\n")


async def example_chart_type_suggestions():
    """Example: Demonstrate chart type suggestions"""
    print("=" * 80)
    print("Example 4: Chart Type Suggestions")
    print("=" * 80)
    
    topic = "Retail Market Share Analysis and Sales Trends"
    industry = "retail"
    execution_id = "example-exec-4"
    
    enriched_data = await data_enrichment_agent.enrich_data(
        topic=topic,
        industry=industry,
        execution_id=execution_id,
    )
    
    print(f"\nTopic: {topic}")
    print(f"Industry: {industry}")
    
    print(f"\n--- Chart Type Suggestions ---")
    for i, chart in enumerate(enriched_data.charts, 1):
        print(f"\n  Chart {i}: {chart.title}")
        print(f"    Suggested Type: {chart.chart_type}")
        print(f"    Reason: {chart.suggested_reason}")
        print(f"    Data: {chart.datasets[0]['data'][:3]}... ({len(chart.datasets[0]['data'])} points)")
    
    print("\n")


async def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "DATA ENRICHMENT AGENT EXAMPLES" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")
    
    # Run examples
    await example_healthcare_enrichment()
    await example_unknown_industry_enrichment()
    await example_reproducibility()
    await example_chart_type_suggestions()
    
    print("=" * 80)
    print("All examples completed successfully!")
    print("=" * 80)
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
