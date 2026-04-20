"""
Template Seeder — Task 29.1 & 29.2

Seeds the database with system templates for known industries:
  Healthcare (3), Insurance (3), Automobile (3), Finance (2),
  Technology (2), Retail (1), Education (1)

Plus a Generic Enterprise Briefing fallback template for any unrecognised industry.

Each template's slide_structure is a list of slide defs that the Storyboarding Agent
uses as constraints when building the Presentation_Plan_JSON.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Template

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Slide structure helpers
# ---------------------------------------------------------------------------

def _slide(section: str, type_: str, title_hint: str = "") -> dict[str, Any]:
    return {"section": section, "type": type_, "title_hint": title_hint}


# ---------------------------------------------------------------------------
# System template definitions
# ---------------------------------------------------------------------------

SYSTEM_TEMPLATES: list[dict[str, Any]] = [
    # ── Healthcare (3) ──────────────────────────────────────────────────────
    {
        "name": "Healthcare Executive Briefing",
        "industry": "healthcare",
        "sub_sector": None,
        "slide_structure": [
            _slide("Title", "title", "Executive Briefing"),
            _slide("Agenda", "content", "Agenda"),
            _slide("Problem", "content", "Clinical Challenge"),
            _slide("Problem", "chart", "Patient Outcome Trends"),
            _slide("Analysis", "content", "Clinical Analysis"),
            _slide("Analysis", "chart", "Key Performance Indicators"),
            _slide("Analysis", "table", "Comparative Metrics"),
            _slide("Evidence", "chart", "Evidence-Based Data"),
            _slide("Evidence", "comparison", "Treatment Comparison"),
            _slide("Recommendations", "content", "Clinical Recommendations"),
            _slide("Recommendations", "content", "Implementation Roadmap"),
            _slide("Conclusion", "content", "Key Takeaways"),
        ],
    },
    {
        "name": "Clinical Research Summary",
        "industry": "healthcare",
        "sub_sector": "clinical research",
        "slide_structure": [
            _slide("Title", "title", "Clinical Research Summary"),
            _slide("Agenda", "content", "Study Overview"),
            _slide("Problem", "content", "Research Hypothesis"),
            _slide("Analysis", "content", "Methodology"),
            _slide("Analysis", "table", "Patient Demographics"),
            _slide("Analysis", "chart", "Primary Endpoints"),
            _slide("Evidence", "chart", "Statistical Results"),
            _slide("Evidence", "table", "Adverse Events"),
            _slide("Recommendations", "content", "Clinical Implications"),
            _slide("Conclusion", "content", "Conclusions & Next Steps"),
        ],
    },
    {
        "name": "Healthcare Compliance Report",
        "industry": "healthcare",
        "sub_sector": "compliance",
        "slide_structure": [
            _slide("Title", "title", "Compliance Report"),
            _slide("Agenda", "content", "Compliance Overview"),
            _slide("Problem", "content", "Regulatory Requirements"),
            _slide("Analysis", "table", "Compliance Status Matrix"),
            _slide("Analysis", "chart", "Audit Findings"),
            _slide("Evidence", "comparison", "Gap Analysis"),
            _slide("Recommendations", "content", "Remediation Plan"),
            _slide("Conclusion", "content", "Compliance Roadmap"),
        ],
    },

    # ── Insurance (3) ───────────────────────────────────────────────────────
    {
        "name": "Risk Assessment",
        "industry": "insurance",
        "sub_sector": "risk",
        "slide_structure": [
            _slide("Title", "title", "Risk Assessment"),
            _slide("Agenda", "content", "Assessment Scope"),
            _slide("Problem", "content", "Risk Landscape"),
            _slide("Problem", "chart", "Risk Exposure Overview"),
            _slide("Analysis", "table", "Risk Register"),
            _slide("Analysis", "chart", "Loss Frequency & Severity"),
            _slide("Evidence", "comparison", "Benchmark Comparison"),
            _slide("Evidence", "chart", "Actuarial Projections"),
            _slide("Recommendations", "content", "Risk Mitigation Strategies"),
            _slide("Recommendations", "table", "Action Plan"),
            _slide("Conclusion", "content", "Summary & Next Steps"),
        ],
    },
    {
        "name": "Insurance Market Analysis",
        "industry": "insurance",
        "sub_sector": "market",
        "slide_structure": [
            _slide("Title", "title", "Market Analysis"),
            _slide("Agenda", "content", "Market Overview"),
            _slide("Problem", "content", "Market Challenges"),
            _slide("Analysis", "chart", "Market Size & Growth"),
            _slide("Analysis", "comparison", "Competitive Landscape"),
            _slide("Evidence", "chart", "Premium Trends"),
            _slide("Evidence", "table", "Product Performance"),
            _slide("Recommendations", "content", "Strategic Opportunities"),
            _slide("Conclusion", "content", "Key Takeaways"),
        ],
    },
    {
        "name": "Claims Performance Report",
        "industry": "insurance",
        "sub_sector": "claims",
        "slide_structure": [
            _slide("Title", "title", "Claims Performance Report"),
            _slide("Agenda", "content", "Report Overview"),
            _slide("Problem", "content", "Claims Environment"),
            _slide("Analysis", "chart", "Claims Volume Trends"),
            _slide("Analysis", "table", "Claims by Category"),
            _slide("Evidence", "chart", "Settlement Ratios"),
            _slide("Recommendations", "content", "Process Improvements"),
            _slide("Conclusion", "content", "Performance Summary"),
        ],
    },

    # ── Automobile (3) ──────────────────────────────────────────────────────
    {
        "name": "Automotive Manufacturing Update",
        "industry": "automobile",
        "sub_sector": "manufacturing",
        "slide_structure": [
            _slide("Title", "title", "Manufacturing Update"),
            _slide("Agenda", "content", "Operations Overview"),
            _slide("Problem", "content", "Production Challenges"),
            _slide("Analysis", "chart", "Production Volume"),
            _slide("Analysis", "table", "Quality Metrics"),
            _slide("Analysis", "chart", "Supply Chain Status"),
            _slide("Evidence", "comparison", "OEM Benchmarks"),
            _slide("Recommendations", "content", "Operational Improvements"),
            _slide("Recommendations", "table", "Implementation Timeline"),
            _slide("Conclusion", "content", "Key Takeaways"),
        ],
    },
    {
        "name": "Automotive Market Research",
        "industry": "automobile",
        "sub_sector": "market",
        "slide_structure": [
            _slide("Title", "title", "Market Research"),
            _slide("Agenda", "content", "Research Scope"),
            _slide("Problem", "content", "Market Dynamics"),
            _slide("Analysis", "chart", "Market Share Analysis"),
            _slide("Analysis", "comparison", "Segment Comparison"),
            _slide("Evidence", "chart", "Consumer Trends"),
            _slide("Evidence", "table", "EV Adoption Data"),
            _slide("Recommendations", "content", "Strategic Recommendations"),
            _slide("Conclusion", "content", "Market Outlook"),
        ],
    },
    {
        "name": "Vehicle Safety Report",
        "industry": "automobile",
        "sub_sector": "safety",
        "slide_structure": [
            _slide("Title", "title", "Safety Report"),
            _slide("Agenda", "content", "Safety Overview"),
            _slide("Problem", "content", "Safety Challenges"),
            _slide("Analysis", "table", "Incident Analysis"),
            _slide("Analysis", "chart", "Safety Ratings"),
            _slide("Evidence", "comparison", "Regulatory Compliance"),
            _slide("Recommendations", "content", "Safety Improvements"),
            _slide("Conclusion", "content", "Safety Roadmap"),
        ],
    },

    # ── Finance (2) ─────────────────────────────────────────────────────────
    {
        "name": "Financial Executive Briefing",
        "industry": "finance",
        "sub_sector": None,
        "slide_structure": [
            _slide("Title", "title", "Financial Briefing"),
            _slide("Agenda", "content", "Agenda"),
            _slide("Problem", "content", "Financial Context"),
            _slide("Analysis", "chart", "Revenue & Profitability"),
            _slide("Analysis", "table", "Financial Highlights"),
            _slide("Analysis", "chart", "Portfolio Performance"),
            _slide("Evidence", "comparison", "Peer Benchmarking"),
            _slide("Evidence", "chart", "Market Indicators"),
            _slide("Recommendations", "content", "Strategic Recommendations"),
            _slide("Recommendations", "table", "Action Items"),
            _slide("Conclusion", "content", "Key Takeaways"),
        ],
    },
    {
        "name": "Investment Analysis",
        "industry": "finance",
        "sub_sector": "investment",
        "slide_structure": [
            _slide("Title", "title", "Investment Analysis"),
            _slide("Agenda", "content", "Analysis Overview"),
            _slide("Problem", "content", "Investment Thesis"),
            _slide("Analysis", "chart", "Valuation Analysis"),
            _slide("Analysis", "table", "Financial Model"),
            _slide("Evidence", "chart", "Comparable Transactions"),
            _slide("Evidence", "comparison", "Risk/Return Profile"),
            _slide("Recommendations", "content", "Investment Recommendation"),
            _slide("Conclusion", "content", "Summary"),
        ],
    },

    # ── Technology (2) ──────────────────────────────────────────────────────
    {
        "name": "Technology Strategy",
        "industry": "technology",
        "sub_sector": None,
        "slide_structure": [
            _slide("Title", "title", "Technology Strategy"),
            _slide("Agenda", "content", "Agenda"),
            _slide("Problem", "content", "Technology Challenges"),
            _slide("Analysis", "content", "Current State Assessment"),
            _slide("Analysis", "chart", "Technology Landscape"),
            _slide("Analysis", "comparison", "Build vs Buy Analysis"),
            _slide("Evidence", "chart", "Performance Metrics"),
            _slide("Evidence", "table", "Technology Stack"),
            _slide("Recommendations", "content", "Strategic Roadmap"),
            _slide("Recommendations", "chart", "Investment Plan"),
            _slide("Conclusion", "content", "Key Takeaways"),
        ],
    },
    {
        "name": "Product Launch",
        "industry": "technology",
        "sub_sector": "product",
        "slide_structure": [
            _slide("Title", "title", "Product Launch"),
            _slide("Agenda", "content", "Launch Overview"),
            _slide("Problem", "content", "Market Opportunity"),
            _slide("Analysis", "content", "Product Overview"),
            _slide("Analysis", "comparison", "Competitive Differentiation"),
            _slide("Evidence", "chart", "Market Validation"),
            _slide("Evidence", "table", "Feature Comparison"),
            _slide("Recommendations", "content", "Go-to-Market Strategy"),
            _slide("Conclusion", "content", "Launch Roadmap"),
        ],
    },

    # ── Retail (1) ──────────────────────────────────────────────────────────
    {
        "name": "Retail Market & Consumer Analysis",
        "industry": "retail",
        "sub_sector": None,
        "slide_structure": [
            _slide("Title", "title", "Market & Consumer Analysis"),
            _slide("Agenda", "content", "Analysis Overview"),
            _slide("Problem", "content", "Market Challenges"),
            _slide("Analysis", "chart", "Sales Performance"),
            _slide("Analysis", "table", "Category Analysis"),
            _slide("Analysis", "chart", "Consumer Behaviour"),
            _slide("Evidence", "comparison", "Competitive Benchmarks"),
            _slide("Recommendations", "content", "Growth Strategies"),
            _slide("Recommendations", "table", "Action Plan"),
            _slide("Conclusion", "content", "Key Takeaways"),
        ],
    },

    # ── Education (1) ───────────────────────────────────────────────────────
    {
        "name": "Education Research & Insights",
        "industry": "education",
        "sub_sector": None,
        "slide_structure": [
            _slide("Title", "title", "Research & Insights"),
            _slide("Agenda", "content", "Overview"),
            _slide("Problem", "content", "Educational Challenge"),
            _slide("Analysis", "content", "Research Findings"),
            _slide("Analysis", "chart", "Performance Data"),
            _slide("Analysis", "table", "Comparative Analysis"),
            _slide("Evidence", "chart", "Outcome Metrics"),
            _slide("Recommendations", "content", "Recommendations"),
            _slide("Conclusion", "content", "Key Takeaways"),
        ],
    },

    # ── Generic Enterprise Briefing (fallback — Task 29.2) ──────────────────
    {
        "name": "Generic Enterprise Briefing",
        "industry": "general",
        "sub_sector": None,
        "slide_structure": [
            _slide("Title", "title", "Executive Briefing"),
            _slide("Agenda", "content", "Agenda"),
            _slide("Problem", "content", "Business Challenge"),
            _slide("Problem", "chart", "Current State Overview"),
            _slide("Analysis", "content", "Detailed Analysis"),
            _slide("Analysis", "chart", "Key Metrics"),
            _slide("Analysis", "table", "Data Summary"),
            _slide("Evidence", "comparison", "Benchmarking"),
            _slide("Evidence", "chart", "Supporting Evidence"),
            _slide("Recommendations", "content", "Strategic Recommendations"),
            _slide("Recommendations", "table", "Implementation Plan"),
            _slide("Conclusion", "content", "Key Takeaways"),
        ],
    },
]


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

async def seed_system_templates(db: AsyncSession) -> int:
    """
    Idempotently seed system templates into the database.

    Skips templates that already exist (matched by name + industry).
    Returns the number of templates inserted.
    """
    inserted = 0

    for tpl_def in SYSTEM_TEMPLATES:
        # Check if already seeded
        result = await db.execute(
            select(Template).where(
                Template.name == tpl_def["name"],
                Template.industry == tpl_def["industry"],
                Template.is_system == True,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.debug(
                "template_already_seeded",
                name=tpl_def["name"],
                industry=tpl_def["industry"],
            )
            continue

        template = Template(
            name=tpl_def["name"],
            industry=tpl_def["industry"],
            sub_sector=tpl_def.get("sub_sector"),
            slide_structure={"slides": tpl_def["slide_structure"]},
            is_system=True,
            usage_count=0,
            tenant_id=None,  # system templates have no tenant
        )
        db.add(template)
        inserted += 1
        logger.info(
            "template_seeded",
            name=tpl_def["name"],
            industry=tpl_def["industry"],
        )

    if inserted:
        await db.commit()

    logger.info("template_seeding_complete", inserted=inserted, total=len(SYSTEM_TEMPLATES))
    return inserted
