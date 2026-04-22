"""
Industry Classifier Agent

This agent is the FIRST agent in the pipeline. It automatically detects the industry
from the topic using a three-step classification approach:
1. Keyword matching (fast, deterministic)
2. Semantic similarity (embedding-based)
3. LLM classification (open-ended, handles any industry)

The user never sees or interacts with this step — it is fully automatic.
"""

import re
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import structlog

from sentence_transformers import SentenceTransformer
import numpy as np
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.services.llm_provider import provider_factory


logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Industry Seed Terms for Keyword Matching (Step 1)
# ---------------------------------------------------------------------------

INDUSTRY_SEED_TERMS = {
    "healthcare": [
        "patient", "clinical", "hospital", "diagnosis", "treatment",
        "pharma", "pharmaceutical", "EHR", "HIPAA", "FDA", "medical", "physician",
        "drug", "therapy", "biotech", "surgical", "radiology", "healthcare",
        "medicine", "doctor", "nurse", "clinic", "disease", "health"
    ],
    "insurance": [
        "premium", "policy", "underwriting", "actuarial", "claims",
        "risk", "reinsurance", "liability", "coverage", "deductible",
        "insurance", "insurer", "policyholder", "beneficiary", "indemnity"
    ],
    "automobile": [
        "vehicle", "car", "OEM", "fleet", "manufacturing", "EV",
        "supply chain", "dealership", "automotive", "engine", "automobile",
        "auto", "truck", "sedan", "SUV", "electric vehicle", "hybrid"
    ],
    "finance": [
        "banking", "investment", "portfolio", "equity", "bond",
        "fintech", "trading", "hedge fund", "asset management", "finance",
        "financial", "bank", "credit", "loan", "mortgage", "capital"
    ],
    "fintech": [
        "fintech", "blockchain", "cryptocurrency", "digital wallet", "payment",
        "neobank", "peer-to-peer", "P2P", "digital currency", "crypto",
        "DeFi", "decentralized finance", "smart contract", "token"
    ],
    "technology": [
        "software", "SaaS", "cloud", "API", "platform", "startup",
        "AI", "machine learning", "cybersecurity", "DevOps", "technology",
        "tech", "digital", "app", "application", "data", "analytics"
    ],
    "retail": [
        "e-commerce", "consumer", "merchandise", "store", "SKU",
        "inventory", "supply chain", "omnichannel", "loyalty", "retail",
        "shopping", "customer", "sales", "product", "brand", "market"
    ],
    "education": [
        "university", "curriculum", "student", "learning", "EdTech",
        "training", "certification", "academic", "school", "education",
        "teacher", "course", "degree", "college", "classroom"
    ],
    "manufacturing": [
        "production", "factory", "assembly", "quality control", "lean",
        "manufacturing", "industrial", "machinery", "equipment", "process",
        "operations", "plant", "fabrication", "automation"
    ],
    "logistics": [
        "shipping", "freight", "warehouse", "distribution", "transportation",
        "logistics", "delivery", "cargo", "supply chain", "fulfillment",
        "courier", "tracking", "inventory management"
    ],
    "real_estate": [
        "property", "real estate", "housing", "commercial", "residential",
        "lease", "rent", "mortgage", "broker", "listing", "development",
        "construction", "building", "tenant", "landlord"
    ],
}


# ---------------------------------------------------------------------------
# Audience Inference Rules
# ---------------------------------------------------------------------------

AUDIENCE_SIGNALS = {
    "executives": [
        "board", "CEO", "CFO", "CTO", "strategy", "ROI", "investment",
        "executive", "leadership", "vision", "growth", "revenue", "profit"
    ],
    "analysts": [
        "data", "metrics", "KPI", "analysis", "trends", "statistics",
        "analytics", "insights", "performance", "measurement", "reporting"
    ],
    "technical": [
        "architecture", "API", "implementation", "system", "infrastructure",
        "technical", "engineering", "development", "code", "integration"
    ],
}


# ---------------------------------------------------------------------------
# Template Selection Matrix
# ---------------------------------------------------------------------------

TEMPLATE_SELECTION_MATRIX = {
    "healthcare": {
        "research|study|trial|clinical": "Clinical Research Summary",
        "compliance|regulation|HIPAA|FDA": "Compliance Report",
        "default": "Healthcare Executive Briefing",
    },
    "insurance": {
        "risk|assessment|underwriting": "Risk Assessment",
        "market|product|launch": "Market Analysis",
        "default": "Risk Assessment",
    },
    "automobile": {
        "safety|recall|quality": "Safety Report",
        "market|consumer|sales": "Market Research",
        "default": "Manufacturing Update",
    },
    "finance": {
        "investment|portfolio|trading": "Investment Analysis",
        "default": "Financial Executive Briefing",
    },
    "technology": {
        "product|launch|release": "Product Launch",
        "default": "Technology Strategy",
    },
    "retail": {
        "default": "Market & Consumer Analysis",
    },
    "education": {
        "default": "Research & Insights",
    },
    "manufacturing": {
        "default": "Operations & Efficiency Report",
    },
    "logistics": {
        "default": "Supply Chain Analysis",
    },
    "real_estate": {
        "default": "Market & Investment Analysis",
    },
}

