import { describe, it, expect } from 'vitest'
import {
  isGridAligned,
  snapToGrid,
  GRID_UNIT,
  spacing,
  VALID_SPACING_TOKENS,
  VALID_TYPOGRAPHY_TOKENS,
  VALID_THEME_NAMES,
  themes,
} from '../styles/tokens'

// ---------------------------------------------------------------------------
// 8px Grid Enforcement
// ---------------------------------------------------------------------------

describe('isGridAligned', () => {
  it('returns true for 0', () => expect(isGridAligned(0)).toBe(true))
  it('returns true for 4 (fine-grained unit)', () => expect(isGridAligned(4)).toBe(true))
  it('returns true for multiples of 8', () => {
    ;[8, 16, 24, 32, 40, 48, 64, 80, 96].forEach(v => expect(isGridAligned(v)).toBe(true))
  })
  it('returns false for non-grid values', () => {
    ;[1, 3, 5, 6, 7, 9, 10, 11, 13, 15].forEach(v => expect(isGridAligned(v)).toBe(false))
  })
})

describe('snapToGrid', () => {
  it('snaps 0 to 0', () => expect(snapToGrid(0)).toBe(0))
  it('snaps negative to 0', () => expect(snapToGrid(-5)).toBe(0))
  it('preserves 4 as fine-grained unit', () => expect(snapToGrid(4)).toBe(4))
  it('snaps 5 to 8', () => expect(snapToGrid(5)).toBe(8))
  it('snaps 12 to 8', () => expect(snapToGrid(12)).toBe(8))
  it('snaps 13 to 16', () => expect(snapToGrid(13)).toBe(16))
  it('snaps 20 to 24', () => expect(snapToGrid(20)).toBe(24))
  it('leaves already-aligned values unchanged', () => {
    ;[8, 16, 24, 32, 40, 48, 64].forEach(v => expect(snapToGrid(v)).toBe(v))
  })
})

describe('GRID_UNIT', () => {
  it('is 8', () => expect(GRID_UNIT).toBe(8))
})

// ---------------------------------------------------------------------------
// Spacing tokens are grid-aligned
// ---------------------------------------------------------------------------

describe('spacing tokens', () => {
  it('all spacing values are grid-aligned', () => {
    Object.entries(spacing).forEach(([key, value]) => {
      const px = parseInt(value, 10)
      expect(isGridAligned(px), `spacing['${key}'] = ${value} is not grid-aligned`).toBe(true)
    })
  })
})

// ---------------------------------------------------------------------------
// Token name sets
// ---------------------------------------------------------------------------

describe('VALID_SPACING_TOKENS', () => {
  it('contains all spacing keys', () => {
    Object.keys(spacing).forEach(k => expect(VALID_SPACING_TOKENS.has(k)).toBe(true))
  })
})

describe('VALID_TYPOGRAPHY_TOKENS', () => {
  it('contains required typography tokens', () => {
    ;['slide-title', 'slide-subtitle', 'slide-body', 'slide-caption'].forEach(t =>
      expect(VALID_TYPOGRAPHY_TOKENS.has(t)).toBe(true)
    )
  })
})

describe('VALID_THEME_NAMES', () => {
  it('contains all three themes', () => {
    ;['mckinsey', 'deloitte', 'dark-modern'].forEach(t =>
      expect(VALID_THEME_NAMES.has(t as any)).toBe(true)
    )
  })
})

// ---------------------------------------------------------------------------
// Theme palettes completeness
// ---------------------------------------------------------------------------

describe('themes', () => {
  const requiredKeys = ['primary', 'secondary', 'accent', 'bg', 'surface', 'text', 'muted', 'border', 'highlight']

  ;(['mckinsey', 'deloitte', 'dark-modern'] as const).forEach(theme => {
    it(`${theme} has all required color keys`, () => {
      requiredKeys.forEach(key =>
        expect(themes[theme]).toHaveProperty(key)
      )
    })
  })
})
