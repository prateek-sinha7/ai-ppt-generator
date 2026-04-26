"""
Test that the Navy Blue color (#000080) is correctly applied in the Hexaware themes.
"""

import pytest
from pptx.dml.color import RGBColor
from app.services.pptx_export import ThemeColors
from app.agents.design_agent import FALLBACK_PALETTES


class TestClassicBlueColor:
    """Test that Classic Blue color is correctly applied across all components."""

    def test_hexaware_corporate_uses_classic_blue(self):
        """Test that Hexaware Corporate theme uses Navy Blue (#000080)."""
        theme = ThemeColors.HEXAWARE_CORPORATE
        
        # Check that secondary and accent colors use Navy Blue RGB values
        # #000080 = RGB(0, 0, 128)
        # RGBColor is tuple-like, so we can compare directly
        assert theme["secondary"] == RGBColor(0, 0, 128), "Secondary color should be Navy Blue #000080"
        assert theme["accent"] == RGBColor(0, 0, 128), "Accent color should be Navy Blue #000080"
        
        # Check that Navy Blue is the primary chart color
        assert theme["chart_colors"][0] == RGBColor(0, 0, 128), "First chart color should be Navy Blue #000080"

    def test_hexaware_professional_uses_classic_blue(self):
        """Test that Hexaware Professional theme uses Navy Blue (#000080)."""
        theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # Check that secondary color uses Navy Blue
        assert theme["secondary"] == RGBColor(0, 0, 128), "Secondary color should be Navy Blue #000080"
        
        # Check that Navy Blue is the second chart color (after orange)
        assert theme["chart_colors"][1] == RGBColor(0, 0, 128), "Second chart color should be Navy Blue #000080"

    def test_design_specs_use_classic_blue(self):
        """Test that design specs use Navy Blue color codes."""
        corporate_spec = FALLBACK_PALETTES["hexaware_corporate"]
        professional_spec = FALLBACK_PALETTES["hexaware_professional"]
        
        # Check Corporate theme
        assert corporate_spec.secondary_color == "000080", "Corporate secondary should be Navy Blue"
        assert corporate_spec.accent_color == "000080", "Corporate accent should be Navy Blue"
        assert "000080" in corporate_spec.chart_colors, "Corporate chart colors should include Navy Blue"
        
        # Check Professional theme
        assert professional_spec.secondary_color == "000080", "Professional secondary should be Navy Blue"
        assert "000080" in professional_spec.chart_colors, "Professional chart colors should include Navy Blue"

    def test_no_old_blue_colors_remain(self):
        """Test that old blue colors (2B5CE6, 1A3FB0) are not used anywhere."""
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        professional_theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # Check that old colors are not in any theme
        old_electric_blue = RGBColor(43, 92, 230)  # #2B5CE6
        old_medium_blue = RGBColor(26, 63, 176)    # #1A3FB0
        
        for color_name, color_obj in corporate_theme.items():
            if isinstance(color_obj, RGBColor):
                assert color_obj != old_electric_blue, f"Corporate {color_name} should not use old electric blue"
                assert color_obj != old_medium_blue, f"Corporate {color_name} should not use old medium blue"
            elif isinstance(color_obj, list):  # chart_colors
                for chart_color in color_obj:
                    if isinstance(chart_color, RGBColor):
                        assert chart_color != old_electric_blue, f"Corporate chart color should not use old electric blue"
                        assert chart_color != old_medium_blue, f"Corporate chart color should not use old medium blue"
        
        for color_name, color_obj in professional_theme.items():
            if isinstance(color_obj, RGBColor):
                assert color_obj != old_electric_blue, f"Professional {color_name} should not use old electric blue"
                assert color_obj != old_medium_blue, f"Professional {color_name} should not use old medium blue"
            elif isinstance(color_obj, list):  # chart_colors
                for chart_color in color_obj:
                    if isinstance(chart_color, RGBColor):
                        assert chart_color != old_electric_blue, f"Professional chart color should not use old electric blue"
                        assert chart_color != old_medium_blue, f"Professional chart color should not use old medium blue"

    def test_classic_blue_rgb_values(self):
        """Test that Navy Blue RGB values are correct."""
        # #000080 = RGB(0, 0, 128)
        expected_rgb = RGBColor(0, 0, 128)
        
        corporate_theme = ThemeColors.HEXAWARE_CORPORATE
        professional_theme = ThemeColors.HEXAWARE_PROFESSIONAL
        
        # Test Corporate theme
        assert corporate_theme["secondary"] == expected_rgb
        assert corporate_theme["accent"] == expected_rgb
        assert corporate_theme["chart_colors"][0] == expected_rgb
        
        # Test Professional theme
        assert professional_theme["secondary"] == expected_rgb
        assert professional_theme["chart_colors"][1] == expected_rgb