# Fallback template for any unrecognized industry
DEFAULT_TEMPLATE = "Generic Enterprise Briefing"


# ---------------------------------------------------------------------------
# Pydantic Models for LLM Output
# ---------------------------------------------------------------------------

class LLMClassificationOutput(BaseModel):
    """Structured output from LLM classification"""
    industry: str = Field(description="Industry name as a short label (e.g., 'healthcare', 'fintech', 'retail')")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0)
    sub_sector: Optional[str] = Field(default=None, description="Specific sub-sector within the industry")
    target_audience: str = Field(description="Target audience: executives, analysts, technical, or general")
    compliance_context: List[str] = Field(default_factory=list, description="Relevant compliance frameworks or regulations")


@dataclass
class DetectedContext:
    """Output schema for Industry Classifier Agent"""
    industry: str
    confidence: float
    sub_sector: Optional[str]
    target_audience: str
    selected_template_id: Optional[str]
    selected_template_name: str
    theme: str
    compliance_context: List[str]
    classification_method: str  # "keyword", "semantic", or "llm"


class IndustryClassifierAgent:
    """
    Industry Classifier Agent - First agent in the pipeline
    
    Automatically detects industry, infers audience, and selects template
    from topic text alone using a three-step classification approach.
    """
    
    def __init__(self):
        self.embedding_model: Optional[SentenceTransformer] = None
        self.industry_centroids: Dict[str, np.ndarray] = {}
        self._initialize_embedding_model()
    
    def _initialize_embedding_model(self) -> None:
        """Initialize sentence-transformers model for semantic similarity"""
        try:
            logger.info("initializing_embedding_model")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Pre-compute industry centroids
            self._compute_industry_centroids()
            
            logger.info("embedding_model_initialized")
        except Exception as e:
            logger.error("embedding_model_initialization_failed", error=str(e))
            self.embedding_model = None
    
    def _compute_industry_centroids(self) -> None:
        """Pre-compute embedding centroids for each industry"""
        if not self.embedding_model:
            return
        
        logger.info("computing_industry_centroids")
        
        for industry, terms in INDUSTRY_SEED_TERMS.items():
            # Compute embeddings for all terms
            embeddings = self.embedding_model.encode(terms)
            
            # Compute centroid (mean of all embeddings)
            centroid = np.mean(embeddings, axis=0)
            self.industry_centroids[industry] = centroid
        
        logger.info("industry_centroids_computed", count=len(self.industry_centroids))
    
    def _normalize_topic(self, topic: str) -> str:
        """Normalize topic text for matching"""
        # Convert to lowercase
        normalized = topic.lower()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _keyword_matching(self, topic: str) -> Tuple[Optional[str], float]:
        """
        Step 1: Keyword matching against industry seed terms
        
        Returns:
            Tuple of (industry, score) where score is between 0.0 and 1.0
        """
        logger.info("step1_keyword_matching", topic=topic[:100])
        
        normalized_topic = self._normalize_topic(topic)
        topic_words = set(normalized_topic.split())
        
        best_industry = None
        best_score = 0.0
        
        for industry, terms in INDUSTRY_SEED_TERMS.items():
            # Normalize terms
            normalized_terms = [term.lower() for term in terms]
            
            # Count matches
            matches = 0
            for term in normalized_terms:
                # Check for exact word match or substring match
                if term in topic_words or term in normalized_topic:
                    matches += 1
            
            # Calculate score (percentage of terms matched)
            score = matches / len(normalized_terms) if normalized_terms else 0.0
            
            if score > best_score:
                best_score = score
                best_industry = industry
        
        logger.info(
            "keyword_matching_result",
            industry=best_industry,
            score=best_score,
        )
        
        return best_industry, best_score
    
    def _semantic_similarity(self, topic: str) -> Tuple[Optional[str], float]:
        """
        Step 2: Semantic similarity using sentence-transformers
        
        Returns:
            Tuple of (industry, score) where score is between 0.0 and 1.0
        """
        logger.info("step2_semantic_similarity", topic=topic[:100])
        
        if not self.embedding_model or not self.industry_centroids:
            logger.warning("embedding_model_not_available")
            return None, 0.0
        
        try:
            # Encode topic
            topic_embedding = self.embedding_model.encode(topic)
            
            # Compute cosine similarity with each industry centroid
            best_industry = None
            best_score = 0.0
            
            for industry, centroid in self.industry_centroids.items():
                # Cosine similarity
                similarity = np.dot(topic_embedding, centroid) / (
                    np.linalg.norm(topic_embedding) * np.linalg.norm(centroid)
                )
                
                if similarity > best_score:
                    best_score = float(similarity)
                    best_industry = industry
            
            logger.info(
                "semantic_similarity_result",
                industry=best_industry,
                score=best_score,
            )
            
            return best_industry, best_score
            
        except Exception as e:
            logger.error("semantic_similarity_failed", error=str(e))
            return None, 0.0
    
    async def _llm_classification(
        self,
        topic: str,
        execution_id: str,
    ) -> Tuple[Optional[str], float, Optional[str], str, List[str]]:
        """
        Step 3: LLM-based classification for open-ended industry detection
        
        Returns:
            Tuple of (industry, confidence, sub_sector, audience, compliance_context)
        """
        logger.info("step3_llm_classification", topic=topic[:100])
        
        system_prompt = """You are an expert industry classifier. Your task is to identify the industry that a presentation topic belongs to.

Return your classification as JSON with the following fields:
- industry: A short industry label (e.g., 'healthcare', 'fintech', 'retail', 'manufacturing', 'education', 'logistics', 'real estate', etc.)
- confidence: Your confidence score between 0.0 and 1.0
- sub_sector: Specific sub-sector within the industry (optional)
- target_audience: The target audience - must be one of: executives, analysts, technical, or general
- compliance_context: List of relevant compliance frameworks or regulations (e.g., ["HIPAA", "FDA"] for healthcare)

Be open-ended - you can identify ANY industry, not just common ones. Use your best judgment."""
        
        user_prompt = f"""Classify the following presentation topic:

Topic: {topic}

Return your classification as JSON."""
        
        try:
            # Use provider factory with failover
            async def call_llm(client: BaseChatModel):
                parser = JsonOutputParser(pydantic_object=LLMClassificationOutput)
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
                
                response = await client.ainvoke(messages)
                parsed = parser.parse(response.content)
                
                return parsed
            
            result = await provider_factory.call_with_failover(
                call_llm,
                execution_id=execution_id,
                industry="classification",  # Special marker for classification calls
            )
            
            logger.info(
                "llm_classification_result",
                industry=result.get("industry"),
                confidence=result.get("confidence"),
                sub_sector=result.get("sub_sector"),
            )
            
            return (
                result.get("industry"),
                result.get("confidence", 0.0),
                result.get("sub_sector"),
                result.get("target_audience", "general"),
                result.get("compliance_context", []),
            )
            
        except Exception as e:
            logger.error("llm_classification_failed", error=str(e))
            return None, 0.0, None, "general", []
    
    def _infer_audience(self, topic: str) -> str:
        """Infer target audience from topic language signals"""
        normalized_topic = self._normalize_topic(topic)
        
        audience_scores = {
            "executives": 0,
            "analysts": 0,
            "technical": 0,
        }
        
        for audience, signals in AUDIENCE_SIGNALS.items():
            for signal in signals:
                if signal.lower() in normalized_topic:
                    audience_scores[audience] += 1
        
        # Return audience with highest score, or "general" if no strong signals
        if max(audience_scores.values()) > 0:
            return max(audience_scores, key=audience_scores.get)
        
        return "general"
    
    def _select_template(
        self,
        industry: str,
        topic: str,
    ) -> Tuple[Optional[str], str]:
        """
        Select best-fit template based on industry and topic signals
        
        Returns:
            Tuple of (template_id, template_name)
        """
        logger.info("selecting_template", industry=industry)
        
        # Get industry-specific template matrix
        industry_templates = TEMPLATE_SELECTION_MATRIX.get(industry, {})
        
        if not industry_templates:
            # Use default template for unrecognized industry
            logger.info("using_default_template", industry=industry)
            return None, DEFAULT_TEMPLATE
        
        # Check for topic-specific template
        normalized_topic = self._normalize_topic(topic)
        
        for pattern, template_name in industry_templates.items():
            if pattern == "default":
                continue
            
            # Check if any pattern keyword matches
            keywords = pattern.split("|")
            if any(keyword in normalized_topic for keyword in keywords):
                logger.info(
                    "template_selected",
                    industry=industry,
                    pattern=pattern,
                    template=template_name,
                )
                return None, template_name  # template_id will be resolved from DB
        
        # Use default template for industry
        default_template = industry_templates.get("default", DEFAULT_TEMPLATE)
        logger.info(
            "using_industry_default_template",
            industry=industry,
            template=default_template,
        )
        
        return None, default_template
    
    def _select_theme(self, industry: str, audience: str) -> str:
        """
        Select presentation theme based on industry and audience.

        Priority: dark_modern is the default. Agent selects the best fit:
        - dark_modern: tech, fintech, data-heavy, technical audiences (default)
        - mckinsey:    strategy, consulting, executive C-suite presentations
        - deloitte:    finance, professional services, analyst audiences

        Returns:
            Theme name: "dark_modern" | "mckinsey" | "deloitte"
        """
        # Technical audiences → dark modern
        if audience == "technical":
            return "dark_modern"

        # Executive / C-suite strategy content → McKinsey
        if audience == "executives":
            # For executives, prefer McKinsey for most industries except pure tech
            if industry in ("technology", "fintech"):
                return "dark_modern"
            # All other industries with executive audience get McKinsey
            return "mckinsey"

        # Analyst / finance audiences → Deloitte
        if audience == "analysts":
            if industry in ("finance", "insurance", "healthcare"):
                return "deloitte"

        # Industry-based selection for remaining cases
        if industry in ("technology", "fintech", "automobile"):
            return "dark_modern"
        if industry in ("finance", "insurance"):
            return "deloitte"
        if industry in ("consulting", "strategy"):
            return "mckinsey"

        # Default: dark_modern
        return "dark_modern"
    
    async def classify(
        self,
        topic: str,
        execution_id: str,
    ) -> DetectedContext:
        """
        Main classification method - runs all three steps
        
        Args:
            topic: User-provided presentation topic
            execution_id: Unique execution ID for tracing
        
        Returns:
            DetectedContext with all classification results
        """
        logger.info(
            "industry_classification_started",
            topic=topic[:100],
            execution_id=execution_id,
        )
        
        start_time = datetime.utcnow()
        
        # Step 1: Keyword matching
        keyword_industry, keyword_score = self._keyword_matching(topic)
        
        # If keyword score is high enough, use it
        if keyword_score >= 0.6:
            industry = keyword_industry
            confidence = keyword_score
            classification_method = "keyword"
            sub_sector = None
            compliance_context = []
            
            # Infer audience from topic
            audience = self._infer_audience(topic)
            
            logger.info(
                "classification_completed_keyword",
                industry=industry,
                confidence=confidence,
                method=classification_method,
            )
        
        else:
            # Step 2: Semantic similarity
            semantic_industry, semantic_score = self._semantic_similarity(topic)
            
            # If semantic score is high enough, use it
            if semantic_score >= 0.8:
                industry = semantic_industry
                confidence = semantic_score
                classification_method = "semantic"
                sub_sector = None
                compliance_context = []
                
                # Infer audience from topic
                audience = self._infer_audience(topic)
                
                logger.info(
                    "classification_completed_semantic",
                    industry=industry,
                    confidence=confidence,
                    method=classification_method,
                )
            
            else:
                # Step 3: LLM classification
                (
                    llm_industry,
                    llm_confidence,
                    llm_sub_sector,
                    llm_audience,
                    llm_compliance,
                ) = await self._llm_classification(topic, execution_id)
                
                if llm_industry:
                    industry = llm_industry
                    confidence = llm_confidence
                    classification_method = "llm"
                    sub_sector = llm_sub_sector
                    compliance_context = llm_compliance
                    audience = llm_audience
                    
                    logger.info(
                        "classification_completed_llm",
                        industry=industry,
                        confidence=confidence,
                        method=classification_method,
                    )
                
                else:
                    # Fallback: use best available result
                    if semantic_score > keyword_score:
                        industry = semantic_industry
                        confidence = semantic_score
                        classification_method = "semantic"
                    else:
                        industry = keyword_industry
                        confidence = keyword_score
                        classification_method = "keyword"
                    
                    sub_sector = None
                    compliance_context = []
                    audience = self._infer_audience(topic)
                    
                    logger.warning(
                        "classification_fallback",
                        industry=industry,
                        confidence=confidence,
                        method=classification_method,
                    )
        
        # Select template
        template_id, template_name = self._select_template(industry, topic)
        
        # Select theme
        theme = self._select_theme(industry, audience)
        
        # Create result
        result = DetectedContext(
            industry=industry,
            confidence=confidence,
            sub_sector=sub_sector,
            target_audience=audience,
            selected_template_id=template_id,
            selected_template_name=template_name,
            theme=theme,
            compliance_context=compliance_context,
            classification_method=classification_method,
        )
        
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info(
            "industry_classification_completed",
            industry=result.industry,
            confidence=result.confidence,
            template=result.selected_template_name,
            theme=result.theme,
            audience=result.target_audience,
            method=result.classification_method,
            elapsed_ms=elapsed_ms,
            execution_id=execution_id,
        )
        
        return result


# Global agent instance
industry_classifier = IndustryClassifierAgent()
