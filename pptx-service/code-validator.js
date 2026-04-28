"use strict";
const acorn = require("acorn");
const walk = require("acorn-walk");

// ─── CONSTANTS ────────────────────────────────────────────────────────────────

const MAX_CODE_LENGTH = 50_000;

// Blocked top-level identifiers — any reference to these names is rejected
const BLOCKED_IDENTIFIERS = new Set([
  "process", "child_process", "fs", "net", "http", "https",
  "global", "globalThis", "__dirname", "__filename",
]);

// Blocked function calls — calling these by name is rejected
const BLOCKED_CALLS = new Set([
  "require", "eval", "setTimeout", "setInterval", "setImmediate",
]);

// pptxgenjs API method names we look for on the `slide` object
const PPTX_API_METHODS = new Set([
  "addText", "addShape", "addChart", "addImage", "addTable",
]);

// ─── HELPERS ──────────────────────────────────────────────────────────────────

/**
 * Build a ValidationError object.
 * @param {"blocked_api"|"size_limit"|"no_pptx_call"|"syntax_error"} type
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
 * Validate LLM-generated pptxgenjs slide code using AST-based static analysis.
 *
 * @param {string} code — JavaScript source code for a single slide
 * @returns {{ valid: boolean, errors: ValidationError[] }}
 *
 * ValidationError shape:
 *   { type: string, message: string, line?: number, column?: number }
 */
function validateSlideCode(code) {
  const errors = [];

  // ── 1. Size limit ───────────────────────────────────────────────────────
  if (typeof code !== "string" || code.length > MAX_CODE_LENGTH) {
    const len = typeof code === "string" ? code.length : 0;
    errors.push(
      makeError(
        "size_limit",
        `Code exceeds maximum length of ${MAX_CODE_LENGTH} characters (got ${len})`,
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

  // ── 3. Walk the AST — detect blocked patterns ───────────────────────────
  let hasPptxCall = false;

  // Helper: check if a node is `slide.<method>` call
  function checkPptxCall(node) {
    if (
      node.type === "CallExpression" &&
      node.callee.type === "MemberExpression" &&
      node.callee.object.type === "Identifier" &&
      node.callee.object.name === "slide" &&
      node.callee.property.type === "Identifier" &&
      PPTX_API_METHODS.has(node.callee.property.name)
    ) {
      hasPptxCall = true;
    }
  }

  // Helper: check if a node is `slide.background = ...` assignment
  function checkBackgroundAssignment(node) {
    if (
      node.type === "AssignmentExpression" &&
      node.left.type === "MemberExpression" &&
      node.left.object.type === "Identifier" &&
      node.left.object.name === "slide" &&
      node.left.property.type === "Identifier" &&
      node.left.property.name === "background"
    ) {
      hasPptxCall = true;
    }
  }

  // Walk every node using the simple walker
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
      // Check for pptxgenjs API calls first
      checkPptxCall(node);

      const callee = node.callee;

      // Direct call: require(), eval(), setTimeout(), etc.
      if (callee.type === "Identifier" && BLOCKED_CALLS.has(callee.name)) {
        const { line, column } = loc(node);
        errors.push(
          makeError("blocked_api", `Call to '${callee.name}()' is not allowed`, line, column),
        );
      }

      // new Function(...) or Function(...) — both are blocked
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

    // ── Assignment expressions (slide.background = ...) ─────────────────
    AssignmentExpression(node) {
      checkBackgroundAssignment(node);
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
      // Catch patterns like something["child_process"] or something['fs']
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

  // ── 4. Verify at least one pptxgenjs API call ──────────────────────────
  if (!hasPptxCall) {
    errors.push(
      makeError(
        "no_pptx_call",
        "Code must contain at least one pptxgenjs API call (slide.addText, slide.addShape, slide.addChart, slide.addImage, slide.addTable, or slide.background assignment)",
      ),
    );
  }

  return { valid: errors.length === 0, errors };
}

// ─── EXPORTS ──────────────────────────────────────────────────────────────────
module.exports = { validateSlideCode, MAX_CODE_LENGTH };
