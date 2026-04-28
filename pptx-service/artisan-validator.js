"use strict";
const acorn = require("acorn");
const walk = require("acorn-walk");

// ─── CONSTANTS ────────────────────────────────────────────────────────────────

const MAX_ARTISAN_CODE_LENGTH = 500_000;

// Blocked top-level identifiers — any reference to these names is rejected
const BLOCKED_IDENTIFIERS = new Set([
  "process", "child_process", "fs", "net", "http", "https",
  "global", "globalThis", "__dirname", "__filename",
]);

// Blocked function calls — calling these by name is rejected
const BLOCKED_CALLS = new Set([
  "require", "eval", "setTimeout", "setInterval", "setImmediate",
]);

// ─── HELPERS ──────────────────────────────────────────────────────────────────

/**
 * Build a ValidationError object.
 * @param {"blocked_api"|"size_limit"|"no_add_slide"|"syntax_error"} type
 * @param {string} message
 * @param {number} [line]
 * @param {number} [column]
 */
function makeError(type, message, line, column) {
  const err = { type, message };
  if (line != null) err.line = line;
  if (column != null) err.column = column;
  return err;
}

/**
 * Resolve line/column from a node's `start` offset using acorn's loc info.
 * Falls back to undefined when loc is missing.
 */
function loc(node) {
  if (node && node.loc && node.loc.start) {
    return { line: node.loc.start.line, column: node.loc.start.column };
  }
  return { line: undefined, column: undefined };
}

// ─── MAIN VALIDATOR ───────────────────────────────────────────────────────────

/**
 * Validate LLM-generated Artisan pptxgenjs full-presentation code using
 * AST-based static analysis.
 *
 * Unlike the per-slide `validateSlideCode`, this validates a complete script
 * that receives a `pres` object and calls `pres.addSlide()` to create slides.
 *
 * @param {string} code — JavaScript source code for the entire presentation
 * @returns {{ valid: boolean, errors: Array<{ type: string, message: string, line?: number, column?: number }> }}
 */
function validateArtisanCode(code) {
  const errors = [];

  // ── 1. Size limit ───────────────────────────────────────────────────────
  if (typeof code !== "string" || code.length > MAX_ARTISAN_CODE_LENGTH) {
    const len = typeof code === "string" ? code.length : 0;
    errors.push(
      makeError(
        "size_limit",
        `Code exceeds maximum length of ${MAX_ARTISAN_CODE_LENGTH} characters (got ${len})`,
      ),
    );
    // If it's not even a string we can't parse — return early
    if (typeof code !== "string") return { valid: false, errors };
  }

  // ── 2. Parse with acorn ─────────────────────────────────────────────────
  let ast;
  try {
    ast = acorn.parse(code, {
      ecmaVersion: "latest",
      sourceType: "script",
      locations: true,          // gives us line/column on every node
      allowAwaitOutsideFunction: true,
    });
  } catch (parseErr) {
    errors.push(
      makeError(
        "syntax_error",
        parseErr.message,
        parseErr.loc ? parseErr.loc.line : undefined,
        parseErr.loc ? parseErr.loc.column : undefined,
      ),
    );
    return { valid: false, errors };
  }

  // If we already have a size_limit error but parsing succeeded, we still
  // report the size error and skip further analysis.
  if (errors.length > 0) {
    return { valid: false, errors };
  }

  // ── 3. Walk the AST — detect blocked patterns & pres.addSlide() ─────────
  let hasAddSlide = false;

  walk.simple(ast, {
    // ── Import declarations ─────────────────────────────────────────────
    ImportDeclaration(node) {
      const { line, column } = loc(node);
      errors.push(
        makeError("blocked_api", "Import declarations are not allowed", line, column),
      );
    },
    ImportExpression(node) {
      const { line, column } = loc(node);
      errors.push(
        makeError("blocked_api", "Dynamic import() is not allowed", line, column),
      );
    },

    // ── Call expressions ────────────────────────────────────────────────
    CallExpression(node) {
      const callee = node.callee;

      // Check for pres.addSlide() call
      if (
        callee.type === "MemberExpression" &&
        callee.object.type === "Identifier" &&
        callee.object.name === "pres" &&
        callee.property.type === "Identifier" &&
        callee.property.name === "addSlide"
      ) {
        hasAddSlide = true;
      }

      // Direct call: require(), eval(), setTimeout(), etc.
      if (callee.type === "Identifier" && BLOCKED_CALLS.has(callee.name)) {
        const { line, column } = loc(node);
        errors.push(
          makeError("blocked_api", `Call to '${callee.name}()' is not allowed`, line, column),
        );
      }

      // Function(...) constructor call
      if (callee.type === "Identifier" && callee.name === "Function") {
        const { line, column } = loc(node);
        errors.push(
          makeError("blocked_api", "Function constructor is not allowed", line, column),
        );
      }
    },

    // ── new Function(...) via NewExpression ──────────────────────────────
    NewExpression(node) {
      if (node.callee.type === "Identifier" && node.callee.name === "Function") {
        const { line, column } = loc(node);
        errors.push(
          makeError("blocked_api", "Function constructor is not allowed", line, column),
        );
      }
    },

    // ── Identifier references ───────────────────────────────────────────
    Identifier(node) {
      if (BLOCKED_IDENTIFIERS.has(node.name)) {
        const { line, column } = loc(node);
        errors.push(
          makeError(
            "blocked_api",
            `Reference to '${node.name}' is not allowed`,
            line,
            column,
          ),
        );
      }
    },

    // ── Member expressions — catch computed access to blocked names ──────
    MemberExpression(node) {
      if (
        node.computed &&
        node.property.type === "Literal" &&
        typeof node.property.value === "string" &&
        BLOCKED_IDENTIFIERS.has(node.property.value)
      ) {
        const { line, column } = loc(node);
        errors.push(
          makeError(
            "blocked_api",
            `Computed access to '${node.property.value}' is not allowed`,
            line,
            column,
          ),
        );
      }
    },
  });

  // ── 4. Verify at least one pres.addSlide() call ────────────────────────
  if (!hasAddSlide) {
    errors.push(
      makeError(
        "no_add_slide",
        "Code must contain at least one pres.addSlide() call",
      ),
    );
  }

  return { valid: errors.length === 0, errors };
}

// ─── EXPORTS ──────────────────────────────────────────────────────────────────
module.exports = { validateArtisanCode, MAX_ARTISAN_CODE_LENGTH };
