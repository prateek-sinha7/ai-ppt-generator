// Theme utility functions for accessing theme colors and styles

import { Theme, themes } from '../styles/tokens'

/**
 * Get theme colors for a given theme name
 */
export function getThemeColors(theme: Theme) {
  return themes[theme]
}

/**
 * Get CSS class names for theme-based styling
 */
export function getThemeClasses(theme: Theme) {
  const colors = themes[theme]
  
  return {
    bg: `bg-[${colors.bg}]`,
    surface: `bg-[${colors.surface}]`,
    text: `text-[${colors.text}]`,
    primary: `text-[${colors.primary}]`,
    secondary: `text-[${colors.secondary}]`,
    accent: `text-[${colors.accent}]`,
    muted: `text-[${colors.muted}]`,
    border: `border-[${colors.border}]`,
    highlight: `bg-[${colors.highlight}]`,
  }
}

/**
 * Get inline styles for theme colors (for dynamic styling)
 */
export function getThemeStyles(theme: Theme) {
  const colors = themes[theme]
  
  return {
    backgroundColor: colors.bg,
    color: colors.text,
    borderColor: colors.border,
  }
}

/**
 * Get chart color palette for a theme
 */
export function getChartColors(theme: Theme): string[] {
  const colors = themes[theme]
  
  return [
    colors.primary,
    colors.secondary,
    colors.accent,
    colors.muted,
  ]
}
