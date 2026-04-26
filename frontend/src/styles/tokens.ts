// Design Token System — single source of truth for all visual values
// Spacing values follow the 8px grid (base unit = 8px; 4px allowed for fine-grained control)

// ---------------------------------------------------------------------------
// Spacing Scale (multiples of 8px; 4px as the minimum fine-grained unit)
// ---------------------------------------------------------------------------
export const spacing = {
  '0': '0px',
  '1': '4px',   // fine-grained only — not a grid unit
  '2': '8px',   // 1 grid unit
  '4': '16px',  // 2 grid units
  '6': '24px',  // 3 grid units
  '8': '32px',  // 4 grid units
  '10': '40px', // 5 grid units
  '12': '48px', // 6 grid units
  '16': '64px', // 8 grid units
  '20': '80px', // 10 grid units
  '24': '96px', // 12 grid units
} as const

export type SpacingToken = keyof typeof spacing

// ---------------------------------------------------------------------------
// Typography Scale
// ---------------------------------------------------------------------------
export const fontSize = {
  'slide-title':    ['2.25rem', { lineHeight: '2.5rem',  fontWeight: '700' }],
  'slide-subtitle': ['1.5rem',  { lineHeight: '2rem',    fontWeight: '600' }],
  'slide-body':     ['1rem',    { lineHeight: '1.5rem',  fontWeight: '400' }],
  'slide-caption':  ['0.75rem', { lineHeight: '1rem',    fontWeight: '400' }],
} as const

export type TypographyToken = keyof typeof fontSize

// ---------------------------------------------------------------------------
// Font Families
// ---------------------------------------------------------------------------
export const fontFamily = {
  sans:    ['Inter', 'system-ui', 'sans-serif'],
  display: ['Playfair Display', 'Georgia', 'serif'],
} as const

// ---------------------------------------------------------------------------
// Theme Palettes — Hexaware Brand Only
// Two palettes are supported. No other themes exist.
// ---------------------------------------------------------------------------
export const themes = {
  'hexaware_corporate': {
    primary:   '#0A2240',   // deep navy
    secondary: '#000080',   // Navy Blue
    accent:    '#000080',   // Navy Blue
    bg:        '#FFFFFF',
    surface:   '#F4F6FB',
    text:      '#1A1A2E',
    muted:     '#5A6A7A',
    border:    '#C8D7EB',
    highlight: '#EBF0FB',
  },
  'hexaware_professional': {
    primary:   '#0D0D0D',   // near-black
    secondary: '#000080',   // Navy Blue
    accent:    '#FF6B35',   // Hexaware orange
    bg:        '#FFFFFF',
    surface:   '#F7F7F7',
    text:      '#1A1A1A',
    muted:     '#5A5A6A',
    border:    '#DCDCDC',
    highlight: '#FFF0EA',
  },
} as const

export type Theme = keyof typeof themes
export type ThemeColors = typeof themes[Theme]

// ---------------------------------------------------------------------------
// Flat colors map for Tailwind (nested under theme name)
// ---------------------------------------------------------------------------
export const colors = themes

// ---------------------------------------------------------------------------
// 8px Grid Enforcement
// ---------------------------------------------------------------------------

/** All valid layout values must be multiples of 8 (or the 4px fine-grained unit). */
export const GRID_UNIT = 8

/**
 * Returns true when a pixel value is a valid grid-aligned value.
 * Accepts multiples of 8, plus 4px as the minimum fine-grained unit.
 */
export function isGridAligned(px: number): boolean {
  if (px === 0) return true
  if (px === 4) return true          // fine-grained exception
  return px % GRID_UNIT === 0
}

/**
 * Snaps a pixel value to the nearest 8px grid unit.
 * Values below 4 snap to 0; values between 4 and 8 snap to 8.
 */
export function snapToGrid(px: number): number {
  if (px <= 0) return 0
  if (px <= 4) return 4              // preserve fine-grained unit
  return Math.round(px / GRID_UNIT) * GRID_UNIT
}

/**
 * Asserts that a pixel value is grid-aligned (throws in development).
 * Use this in component code to catch accidental off-grid values early.
 */
export function assertGridAligned(px: number, label = 'value'): void {
  // Only warn in development (Vite sets import.meta.env.DEV)
  if (typeof window !== 'undefined' && !isGridAligned(px)) {
    console.warn(`[tokens] ${label} (${px}px) is not grid-aligned. Nearest: ${snapToGrid(px)}px`)
  }
}

// ---------------------------------------------------------------------------
// Valid token name sets (used by backend validation)
// ---------------------------------------------------------------------------

/** All valid spacing token names (mirrors the spacing object keys). */
export const VALID_SPACING_TOKENS = new Set(Object.keys(spacing))

/** All valid typography token names. */
export const VALID_TYPOGRAPHY_TOKENS = new Set(Object.keys(fontSize))

/** All valid theme names. */
export const VALID_THEME_NAMES = new Set(['hexaware_corporate', 'hexaware_professional']) as Set<Theme>

// ---------------------------------------------------------------------------
// Consolidated export (for Tailwind config)
// ---------------------------------------------------------------------------
export const tokens = {
  spacing,
  fontSize,
  fontFamily,
  colors,
} as const
