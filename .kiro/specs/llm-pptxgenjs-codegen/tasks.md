# Implementation Plan: LLM PptxGenJS Code Generation

## Overview

This plan implements a new generation mode where the LLM produces raw pptxgenjs JavaScript code instead of structured Slide_JSON. The implementation proceeds bottom-up: first the pptx-service sandbox infrastructure (validator, executor, theme palette, endpoints), then the backend pipeline extensions (prompt templates, validation, orchestrator, visual QA), and finally the frontend UI changes. Each task builds on the previous, and fallback to the existing JSON→builder path is wired in from the start.

## Tasks

- [x] 1. Create the Code Validator module in pptx-service
  - [x] 1.1 Create `pptx-service/code-validator.js` with AST-based static analysis
    - Install `acorn` and `acorn-walk` as dependencies in `pptx-service/package.json`
    - Implement `validateSlideCode(code)` that parses code with `acorn` and walks the AST
    - Detect and reject blocked patterns: `require()`, `import`, `process`, `child_process`, `fs`, `net`, `http`, `https`, `eval`, `Function` constructor, `setTimeout`, `setInterval`, `setImmediate`, `global`, `globalThis`, `__dirname`, `__filename`
    - Enforce 50,000 character limit per slide code
    - Verify at least one pptxgenjs API call exists (`slide.addText`, `slide.addShape`, `slide.addChart`, `slide.addImage`, `slide.addTable`, or `slide.background` assignment)
    - Return `{ valid: boolean, errors: ValidationError[] }` with error type, message, line, and column
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 1.2 Write unit tests for the Code Validator
    - Test that valid pptxgenjs code passes validation
    - Test that each blocked pattern (require, import, process, eval, etc.) is rejected
    - Test the 50,000 character limit enforcement
    - Test that code without any pptxgenjs API call is rejected
    - Test syntax error handling
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 2. Create the Theme Palette Builder module in pptx-service
  - [x] 2.1 Create `pptx-service/theme-palette.js`
    - Extract the THEMES object and `resolveDesign()` logic from `builder.js` into a shared module (or import from builder)
    - Implement `buildThemePalette(designSpec, theme)` that returns a `ThemePalette` object with fields: primary, secondary, accent, bg, bgDark, surface, text, muted, border, highlight, chartColors
    - Implement `getAllThemePalettes()` that returns all 10 built-in themes as a lookup object
    - Map resolved palette fields to the simplified ThemePalette interface (surface=cardBg, muted=slateL, border=slate, highlight=gold/accent)
    - _Requirements: 5.1, 5.3, 5.4_

  - [ ]* 2.2 Write unit tests for the Theme Palette Builder
    - Test that each of the 10 built-in themes produces a valid ThemePalette
    - Test that designSpec overrides are applied correctly
    - Test that all required fields are present in the output
    - _Requirements: 5.1, 5.3, 5.4_

- [x] 3. Create the Code Executor module in pptx-service
  - [x] 3.1 Create `pptx-service/code-executor.js` with sandboxed execution
    - Implement `executeSlideCode(code, slide, pres, designSpec, theme)` using Node.js `vm.createContext()` and `vm.Script`
    - Create a minimal sandbox context containing only: slide, pres, theme palette, fonts, themes lookup, and iconToBase64 helper
    - Wrap LLM code in an async IIFE: `(async function(slide, pres, theme, fonts, themes, iconToBase64) { ${code} })`
    - Enforce a 10-second timeout per slide using `AbortController`
    - Catch and report runtime errors with slide index
    - Return `{ success: boolean, error?: string, slideIndex: number }`
    - Import `iconToBase64` from `icons.js` and bind it into the sandbox context
    - Import `buildThemePalette` and `getAllThemePalettes` from `theme-palette.js` for context injection
    - _Requirements: 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 14.1, 14.2, 14.3, 15.1, 15.4_

  - [ ]* 3.2 Write unit tests for the Code Executor
    - Test successful execution of valid pptxgenjs code in sandbox
    - Test that blocked globals (require, process, fs) are not accessible in sandbox
    - Test 10-second timeout enforcement
    - Test that theme and fonts objects are correctly injected
    - Test that iconToBase64 is callable from sandbox code
    - Test runtime error reporting with correct slide index
    - _Requirements: 4.4, 4.5, 4.6, 5.1, 5.2, 15.1_

