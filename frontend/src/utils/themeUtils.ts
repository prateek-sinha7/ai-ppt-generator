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
  // Derive bgDark from the primary color for static themes
  const bgDarkMap: Record<Theme, string> = {
    mckinsey: '#002040',
    deloitte: '#000000',
    'dark-modern': '#0A0A0A',
  }
  return {
    ...t,
    bgDark: bgDarkMap[theme],
    chartColors: [t.primary, t.secondary, t.accent, t.muted],
  }
}

/**
 * Convert a DesignSpec (from DesignAgent) into SlideColors.
 * This makes the browser preview match the exported PPTX palette.
 */
export function designSpecToColors(spec: DesignSpec): SlideColors {
  const hex = (h: string) => (h.startsWith('#') ? h : `#${h}`)
  const chartColors = (spec.chart_colors || []).map(hex)

  return {
    primary:     hex(spec.primary_color),
    secondary:   hex(spec.secondary_color),
    accent:      hex(spec.accent_color),
    bg:          hex(spec.background_color),
    bgDark:      hex(spec.background_dark_color),
    surface:     lighten(hex(spec.background_color), 0.04),
    text:        hex(spec.text_color),
    muted:       hex(spec.text_light_color),
    border:      lighten(hex(spec.text_light_color), 0.6),
    highlight:   lighten(hex(spec.accent_color), 0.88),
    chartColors: chartColors.length >= 4 ? chartColors : [
      hex(spec.primary_color),
      hex(spec.secondary_color),
      hex(spec.accent_color),
      hex(spec.text_light_color),
    ],
  }
}

/**
 * Resolve colors from either a DesignSpec (preferred) or a static theme name.
 */
export function resolveColors(theme: Theme, designSpec?: DesignSpec | null): SlideColors {
  if (designSpec && designSpec.primary_color) {
    return designSpecToColors(designSpec)
  }
  return getThemeColors(theme)
}

/** Lighten a hex color by mixing it toward white by `amount` (0–1). */
function lighten(hex: string, amount: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  const mix = (c: number) => Math.round(c + (255 - c) * amount)
  return `#${mix(r).toString(16).padStart(2, '0')}${mix(g).toString(16).padStart(2, '0')}${mix(b).toString(16).padStart(2, '0')}`
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
