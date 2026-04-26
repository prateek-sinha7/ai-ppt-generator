// Theme utility functions for accessing theme colors and styles

import { Theme, themes } from '../styles/tokens'
import { DesignSpec } from '../types'

// The resolved color set used by all slide components
export interface SlideColors {
  primary: string
  secondary: string
  accent: string
  bg: string
  bgDark: string   // dark background for title + conclusion slides
  surface: string
  text: string
  muted: string
  border: string
  highlight: string
  chartColors: string[]
}

/**
 * Get theme colors for a given theme name (static fallback)
 */
export function getThemeColors(theme: Theme): SlideColors {
  const t = themes[theme]
  const bgDarkMap: Record<Theme, string> = {
    'hexaware_corporate':    '#060F1E',
    'hexaware_professional': '#000000',
  }
  return {
    ...t,
    bgDark: bgDarkMap[theme],
    chartColors: [t.primary, t.secondary, t.accent, t.muted],
  }
}

/**
 * Resolve colors from the Hexaware theme. DesignSpec colors are intentionally
 * ignored — the Hexaware brand palette is fixed. Only the theme name matters.
 */
export function resolveColors(theme: Theme, _designSpec?: DesignSpec | null): SlideColors {
  return getThemeColors(theme)
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