- [x] 4. Checkpoint — Ensure pptx-service modules work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Add `/build-code` and `/preview-code` endpoints to pptx-service
  - [x] 5.1 Add POST `/build-code` endpoint in `pptx-service/server.js`
    - Accept JSON body with `slides`, `design_spec`, and `theme` fields
    - For each slide: if `render_code` is present, validate with Code Validator then execute with Code Executor
    - If `render_code` is absent, route to existing `builder.js` `buildPptx` rendering for that slide (hybrid support)
    - If validation or execution fails and JSON fields (type, title, content) are present, fall back to `builder.js` for that slide
    - If all slides fail, return 422 with per-slide error details and a `retry_with_json` flag
    - On success, return PPTX buffer with correct Content-Type and Content-Disposition headers
    - _Requirements: 6.1, 6.2, 6.3, 7.1, 7.2, 7.4, 7.5, 15.2_

  - [x] 5.2 Add POST `/preview-code` endpoint in `pptx-service/server.js`
    - Accept the same body as `/build-code`
    - Internally call the same code/hybrid rendering pipeline to produce a PPTX buffer
    - Convert PPTX → PDF → JPEG images using the same LibreOffice + pdftoppm pipeline as existing `/preview`
    - Return `{ images: string[], count: number }`
    - _Requirements: 7.3, 7.4, 15.3_

  - [ ]* 5.3 Write integration tests for `/build-code` and `/preview-code` endpoints
    - Test `/build-code` with valid code-mode slides
    - Test `/build-code` with hybrid-mode slides (mix of code and JSON)
    - Test fallback behavior when code validation fails but JSON fields are present
    - Test 422 response when all slides fail
    - Test `/preview-code` returns base64 images
    - _Requirements: 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 6. Checkpoint — Ensure pptx-service endpoints work end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Add GenerationMode enum and update backend API models
  - [x] 7.1 Add `GenerationMode` enum and provider-to-mode mapping in the backend
    - Create or extend a module (e.g., `backend/app/core/generation_mode.py`) with `GenerationMode` enum: CODE, HYBRID, JSON
    - Define `PROVIDER_DEFAULT_MODES` mapping: Claude→CODE, OpenAI→CODE, Groq→HYBRID, Local→JSON
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 7.2 Update `CreatePresentationRequest` in `backend/app/api/v1/presentations.py`
    - Add optional `generation_mode: Optional[str]` field with validation against `{"code", "hybrid", "json"}`
    - Pass `generation_mode` through to the pipeline orchestrator in `create_presentation` and `generate_presentation_task`
    - _Requirements: 11.3, 11.4, 11.5_

- [x] 8. Extend the Prompt Engineering Agent with code and hybrid templates
  - [x] 8.1 Add `CODE_TEMPLATE` to `backend/app/agents/prompt_engineering.py`
    - Create a code-mode prompt template that instructs the LLM to produce a JSON array with `slide_id`, `slide_number`, `type`, `title`, `speaker_notes`, and `render_code` fields
    - Embed condensed pptxgenjs API reference (text, shapes, charts, tables, images, backgrounds, shadows)
    - Include common pitfalls section (no `#` in hex, no reusing option objects, `charSpacing` not `letterSpacing`, `breakLine` between array items, `bullet:true` not unicode)
    - Include theme object reference (`theme.primary`, `theme.secondary`, etc.) and `iconToBase64` helper signature with available icon libraries (fa, md, hi, bi)
    - Include design rules (no accent lines, dominance over equality, dark/light sandwich, visual motif)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 14.4_

  - [x] 8.2 Add `HYBRID_TEMPLATE` to `backend/app/agents/prompt_engineering.py`
    - Create a hybrid-mode prompt template extending the existing JSON template with instructions to optionally include `render_code` on complex slides
    - Instruct the LLM to use `render_code` for comparison layouts, multi-chart slides, and complex infographics
    - Instruct the LLM to omit `render_code` for standard slides (title, simple content, simple table)
    - _Requirements: 3.1, 3.4_

  - [x] 8.3 Update `optimize()` method to accept and route by `generation_mode`
    - Add `generation_mode` parameter to the prompt optimization flow
    - Select CODE_TEMPLATE for "code" mode, HYBRID_TEMPLATE for "hybrid" mode, existing templates for "json" mode
    - _Requirements: 8.1_

  - [ ]* 8.4 Write unit tests for code and hybrid prompt templates
    - Test that CODE_TEMPLATE includes pptxgenjs API reference, pitfalls, theme reference, and design rules
    - Test that HYBRID_TEMPLATE includes render_code instructions for complex slides
    - Test that optimize() selects the correct template based on generation_mode
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.4_

