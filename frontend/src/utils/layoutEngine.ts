/**
 * Layout Decision Engine — Frontend mirror of backend/app/agents/layout_engine.py
 *
 * Provides deterministic layout utilities for the frontend rendering layer.
 * All layout decisions originate from the backend (visual_hint, layout_instructions).
 * This module provides helpers for interpreting those decisions consistently.
 *
 * References: Req 14, 15, 17, 18 | Design: Design Intelligence Layer
 */

import {
  spacing,
  fontSize,
  themes,
  VALID_SPACING_TOKENS,
  VALID_TYPOGRAPHY_TOKENS,
  VALID_THEME_NAMES,
  type SpacingToken,
  type TypographyToken,
  type Theme,
} from '../styles/tokens'
import type { SlideType, VisualHint, SlideData } from '../types'

// ---------------------------------------------------------------------------
// 23.1 — Layout Mapping Rules
// ---------------------------------------------------------------------------

/** Canonical mapping: slide type → visual hint (mirrors LAYOUT_MAPPING in backend) */
export const LAYOUT_MAPPING: Record<SlideType, VisualHint> = {
  title:      'centered',
  content:    'bullet-left',
  chart:      'split-chart-right',
  table:      'split-table-left',
  comparison: 'two-column',
  metric:     'highlight-metric',
}

/**
 * Map a slide type to its canonical visual hint.
 * Falls back to 'bullet-left' for unknown types.
 */
export function mapSlideTypeToVisualHint(slideType: SlideType | string): VisualHint {
  return (LAYOUT_MAPPING as Record<string, VisualHint>)[slideType] ?? 'bullet-left'
}

// ---------------------------------------------------------------------------
// 23.2 — Content Density Calculation
// ---------------------------------------------------------------------------

export interface DensityResult {
  density: number
  whitespaceRatio: number
  exceedsMax: boolean
  belowMinWhitespace: boolean
  bulletCount: number
  hasChart: boolean
  hasTable: boolean
}

const MAX_CONTENT_DENSITY = 0.75
const MIN_WHITESPACE_RATIO = 0.25

/**
 * Calculate content density for a slide.
 * Mirrors the Python calculate_content_density() function.
 */
export function calculateContentDensity(slide: SlideData): DensityResult {
  const bullets = slide.bullets ?? []
  const hasChart = Boolean(slide.chart_data)
  const hasTable = Boolean(slide.table_rows)

  let density = 0.10 // base for title
  density += Math.min(bullets.length, 4) * 0.15
  if (hasChart) density += 0.40
  if (hasTable) density += 0.40
  density = Math.min(density, 1.0)

  const whitespaceRatio = 1.0 - density

  return {
    density: Math.round(density * 10000) / 10000,
    whitespaceRatio: Math.round(whitespaceRatio * 10000) / 10000,
    exceedsMax: density > MAX_CONTENT_DENSITY,
    belowMinWhitespace: whitespaceRatio < MIN_WHITESPACE_RATIO,
    bulletCount: bullets.length,
    hasChart,
    hasTable,
  }
}

// ---------------------------------------------------------------------------
// 23.3 — Dynamic Font Size Resolution
// ---------------------------------------------------------------------------

/** Font size scale in descending order (largest → smallest) */
const FONT_SIZE_SCALE: TypographyToken[] = [
  'slide-title',
  'slide-subtitle',
  'slide-body',
  'slide-caption',
]

/**
 * Resolve the effective font size CSS value from a token name.
 * Falls back to slide-body if the token is unknown.
 */
export function resolveFontSizeToken(token: string): string {
  const validToken = VALID_TYPOGRAPHY_TOKENS.has(token as TypographyToken)
    ? (token as TypographyToken)
    : 'slide-body'
  const entry = fontSize[validToken]
  return Array.isArray(entry) ? entry[0] : String(entry)
}

/**
 * Get the adjusted font size token when content density is high.
 * Steps down the scale by one level; never goes below slide-caption.
 */
