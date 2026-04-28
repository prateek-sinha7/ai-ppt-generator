"use strict";

const { resolveDesign, THEMES } = require("./builder");

// ─── THEME PALETTE BUILDER ────────────────────────────────────────────────────
// Maps the full internal palette from resolveDesign() to the simplified
// ThemePalette interface used by the sandbox execution context.
//
// ThemePalette fields:
//   primary, secondary, accent, bg, bgDark, surface, text, muted,
//   border, highlight, chartColors

/**
 * Normalize a theme name so both hyphens and underscores resolve to the
 * same built-in key (e.g. "ocean-depths" → "ocean_depths").
 */
function normalizeThemeName(name) {
  if (!name || typeof name !== "string") return "ocean_depths";
  return name.replace(/-/g, "_");
}

/**
 * Map a resolved palette (from resolveDesign) to the simplified ThemePalette
 * interface consumed by the code-execution sandbox.
 */
function toThemePalette(resolved) {
  return {
    primary:     resolved.primary,
    secondary:   resolved.secondary,
    accent:      resolved.accent,
    bg:          resolved.bg,
    bgDark:      resolved.bgDark,
    surface:     resolved.cardBg,      // surface = cardBg
    text:        resolved.text,
    muted:       resolved.slateL,      // muted   = slateL
    border:      resolved.slate,       // border  = slate
    highlight:   resolved.gold,        // highlight = gold (accent in most themes)
    chartColors: resolved.chartColors,
  };
}

/**
 * Build a ThemePalette for a given designSpec + theme name.
 *
 * @param {object|null} designSpec  – LLM design spec overrides (may be null)
 * @param {string}      theme       – theme name (hyphens or underscores)
 * @returns {ThemePalette}
 */
function buildThemePalette(designSpec, theme) {
  const normalized = normalizeThemeName(theme);
  const resolved = resolveDesign(designSpec, normalized);
  return toThemePalette(resolved);
}

/**
 * Return all 10 built-in themes as a lookup object keyed by theme name
 * (underscore format). Each value is a ThemePalette.
 *
 * @returns {Record<string, ThemePalette>}
 */
function getAllThemePalettes() {
  const palettes = {};
  for (const name of Object.keys(THEMES)) {
    // Pass null designSpec so we get the pure built-in palette
    const resolved = resolveDesign(null, name);
    palettes[name] = toThemePalette(resolved);
  }
  return palettes;
}

module.exports = { buildThemePalette, getAllThemePalettes };