- [ ] 9. Extend the Validation Agent for code and hybrid modes
  - [x] 9.1 Add code-mode and hybrid-mode validation to `backend/app/agents/validation.py`
    - For code mode: verify each slide has `slide_id`, `slide_number`, `type`, `title`, `speaker_notes`, and `render_code` fields
    - For code mode: verify `render_code` is non-empty and contains at least one pptxgenjs API call pattern
    - For hybrid mode: validate slides with `render_code` using code-mode rules, slides without using existing Slide_JSON schema
    - Enforce 50,000 character limit on `render_code`
    - Implement auto-correction: strip markdown code fences, fix double-escaped newlines/quotes in `render_code`, attempt JSON repair with up to 2 retries
    - Accept `generation_mode` parameter in the `validate()` method to route validation logic
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 13.1, 13.2, 13.3, 13.4_

  - [ ]* 9.2 Write unit tests for code-mode and hybrid-mode validation
    - Test code-mode validation with valid and invalid slide objects
    - Test hybrid-mode validation with mixed code and JSON slides
    - Test auto-correction of markdown fences and escaped strings
    - Test 50,000 character limit enforcement
    - Test JSON repair retry logic
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 13.1, 13.2, 13.3_

- [x] 10. Extend the Pipeline Orchestrator for generation mode support
  - [x] 10.1 Update `PipelineContext` and orchestrator routing in `backend/app/agents/pipeline_orchestrator.py`
    - Add `generation_mode` field to `PipelineContext` dataclass, persisted in checkpoints via `to_checkpoint()` / `from_checkpoint()`
    - Implement provider-to-mode mapping: set default mode based on active provider using `PROVIDER_DEFAULT_MODES`
    - On provider failover, remap `generation_mode` to the new provider's default
    - Pass `generation_mode` to Prompt Engineering Agent and Validation Agent
    - Route PPTX build calls to `/build-code` when mode is "code" or "hybrid", `/build` when "json"
    - Route preview calls to `/preview-code` when mode is "code" or "hybrid", `/preview` when "json"
    - Allow user-provided `generation_mode` to override the provider default
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 8.1, 8.2, 8.3, 8.4, 8.5, 11.4, 11.5, 12.3_

  - [x] 10.2 Implement code failure tracking and mode downgrade logic
    - Add `CodeFailureTracker` with a deque of last 10 results per provider
    - Track success/failure of code generation per provider
    - When failure rate exceeds 30%, downgrade provider's default mode to "hybrid" or "json"
    - _Requirements: 6.4_

  - [ ]* 10.3 Write unit tests for pipeline orchestrator generation mode logic
    - Test provider-to-mode mapping for each provider type
    - Test failover mode remapping
    - Test that generation_mode persists across checkpoint recovery
    - Test code failure tracking and mode downgrade at >30% failure rate
    - Test routing to correct pptx-service endpoints based on mode
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.4, 8.3, 8.4, 8.5_

