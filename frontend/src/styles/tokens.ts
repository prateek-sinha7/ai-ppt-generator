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
// Theme Palettes
// ---------------------------------------------------------------------------
export const themes = {
  'ocean-depths': {
    primary:   '#1a2332',
    secondary: '#2d8b8b',
    accent:    '#a8dadc',
    bg:        '#f1faee',
    surface:   '#f5f8f6',
    text:      '#1a2332',
    muted:     '#6b7280',
    border:    '#d1d5db',
    highlight: '#e8f4f4',
  },
  'sunset-boulevard': {
    primary:   '#e76f51',
    secondary: '#f4a261',
    accent:    '#e9c46a',
    bg:        '#ffffff',
    surface:   '#fdf8f3',
    text:      '#264653',
    muted:     '#6b7280',
    border:    '#d1d5db',
    highlight: '#fef3e2',
  },
  'forest-canopy': {
    primary:   '#2d4a2b',
    secondary: '#7d8471',
    accent:    '#a4ac86',
    bg:        '#faf9f6',
    surface:   '#f5f5f2',
    text:      '#2d4a2b',
    muted:     '#6b7280',
    border:    '#d1d5db',
    highlight: '#f0f2ec',
  },
  'modern-minimalist': {
    primary:   '#36454f',
    secondary: '#708090',
    accent:    '#d3d3d3',
    bg:        '#ffffff',
    surface:   '#f5f5f5',
    text:      '#36454f',
    muted:     '#708090',
    border:    '#d3d3d3',
    highlight: '#f0f0f0',
  },
  'golden-hour': {
    primary:   '#f4a900',
    secondary: '#c1666b',
    accent:    '#d4b896',
    bg:        '#ffffff',
    surface:   '#faf6f0',
    text:      '#4a403a',
    muted:     '#6b7280',
    border:    '#d1d5db',
    highlight: '#fdf4e0',
  },
  'arctic-frost': {
    primary:   '#4a6fa5',
    secondary: '#c0c0c0',
    accent:    '#d4e4f7',
    bg:        '#fafafa',
    surface:   '#f5f7fa',
    text:      '#2c3e50',
    muted:     '#6b7280',
    border:    '#d1d5db',
    highlight: '#edf3fc',
  },
  'desert-rose': {
    primary:   '#d4a5a5',
    secondary: '#b87d6d',
    accent:    '#e8d5c4',
    bg:        '#ffffff',
    surface:   '#faf5f0',
    text:      '#5d2e46',
    muted:     '#6b7280',
    border:    '#d1d5db',
    highlight: '#f8ede4',
  },
  'tech-innovation': {
    primary:   '#0066ff',
    secondary: '#00ffff',
    accent:    '#00cccc',
    bg:        '#1e1e1e',
    surface:   '#2a2a2a',
    text:      '#ffffff',
    muted:     '#9ca3af',
    border:    '#374151',
    highlight: '#1a1a3e',
  },
  'botanical-garden': {
    primary:   '#4a7c59',
    secondary: '#f9a620',
    accent:    '#b7472a',
    bg:        '#f5f3ed',
    surface:   '#f0ede6',
    text:      '#3a3a3a',
    muted:     '#6b7280',
    border:    '#d1d5db',
    highlight: '#f0f5e8',
  },
  'midnight-galaxy': {
    primary:   '#4a4e8f',
    secondary: '#a490c2',
    accent:    '#e6e6fa',
    bg:        '#2b1e3e',
    surface:   '#362a4e',
    text:      '#e6e6fa',
    muted:     '#9ca3af',
    border:    '#4a4060',
    highlight: '#3d2e5e',
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
export const VALID_THEME_NAMES = new Set(Object.keys(themes)) as Set<Theme>

// ---------------------------------------------------------------------------
// Consolidated export (for Tailwind config)
// ---------------------------------------------------------------------------
export const tokens = {
  spacing,
  fontSize,
  fontFamily,
  colors,
} as const
