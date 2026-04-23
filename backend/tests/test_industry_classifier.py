"""
Tests for Industry Classifier Agent
"""

import pytest
from app.agents.industry_classifier import industry_classifier, INDUSTRY_SEED_TERMS


class TestKeywordMatching:
    """Test keyword matching (Step 1)"""
    
    def test_healthcare_topic(self):
        """Test healthcare topic classification via keywords"""
        topic = "Clinical trial results for new pharmaceutical treatment"
        industry, score = industry_classifier._keyword_matching(topic)
        
        assert industry == "healthcare"
        assert score > 0.0
    
    def test_finance_topic(self):
        """Test finance topic classification via keywords"""
        topic = "Investment portfolio analysis and asset management strategy"
        industry, score = industry_classifier._keyword_matching(topic)
        
        assert industry == "finance"
        assert score > 0.0
    
    def test_technology_topic(self):
        """Test technology topic classification via keywords"""
        topic = "Cloud platform architecture and API integration strategy"
        industry, score = industry_classifier._keyword_matching(topic)
        
        assert industry == "technology"
        assert score > 0.0
    
    def test_low_confidence_topic(self):
        """Test topic with low keyword match"""
        topic = "General business strategy and market positioning"
        industry, score = industry_classifier._keyword_matching(topic)
        
        # Should still return something, but with low score
        assert score < 0.6


class TestSemanticSimilarity:
    """Test semantic similarity (Step 2)"""
    
    def test_semantic_healthcare(self):
        """Test semantic similarity for healthcare topic"""
        topic = "Patient outcomes and medical device effectiveness study"
        industry, score = industry_classifier._semantic_similarity(topic)
        
        # Should match healthcare semantically
        if industry:  # Only if embedding model is available
            assert industry == "healthcare"
            assert score > 0.0
    
    def test_semantic_insurance(self):
        """Test semantic similarity for insurance topic"""
        topic = "Risk assessment and actuarial modeling for insurance products"
        industry, score = industry_classifier._semantic_similarity(topic)
        
        if industry:
            assert industry == "insurance"
            assert score > 0.0


class TestAudienceInference:
    """Test audience inference"""
    
    def test_executive_audience(self):
        """Test executive audience detection"""
        topic = "Board presentation on CEO strategy and ROI analysis"
        audience = industry_classifier._infer_audience(topic)
        
        assert audience == "executives"
    
    def test_analyst_audience(self):
        """Test analyst audience detection"""
        topic = "Data analytics and KPI metrics for performance measurement"
        audience = industry_classifier._infer_audience(topic)
        
        assert audience == "analysts"
    
    def test_technical_audience(self):
        """Test technical audience detection"""
        topic = "System architecture and API implementation details"
        audience = industry_classifier._infer_audience(topic)
        
        assert audience == "technical"
    
    def test_general_audience(self):
        """Test general audience fallback"""
        topic = "Company overview and business model"
        audience = industry_classifier._infer_audience(topic)
        
        assert audience == "general"


class TestTemplateSelection:
    """Test template selection"""
    
    def test_healthcare_research_template(self):
        """Test healthcare research template selection"""
        topic = "Clinical research study results and trial outcomes"
        template_id, template_name = industry_classifier._select_template(
            "healthcare", topic
        )
        
        assert template_name == "Clinical Research Summary"
    
    def test_healthcare_compliance_template(self):
        """Test healthcare compliance template selection"""
        topic = "HIPAA compliance and FDA regulation overview"
        template_id, template_name = industry_classifier._select_template(
            "healthcare", topic
        )
        
        assert template_name == "Compliance Report"
    
    def test_healthcare_default_template(self):
        """Test healthcare default template"""
        topic = "Healthcare industry overview"
        template_id, template_name = industry_classifier._select_template(
            "healthcare", topic
        )
        
        assert template_name == "Healthcare Executive Briefing"
    
    def test_unknown_industry_template(self):
        """Test fallback template for unknown industry"""
        topic = "Some topic"
        template_id, template_name = industry_classifier._select_template(
            "unknown_industry", topic
        )
        
        assert template_name == "Generic Enterprise Briefing"


class TestThemeSelection:
    """Test theme selection"""
    
    def test_executive_theme(self):
        """Test executive theme for executives"""
        theme = industry_classifier._select_theme("healthcare", "executives")
        assert theme == "executive"
    
    def test_technical_theme(self):
        """Test Dark Modern theme for technical audience"""
        theme = industry_classifier._select_theme("technology", "technical")
        assert theme == "dark_modern"
    
    def test_default_theme(self):
        """Test professional theme for finance analysts"""
        theme = industry_classifier._select_theme("finance", "analysts")
        assert theme == "professional"


@pytest.mark.asyncio
class TestFullClassification:
    """Test full classification pipeline"""
    
    async def test_healthcare_classification(self):
        """Test full classification for healthcare topic"""
        topic = "Clinical trial results for new pharmaceutical treatment"
        execution_id = "test-exec-001"
        
        context = await industry_classifier.classify(topic, execution_id)
        
        assert context.industry == "healthcare"
        assert context.confidence > 0.0
        assert context.target_audience in ["executives", "analysts", "technical", "general"]
        assert context.selected_template_name is not None
        assert context.theme in ["executive", "professional", "dark_modern", "corporate"]
        assert context.classification_method in ["keyword", "semantic", "llm"]
    
    async def test_finance_classification(self):
        """Test full classification for finance topic"""
        topic = "Investment portfolio analysis and hedge fund strategy"
        execution_id = "test-exec-002"
        
        context = await industry_classifier.classify(topic, execution_id)
        
        assert context.industry == "finance"
        assert context.confidence > 0.0
        assert context.selected_template_name is not None
    
    async def test_technology_classification(self):
        """Test full classification for technology topic"""
        topic = "Cloud platform architecture and microservices implementation"
        execution_id = "test-exec-003"
        
        context = await industry_classifier.classify(topic, execution_id)
        
        assert context.industry == "technology"
        assert context.confidence > 0.0
        assert context.target_audience == "technical"  # Should detect technical audience
        assert context.theme == "dark_modern"  # Technical audience gets dark theme


class TestIndustrySeedTerms:
    """Test industry seed terms dictionary"""
    
    def test_all_industries_have_terms(self):
        """Verify all industries have seed terms"""
        assert len(INDUSTRY_SEED_TERMS) > 0
        
        for industry, terms in INDUSTRY_SEED_TERMS.items():
            assert len(terms) > 0
            assert all(isinstance(term, str) for term in terms)
    
    def test_known_industries_present(self):
        """Verify expected industries are present"""
        expected_industries = [
            "healthcare",
            "insurance",
            "automobile",
            "finance",
            "technology",
            "retail",
            "education",
        ]
        
        for industry in expected_industries:
            assert industry in INDUSTRY_SEED_TERMS