- [x] 11. Checkpoint — Ensure backend pipeline integration works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Extend the Visual QA Agent for code-generated slides
  - [x] 12.1 Update `backend/app/agents/visual_qa.py` for code and hybrid modes
    - Use `/preview-code` endpoint when mode is "code" or "hybrid"
    - For code-generated slides with issues: instruct LLM to produce corrected `render_code`, providing original code and issue description
    - For JSON-rendered slides in hybrid mode: apply existing JSON-based fix logic
    - Pass `generation_mode` and full slide array with `render_code` fields to preview endpoint
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 12.2 Write unit tests for Visual QA Agent code-mode extensions
    - Test that `/preview-code` is called for code/hybrid modes
    - Test that code-generated slide fixes produce corrected render_code
    - Test that JSON slides in hybrid mode use existing fix logic
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 13. Add SSE generation_mode field to backend events
  - [x] 13.1 Update SSE event emission in the pipeline orchestrator
    - Include `generation_mode` field in `agent_start` SSE event data
    - Ensure the mode is available in the streaming endpoint response
    - _Requirements: 16.1_

- [x] 14. Checkpoint — Ensure all backend changes work together
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Add Generation Mode Selector to the frontend
  - [x] 15.1 Create `GenerationModeSelector` component
    - Create `frontend/src/components/GenerationModeSelector.tsx`
    - Display three radio/toggle options: "Code" (labeled "Highest Visual Quality"), "Hybrid" (labeled "Balanced"), "JSON" (labeled "Classic / Fastest")
    - Default to "code" (hardcoded initially; can be enhanced later with provider-based defaults)
    - Export the selected mode value ("code", "hybrid", or "json")
    - _Requirements: 11.1, 11.2_

  - [x] 15.2 Integrate `GenerationModeSelector` into `PresentationGenerator`
    - Add `GenerationModeSelector` below the `ThemeSelector` in `frontend/src/components/PresentationGenerator.tsx`
    - Add `generation_mode` state and include it in the POST request payload
    - Update the `GenerationStatus` type in `frontend/src/types/index.ts` to include `generation_mode` field
    - _Requirements: 11.1, 11.3_

  - [ ]* 15.3 Write unit tests for GenerationModeSelector
    - Test that all three options render correctly
    - Test that selecting an option updates the value
    - Test default selection
    - _Requirements: 11.1, 11.2_

- [x] 16. Update ProgressIndicator for mode-specific descriptions
  - [x] 16.1 Update `frontend/src/components/ProgressIndicator.tsx` for generation mode awareness
    - Read `generation_mode` from SSE `agent_start` event data
    - For code mode: display "Generating pptxgenjs slide code with AI" and "Validating generated code structure"
    - For hybrid mode: display "Generating slide content and code snippets" and "Validating JSON structure and code snippets"
    - For json mode: keep existing descriptions unchanged
    - Display active generation mode as a badge next to the "Generating Presentation" header
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [ ]* 16.2 Write unit tests for ProgressIndicator mode-specific descriptions
    - Test code-mode step descriptions
    - Test hybrid-mode step descriptions
    - Test json-mode step descriptions remain unchanged
    - Test mode badge rendering
    - _Requirements: 16.3, 16.4, 16.5, 16.6_

- [x] 17. Verify existing JSON mode is preserved
  - [x] 17.1 Verify existing `/build` and `/preview` endpoints are unchanged
    - Confirm that `pptx-service/server.js` still exposes `/build` and `/preview` with unchanged request/response formats
    - Confirm that `builder.js` is not modified and remains fully functional
    - Run existing pptx-service tests to verify no regressions
    - _Requirements: 12.1, 12.2, 12.3_

- [x] 18. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major component
- The pptx-service modules (tasks 1–6) are in JavaScript/Node.js; backend tasks (7–14) are in Python; frontend tasks (15–16) are in TypeScript/React
- The existing JSON→builder pipeline (Requirement 12) is preserved throughout — no modifications to `builder.js` or existing endpoints
- Fallback from code→JSON is wired into the `/build-code` endpoint from the start (task 5.1)
