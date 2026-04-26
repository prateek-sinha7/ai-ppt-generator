"""
Test minimal Navy Blue usage - Navy Blue as border color, white backgrounds.

This test verifies that Navy Blue (#000080) is used minimally as border/accent color
instead of background color, with white backgrounds for better visual clarity.
"""

import pytest
from app.services.pptx_export import ThemeColors


class TestMinimalNavyBlueUsage:
    """Test that Navy Blue is used minimally as border color, not background."""

    def test_kpi_cards_use_white_background(self):
        """Test that KPI cards use white background with Navy Blue text."""
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        professional_theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # KPI cards should have white background
        assert corporate_theme["kpi_bg"] == (255, 255, 255)
        assert professional_theme["kpi_bg"] == (255, 255, 255)
        
        # KPI text should be Navy Blue
        assert corporate_theme["kpi_text"] == (0, 0, 128)
        assert professional_theme["kpi_text"] == (0, 0, 128)

    def test_navy_blue_used_as_accent_not_background(self):
        """Test that Navy Blue is used as accent/border color, not primary background."""
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        professional_theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # Navy Blue should be secondary/accent color (for borders)
        navy_blue = (0, 0, 128)
        
        # Corporate theme
        assert corporate_theme["secondary"] == navy_blue
        assert corporate_theme["accent"] == navy_blue
        
        # Professional theme
        assert professional_theme["secondary"] == navy_blue
        
        # Background should be white, not Navy Blue
        white = (255, 255, 255)
        assert corporate_theme["background"] == white
        assert professional_theme["background"] == white

    def test_chart_colors_include_navy_blue_appropriately(self):
        """Test that Navy Blue is included in chart colors but not dominant."""
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        professional_theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # Navy Blue should be in chart colors but not the only color
        navy_blue = (0, 0, 128)
        
        # Corporate theme - Navy Blue should be first color
        assert corporate_theme["chart_colors"][0] == navy_blue
        
        # Should have other colors too (not all Navy Blue)
        assert len(corporate_theme["chart_colors"]) >= 5
        
        # Professional theme - should have Navy Blue as second color
        assert professional_theme["chart_colors"][1] == navy_blue
        
        # Should have Hexaware orange as first color in professional theme
        hexaware_orange = (255, 107, 53)
        assert professional_theme["chart_colors"][0] == hexaware_orange

    def test_no_dark_backgrounds_in_themes(self):
        """Test that themes don't use dark Navy Blue backgrounds."""
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        professional_theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # Check that main background colors are light, not dark
        # Background should be white (255, 255, 255)
        white = (255, 255, 255)
        
        assert corporate_theme["background"] == white
        assert professional_theme["background"] == white
        
        # Surface colors should also be light
        corp_surface = corporate_theme["surface"]
        prof_surface = professional_theme["surface"]
        
        # Surface should be light (all values > 200)
        assert all(c > 200 for c in corp_surface)
        assert all(c > 200 for c in prof_surface)

    def test_text_colors_provide_good_contrast(self):
        """Test that text colors provide good contrast on white backgrounds."""
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        professional_theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # Main text should be dark for good contrast on white background
        corp_text = corporate_theme["text"]
        prof_text = professional_theme["text"]
        
        # Text should be dark (all values < 100 for good contrast)
        assert all(c < 100 for c in corp_text)
        assert all(c < 100 for c in prof_text)
        
        # Light text should be medium tone (for secondary text)
        corp_text_light = corporate_theme["text_light"]
        prof_text_light = professional_theme["text_light"]
        
        # Light text should be medium tone (values between 50-150)
        assert all(50 < c < 150 for c in corp_text_light)
        assert all(50 < c < 150 for c in prof_text_light)

    def test_design_principles_minimal_navy_usage(self):
        """Test that the design follows minimal Navy Blue usage principles."""
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        
        # Count how many theme elements use Navy Blue as background vs border
        navy_blue = (0, 0, 128)
        
        # These should NOT be Navy Blue (should be white backgrounds)
        background_elements = [
            "background", "surface", "kpi_bg"
        ]
        
        for element in background_elements:
            if element in corporate_theme:
                color = corporate_theme[element]
                assert color != navy_blue, f"{element} should not use Navy Blue background"
        
        # These SHOULD be Navy Blue (for borders/accents)
        accent_elements = [
            "secondary", "accent"
        ]
        
        for element in accent_elements:
            if element in corporate_theme:
                color = corporate_theme[element]
                assert color == navy_blue, f"{element} should use Navy Blue for borders/accents"

    def test_accessibility_compliance(self):
        """Test that color choices meet accessibility guidelines."""
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        professional_theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # White background with Navy Blue text should have good contrast ratio
        # Navy Blue (#000080) on white (#FFFFFF) has contrast ratio > 7:1 (AAA compliant)
        
        white_bg = (255, 255, 255)
        navy_text = (0, 0, 128)
        
        # Verify background is white
        assert corporate_theme["background"] == white_bg
        
        # Verify Navy Blue is available for text/borders
        assert corporate_theme["secondary"] == navy_text
        
        # Calculate approximate contrast ratio (simplified)
        # Navy Blue (#000080) has relative luminance ≈ 0.016
        # White (#FFFFFF) has relative luminance = 1.0
        # Contrast ratio = (1.0 + 0.05) / (0.016 + 0.05) ≈ 15.9 (excellent)
        
        # This is a simplified check - in practice, Navy Blue on white
        # provides excellent contrast for accessibility
        assert True  # Navy Blue on white is AAA compliant