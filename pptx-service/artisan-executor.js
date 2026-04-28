"use strict";

const vm = require("vm");
const pptxgen = require("pptxgenjs");
const { iconToBase64 } = require("./icons");
const { buildThemePalette, getAllThemePalettes } = require("./theme-palette");

// ─── CONSTANTS ────────────────────────────────────────────────────────────────

/** Maximum execution time for the entire artisan script in milliseconds. */
const ARTISAN_EXECUTION_TIMEOUT_MS = 60_000;

// ─── HELPERS ──────────────────────────────────────────────────────────────────

/**
 * Create a safe console object that only exposes log, warn, and error.
 * Output goes to the server's stdout/stderr for debugging.
 */
function makeSafeConsole() {
  return {
    log:   (...args) => console.log("[artisan-sandbox]", ...args),
    warn:  (...args) => console.warn("[artisan-sandbox]", ...args),
    error: (...args) => console.error("[artisan-sandbox]", ...args),
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
      reject(new Error(`Script execution timed out after ${ms}ms`));
    }, ms);

    promise.then(
      (val) => { clearTimeout(timer); resolve(val); },
      (err) => { clearTimeout(timer); reject(err); },
    );
  });
}

// ─── MAIN EXECUTOR ────────────────────────────────────────────────────────────

/**
 * Execute LLM-generated Artisan pptxgenjs code inside a sandboxed Node.js VM
 * context.
 *
 * Unlike `executeSlideCode` which operates on a single slide, this executor
 * runs a complete script that receives a `pres` (PptxGenJS presentation)
 * object and is responsible for calling `pres.addSlide()` to create all
 * slides and populate them with content.
 *
 * The code is wrapped in an async IIFE that receives only the allowed objects
 * as parameters. The sandbox context has NO access to require, process, global,
 * globalThis, Buffer, or any other Node.js built-ins.
 *
 * @param {string}  code        – Complete JavaScript function body (full presentation script)
 * @param {object}  designSpec  – LLM design spec (colors, fonts, motif)
 * @param {string}  theme       – Theme name (e.g. "ocean_depths")
 * @returns {Promise<{ result: { success: boolean, error?: string, slideCount?: number }, pres?: object }>}
 */
async function executeArtisanCode(code, designSpec, theme) {
  try {
    // ── Create fresh pptxgenjs presentation instance ──────────────────────
    const pres = new pptxgen();

    // ── Build theme palette and fonts ───────────────────────────────────
    const themePalette = buildThemePalette(designSpec, theme);
    const allThemes = getAllThemePalettes();

    // Resolve fonts from the design spec / theme palette
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
(async function(pres, theme, fonts, themes, iconToBase64) {
${code}
})(pres, theme, fonts, themes, iconToBase64);
`;

    // ── Compile and execute ─────────────────────────────────────────────
    const script = new vm.Script(wrappedCode, {
      filename: "artisan_script.js",
      timeout:  ARTISAN_EXECUTION_TIMEOUT_MS,  // sync compilation/startup timeout
    });

    // runInContext returns the Promise from the async IIFE.
    // We use script.runInContext with a timeout for the synchronous part,
    // then await the returned promise with our own timeout for the async part.
    const resultPromise = script.runInContext(context, {
      timeout: ARTISAN_EXECUTION_TIMEOUT_MS,
    });

    // Await the async IIFE's promise with a timeout
    await withTimeout(resultPromise, ARTISAN_EXECUTION_TIMEOUT_MS);

    // ── Count slides produced ───────────────────────────────────────────
    // pptxgenjs exposes slides via the internal _slides array or the
    // slides getter. We use the length to report how many slides were created.
    const slideCount = pres.slides ? pres.slides.length : 0;

    return {
      result: { success: true, slideCount },
      pres,
    };
  } catch (err) {
    const message = err && err.message ? err.message : String(err);
    return {
      result: { success: false, error: message },
    };
  }
}

// ─── EXPORTS ──────────────────────────────────────────────────────────────────

module.exports = { executeArtisanCode, ARTISAN_EXECUTION_TIMEOUT_MS };
