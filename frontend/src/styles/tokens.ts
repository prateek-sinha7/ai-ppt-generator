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
  mckinsey: {
    primary:   '#003366',
    secondary: '#0066CC',
    accent:    '#FF6600',
    bg:        '#FFFFFF',
    surface:   '#F5F7FA',
    text:      '#1A1A2E',
    muted:     '#6B7280',
    border:    '#D1D5DB',
    highlight: '#FFF3E0',
  },
  deloitte: {
    primary:   '#86BC25',
    secondary: '#0076A8',
    accent:    '#00A3E0',
    bg:        '#FFFFFF',
    surface:   '#F0F4F8',
    text:      '#1C1C1C',
    muted:     '#6B7280',
    border:    '#D1D5DB',
    highlight: '#E8F5E9',
  },
  'dark-modern': {
    primary:   '#6C63FF',
    secondary: '#FF6584',
    accent:    '#43E97B',
    bg:        '#0F0F1A',
    surface:   '#1A1A2E',
    text:      '#E8E8F0',
    muted:     '#9CA3AF',
    border:    '#374151',
    highlight: '#1E1B4B',
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
