"use strict";

const vm = require("vm");
const { iconToBase64 } = require("./icons");
const { buildThemePalette, getAllThemePalettes } = require("./theme-palette");

// ─── CONSTANTS ────────────────────────────────────────────────────────────────

/** Maximum execution time per slide in milliseconds. */
const EXECUTION_TIMEOUT_MS = 10_000;

// ─── HELPERS ──────────────────────────────────────────────────────────────────

/**
 * Create a safe console object that only exposes log, warn, and error.
 * Output goes to the server's stdout/stderr for debugging.
 */
function makeSafeConsole() {
  return {
    log:   (...args) => console.log("[sandbox]", ...args),
    warn:  (...args) => console.warn("[sandbox]", ...args),
    error: (...args) => console.error("[sandbox]", ...args),
  };
}

/**
 * Race a promise against a timeout. Rejects with a timeout error if the
 * promise does not settle within `ms` milliseconds.
 *
 * @param {Promise} promise
 * @param {number}  ms
 * @returns {Promise}
 */
function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`Slide execution timed out after ${ms}ms`));
    }, ms);

    promise.then(
      (val) => { clearTimeout(timer); resolve(val); },
      (err) => { clearTimeout(timer); reject(err); },
    );
  });
}

// ─── MAIN EXECUTOR ────────────────────────────────────────────────────────────

/**
 * Execute LLM-generated pptxgenjs code inside a sandboxed Node.js VM context.
 *
 * The code is wrapped in an async IIFE that receives only the allowed objects
 * as parameters. The sandbox context has NO access to require, process, global,
 * globalThis, Buffer, or any other Node.js built-ins.
 *
 * @param {string}  code        – JavaScript function body (pptxgenjs API calls)
 * @param {object}  slide       – pptxgenjs Slide object
 * @param {object}  pres        – pptxgenjs Presentation object (for enums)
 * @param {object}  designSpec  – LLM design spec (colors, fonts, motif)
 * @param {string}  theme       – Theme name (e.g. "ocean_depths")
 * @param {number}  [slideIndex=0] – Zero-based slide index for error reporting
 * @returns {Promise<{ success: boolean, error?: string, slideIndex: number }>}
 */
async function executeSlideCode(code, slide, pres, designSpec, theme, slideIndex = 0) {
  try {
    // ── Build theme palette and fonts ───────────────────────────────────
    const themePalette = buildThemePalette(designSpec, theme);
    const allThemes = getAllThemePalettes();

    // Resolve fonts from the design spec / theme palette
    // resolveDesign (called inside buildThemePalette path) puts fontHeader
    // and fontBody on the resolved object, but our ThemePalette strips them.
    // We pull fonts from the full resolved design instead.
    const { resolveDesign } = require("./builder");
    const normalizedTheme = (theme || "ocean_depths").replace(/-/g, "_");
    const resolved = resolveDesign(designSpec, normalizedTheme);
    const fonts = {
      fontHeader: resolved.fontHeader,
      fontBody:   resolved.fontBody,
    };

    // ── Create minimal sandbox context ──────────────────────────────────
    // Only the objects the LLM code is allowed to access are placed here.
    // No require, process, global, globalThis, Buffer, or Node.js built-ins.
    const sandbox = {
      slide,
      pres,
      theme:        themePalette,
      fonts,
      themes:       allThemes,
      iconToBase64,
      console:      makeSafeConsole(),
      // Promise must be available for async/await to work inside the VM
      Promise,
    };

    const context = vm.createContext(sandbox);

    // ── Wrap code in an async IIFE ──────────────────────────────────────
    // The IIFE receives the allowed objects as parameters so the LLM code
    // can reference them by name. The wrapper returns a Promise.
    const wrappedCode = `
(async function(slide, pres, theme, fonts, themes, iconToBase64) {
${code}
})(slide, pres, theme, fonts, themes, iconToBase64);
`;

    // ── Compile and execute ─────────────────────────────────────────────
    const script = new vm.Script(wrappedCode, {
      filename: `slide_${slideIndex}.js`,
      timeout:  EXECUTION_TIMEOUT_MS,  // sync compilation/startup timeout
    });

    // runInContext returns the Promise from the async IIFE.
    // We use script.runInContext with a timeout for the synchronous part,
    // then await the returned promise with our own timeout for the async part.
    const resultPromise = script.runInContext(context, {
      timeout: EXECUTION_TIMEOUT_MS,
    });

    // Await the async IIFE's promise with a timeout
    await withTimeout(resultPromise, EXECUTION_TIMEOUT_MS);

    return { success: true, slideIndex };
  } catch (err) {
    const message = err && err.message ? err.message : String(err);
    return { success: false, error: `Slide ${slideIndex}: ${message}`, slideIndex };
  }
}

// ─── EXPORTS ──────────────────────────────────────────────────────────────────

module.exports = { executeSlideCode, EXECUTION_TIMEOUT_MS };