export function getAdjustedFontToken(
  slide: SlideData,
  currentToken: TypographyToken = 'slide-body',
): TypographyToken {
  const { exceedsMax } = calculateContentDensity(slide)
  if (!exceedsMax) return currentToken

  const idx = FONT_SIZE_SCALE.indexOf(currentToken)
  const nextIdx = Math.min(idx + 1, FONT_SIZE_SCALE.length - 1)
  return FONT_SIZE_SCALE[nextIdx]
}

// ---------------------------------------------------------------------------
// 23.5 — layout_instructions Resolution
// ---------------------------------------------------------------------------

export interface ResolvedLayoutInstructions {
  padding: string       // CSS value
  gap: string           // CSS value
  columnGap?: string    // CSS value (split layouts only)
  fontSize: string      // CSS value
  titleFontSize: string // CSS value
  theme: Theme
}

/**
 * Resolve layout_instructions token names to concrete CSS values.
 *
 * The backend generates layout_instructions as token name strings.
 * This function converts them to actual CSS values for rendering.
 *
 * Falls back to sensible defaults if a token is missing or invalid.
 */
export function resolveLayoutInstructions(
  slide: SlideData,
  fallbackTheme: Theme = 'ocean-depths',
): ResolvedLayoutInstructions {
  const instructions = slide.layout_instructions ?? {}

  const resolveSpacing = (key: string, fallback: SpacingToken): string => {
    const token = instructions[key]
    if (token && VALID_SPACING_TOKENS.has(token as SpacingToken)) {
      return spacing[token as SpacingToken]
    }
    return spacing[fallback]
  }

  const resolveTypography = (key: string, fallback: TypographyToken): string => {
    const token = instructions[key]
    if (token && VALID_TYPOGRAPHY_TOKENS.has(token as TypographyToken)) {
      return resolveFontSizeToken(token)
    }
    return resolveFontSizeToken(fallback)
  }

  const resolveTheme = (): Theme => {
    const token = instructions['theme']
    if (token && VALID_THEME_NAMES.has(token as Theme)) {
      return token as Theme
    }
    return fallbackTheme
  }

  const resolved: ResolvedLayoutInstructions = {
    padding:       resolveSpacing('padding', '6'),
    gap:           resolveSpacing('gap', '4'),
    fontSize:      resolveTypography('font_size', 'slide-body'),
    titleFontSize: resolveTypography('title_font_size', 'slide-subtitle'),
    theme:         resolveTheme(),
  }

  const columnGapToken = instructions['column_gap']
  if (columnGapToken) {
    resolved.columnGap = resolveSpacing('column_gap', '4')
  }

  return resolved
}

// ---------------------------------------------------------------------------
// 23.4 — Layout Scoring (client-side validation helper)
// ---------------------------------------------------------------------------

export interface ClientLayoutScore {
  slideId: string
  typeHintMatch: boolean
  densityOk: boolean
  recommendations: string[]
}

/**
 * Lightweight client-side layout validation.
 * Used for development-time warnings — not a replacement for backend scoring.
 */
export function validateSlideLayout(slide: SlideData): ClientLayoutScore {
  const recommendations: string[] = []

  // Check visual_hint matches canonical mapping
  const expectedHint = mapSlideTypeToVisualHint(slide.type)
  const typeHintMatch = slide.visual_hint === expectedHint
  if (!typeHintMatch) {
    recommendations.push(
      `visual_hint '${slide.visual_hint}' should be '${expectedHint}' for type '${slide.type}'`,
    )
  }

  // Check density
  const density = calculateContentDensity(slide)
  const densityOk = !density.exceedsMax && !density.belowMinWhitespace
  if (density.exceedsMax) {
    recommendations.push(
      `Content density ${density.density.toFixed(2)} exceeds max ${MAX_CONTENT_DENSITY}`,
    )
  }

  return {
    slideId: slide.id,
    typeHintMatch,
    densityOk,
    recommendations,
  }
}

// ---------------------------------------------------------------------------
// Convenience: get theme colors for a slide
// ---------------------------------------------------------------------------

/**
 * Get the theme color palette for a slide based on its layout_instructions.
 */
export function getSlideThemeColors(slide: SlideData, fallbackTheme: Theme = 'ocean-depths') {
  const { theme } = resolveLayoutInstructions(slide, fallbackTheme)
  return themes[theme]
}
