# Implementation Plan: Full Code Generation (Artisan Mode) & Mode Rename

## Overview

This plan implements the Artisan generation mode and renames all four modes (json→express, hybrid→craft, code→studio, plus new artisan) across the full stack. Tasks are ordered bottom-up: pptx-service infrastructure first, then backend Python changes, then frontend TypeScript/React updates, with checkpoints after each major component group.

## Tasks

- [ ] 1. Artisan Validator module (pptx-service)
  - [x] 1.1 Create `pptx-service/artisan-validator.js` with AST-based static analysis
    - Implement `validateArtisanCode(code)` function using acorn parser and acorn-walk
    - Enforce 500,000-character size limit (`MAX_ARTISAN_CODE_LENGTH`)
    - Detect blocked patterns: require(), import, process, child_process, fs, net, http, https, eval, Function constructor, setTimeout, setInterval, setImmediate, global, globalThis, __dirname, __filename
    - Verify at least one `pres.addSlide()` call exists in the AST
    - Return `{ valid: boolean, errors: [{ type, message, line?, column? }] }` with error types: `blocked_api`, `size_limit`, `no_add_slide`, `syntax_error`
    - Follow the same acorn parse + walk pattern as `code-validator.js` but check `pres.addSlide()` instead of `slide.*` API calls
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 1.2 Write property tests for Artisan Validator (fast-check)
    - Create `pptx-service/tests/artisan-validator.prop.test.js`
    - Set up Jest + fast-check test framework in pptx-service (add dev dependencies to package.json, add jest config)
    - **Property 1: Artisan validator rejects unsafe code** — generate random JS strings with injected blocked patterns and verify `valid === false`
    - **Property 2: Artisan validator result shape invariant** — for any input string, verify result has `valid` (boolean) and `errors` (array) fields with correct shape
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

  - [ ]* 1.3 Write unit tests for Artisan Validator
    - Create `pptx-service/tests/artisan-validator.test.js`
    - Test valid code with `pres.addSlide()` passes validation
    - Test each blocked pattern is individually rejected
    - Test code exceeding 500,000 chars is rejected
    - Test code without `pres.addSlide()` is rejected
    - Test syntax errors are caught and reported with line/column
    - Test that existing `code-validator.js` is unchanged (import and verify `MAX_CODE_LENGTH === 50_000`)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 2. Artisan Executor module (pptx-service)
  - [x] 2.1 Create `pptx-service/artisan-executor.js` with sandboxed VM execution
    - Implement `executeArtisanCode(code, designSpec, theme)` async function
    - Create fresh `pptxgenjs` presentation instance inside the executor
    - Build sandbox context with: `pres`, `theme` (ThemePalette via `buildThemePalette`), `fonts`, `themes` (via `getAllThemePalettes`), `iconToBase64`, safe `console`, `Promise`
    - Wrap LLM code in async IIFE: `(async function(pres, theme, fonts, themes, iconToBase64) { ${code} })(pres, theme, fonts, themes, iconToBase64);`
    - Compile with `vm.Script` and execute in `vm.createContext` with 60-second timeout (`ARTISAN_EXECUTION_TIMEOUT_MS`)
    - Return `{ result: { success, error?, slideCount? }, pres? }` — on success, return the populated `pres` object for buffer generation
    - Follow the same sandbox pattern as `code-executor.js` but inject `pres` instead of `slide`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 2.2 Write property tests for Artisan Executor (fast-check)
    - Create `pptx-service/tests/artisan-executor.prop.test.js`
    - **Property 3: Artisan executor error structure** — for random syntactically valid JS that throws, verify `{ success: false, error: <non-empty string> }`
    - **Validates: Requirements 4.4**

  - [ ]* 2.3 Write unit tests for Artisan Executor
    - Create `pptx-service/tests/artisan-executor.test.js`
    - Test valid code that calls `pres.addSlide()` and adds content succeeds
    - Test sandbox context contains all required objects (pres, theme, fonts, themes, iconToBase64, console)
    - Test async IIFE wrapper allows `await iconToBase64(...)` calls
    - Test runtime errors return structured error response
    - Test timeout enforcement (mock a long-running script)
    - Test that existing `code-executor.js` is unchanged (import and verify `EXECUTION_TIMEOUT_MS === 10_000`)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 3. Artisan pptx-service endpoints
  - [x] 3.1 Add `/build-artisan` and `/preview-artisan` endpoints to `pptx-service/server.js`
    - Import `validateArtisanCode` from `artisan-validator.js` and `executeArtisanCode` from `artisan-executor.js`
    - POST `/build-artisan`: accept `{ artisan_code, design_spec, theme }`, validate with artisan-validator, execute with artisan-executor, call `pres.write({ outputType: "nodebuffer" })`, return PPTX buffer with correct Content-Type and Content-Disposition headers
    - POST `/preview-artisan`: same body, build PPTX via artisan executor, convert to images via existing `pptxToImages()` helper, return `{ images, count }`
    - Return 400 if `artisan_code` is missing, 422 with `{ error, retry_with_studio: true }` on validation/execution failure, 500 on unexpected errors
    - Ensure existing `/build`, `/preview`, `/build-code`, `/preview-code` endpoints remain unchanged
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 3.2 Write property tests for `/build-artisan` endpoint (fast-check)
    - Create `pptx-service/tests/artisan-endpoint.prop.test.js`
    - **Property 4: /build-artisan 422 on invalid scripts** — for random invalid artisan_code payloads, verify HTTP 422 with `retry_with_studio: true`
    - **Validates: Requirements 5.5**

  - [ ]* 3.3 Write unit tests for Artisan endpoints
    - Create `pptx-service/tests/artisan-endpoint.test.js`
    - Test `/build-artisan` returns PPTX buffer with correct headers for valid code
    - Test `/build-artisan` returns 400 for missing artisan_code
    - Test `/build-artisan` returns 422 with `retry_with_studio: true` for invalid code
    - Test `/preview-artisan` returns `{ images, count }` for valid code
    - Test existing endpoints still work unchanged
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 14.1_

- [ ] 4. Checkpoint — pptx-service modules complete
  - Ensure all pptx-service tests pass, ask the user if questions arise.

- [x] 5. GenerationMode enum rename and extension (backend)
  - [x] 5.1 Update `backend/app/core/generation_mode.py`
    - Rename enum values: `CODE = "code"` → `STUDIO = "studio"`, `HYBRID = "hybrid"` → `CRAFT = "craft"`, `JSON = "json"` → `EXPRESS = "express"`
    - Add new value: `ARTISAN = "artisan"`
    - Update `PROVIDER_DEFAULT_MODES`: claude→ARTISAN, openai→STUDIO, groq→CRAFT, local→EXPRESS
    - Update module docstring to reflect four modes
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 5.2 Update all backend references to old enum values
    - Search and replace `GenerationMode.CODE` → `GenerationMode.STUDIO`, `GenerationMode.HYBRID` → `GenerationMode.CRAFT`, `GenerationMode.JSON` → `GenerationMode.EXPRESS` across all backend Python files
    - Update string literals `"code"`, `"hybrid"`, `"json"` used as generation mode values in pipeline_orchestrator.py, validation.py, prompt_engineering.py, visual_qa.py, presentations.py
    - Update `CodeFailureTracker.downgraded_mode()` to include artisan→studio→craft→express chain
    - _Requirements: 1.1, 1.2, 14.3_

  - [ ]* 5.3 Write unit tests for GenerationMode enum and provider mapping
    - Add tests to `backend/tests/test_generation_mode.py` (create if needed)
    - Verify enum has exactly four values: artisan, studio, craft, express
    - Verify provider-to-mode mapping: claude→artisan, openai→studio, groq→craft, local→express
    - Verify `CodeFailureTracker.downgraded_mode()` chain: artisan→studio→craft→express
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.6_

- [x] 6. Artisan Prompt Template (backend)
  - [x] 6.1 Add `ARTISAN_TEMPLATE` to `backend/app/agents/prompt_engineering.py`
    - Create a new `PromptTemplate` for artisan mode with system prompt containing full pptxgenjs API reference
    - Instruct LLM to generate a single JavaScript function body receiving `pres` object
    - Instruct LLM to call `pres.addSlide()` for each slide and use pptxgenjs API calls for all content
    - Include instructions that theme colors are available via optional `theme` object but LLM may choose own hex values
    - Include pptxgenjs API reference: text formatting, rich text arrays, shapes, charts, tables, images, backgrounds, shadows, masters, layouts, slide-level properties
    - Include common pitfalls section (no "#" in hex colors, no reusing option objects, charSpacing not letterSpacing, breakLine between array items, bullet:true not unicode)
    - Instruct LLM to embed speaker notes via `slide.addNotes()` for each slide
    - Instruct LLM to return `{ "artisan_code": "<script>" }` JSON wrapper
    - Wire the template selection in `generate_prompt()` to use ARTISAN_TEMPLATE when `generation_mode == ARTISAN`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ]* 6.2 Write unit tests for ARTISAN_TEMPLATE
    - Add tests to `backend/tests/test_prompt_engineering_agent.py`
    - Verify ARTISAN_TEMPLATE system prompt contains `pres.addSlide()` instruction
    - Verify ARTISAN_TEMPLATE mentions `artisan_code` JSON wrapper
    - Verify ARTISAN_TEMPLATE includes common pitfalls section
    - Verify ARTISAN_TEMPLATE includes speaker notes instruction
    - Verify `generate_prompt()` selects ARTISAN_TEMPLATE for artisan mode
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 7. Validation Agent extension for Artisan mode (backend)
  - [x] 7.1 Add `validate_artisan_mode()` to `backend/app/agents/validation.py`
    - Add `ARTISAN_API_PATTERN = re.compile(r'pres\.addSlide\(\)')` and `MAX_ARTISAN_CODE_LENGTH = 500_000`
    - Implement `validate_artisan_mode(data, execution_id)` method:
      - Strip markdown code fences from LLM response
      - Handle unwrapped script (no JSON wrapper) by auto-wrapping in `{ "artisan_code": "<script>" }`
      - JSON repair (trailing commas, missing brackets) with up to 2 retries using existing `_repair_json()`
      - Verify `artisan_code` field is a non-empty string
      - Verify `artisan_code` contains `pres.addSlide()`
      - Enforce 500,000 character limit
      - Round-trip validation
    - Add routing branch in `validate()`: `if generation_mode == GenerationMode.ARTISAN: return self.validate_artisan_mode(...)`
    - Update `parse_raw_llm_output()` to handle artisan mode output
    - Ensure existing studio-mode (`validate_code_mode`) and craft-mode (`validate_hybrid_mode`) logic remain unchanged
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 16.1, 16.2, 16.3, 16.4_

  - [ ]* 7.2 Write property tests for Artisan validation (Hypothesis)
    - Create `backend/tests/test_artisan_validation_props.py`
    - **Property 7: Python artisan validation correctness** — random dicts with/without artisan_code, verify invalid when missing key, empty string, no pres.addSlide(), or exceeds 500k chars
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [ ]* 7.3 Write property tests for code fence stripping (Hypothesis)
    - Create `backend/tests/test_code_fence_strip_props.py`
    - **Property 8: Code fence stripping preserves content** — wrap random strings in ```json, ```javascript, plain ``` fences, verify strip_code_fences() recovers original content
    - **Validates: Requirements 8.4, 16.1**

  - [ ]* 7.4 Write property tests for JSON repair (Hypothesis)
    - Create `backend/tests/test_json_repair_props.py`
    - **Property 12: JSON repair recovers valid objects** — introduce trailing commas into valid JSON, verify _repair_json() recovers original
    - **Validates: Requirements 16.3**

  - [ ]* 7.5 Write property tests for Artisan output round-trip (Hypothesis)
    - Create `backend/tests/test_artisan_roundtrip_props.py`
    - **Property 13: Artisan output JSON round-trip** — for random `{ "artisan_code": "<script>" }` objects, verify `json.loads(json.dumps(x)) == x`
    - **Validates: Requirements 16.4**

  - [ ]* 7.6 Write property tests for unwrapped script auto-wrapping (Hypothesis)
    - Create `backend/tests/test_artisan_autowrap_props.py`
    - **Property 11: Unwrapped script auto-wrapping** — for random JS strings containing `pres.addSlide()`, verify validation agent wraps them into `{ "artisan_code": ... }` structure
    - **Validates: Requirements 16.2**

- [-] 8. Pipeline Orchestrator extensions for Artisan mode (backend)
  - [ ] 8.1 Update `backend/app/agents/pipeline_orchestrator.py` for Artisan routing
    - Update mode resolution to use new enum values (ARTISAN, STUDIO, CRAFT, EXPRESS)
    - Route artisan mode to `/build-artisan` and `/preview-artisan` endpoints in `_run_visual_qa` and `_finalize`
    - Implement Artisan retry logic: on validation failure, retry LLM call once with same prompt; on runtime error, retry once with error message appended
    - Implement fallback: after both retries fail, switch to STUDIO mode and re-run from PROMPT_ENGINEERING agent
    - Extend `CodeFailureTracker` with artisan→studio downgrade (30% failure rate over last 10 requests)
    - Update provider failover to remap generation_mode to new provider's default
    - Ensure generation_mode persists across checkpoint recovery (already in PipelineContext.to_checkpoint)
    - _Requirements: 1.7, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 8.2 Write property tests for CodeFailureTracker (Hypothesis)
    - Create `backend/tests/test_code_failure_tracker_props.py`
    - **Property 5: CodeFailureTracker downgrade threshold** — random sequences of success/failure booleans, verify should_downgrade() returns true iff failure rate > 30% over last 10
    - **Validates: Requirements 6.4**

  - [ ]* 8.3 Write property tests for PipelineContext checkpoint round-trip (Hypothesis)
    - Create `backend/tests/test_pipeline_context_props.py`
    - **Property 6: PipelineContext checkpoint round-trip** — random PipelineContext with all four modes, verify to_checkpoint() then from_checkpoint() preserves generation_mode
    - **Validates: Requirements 7.5**

  - [ ]* 8.4 Write property tests for user mode override (Hypothesis)
    - Create `backend/tests/test_mode_override_props.py`
    - **Property 10: User mode override takes precedence** — random (provider, mode) pairs, verify pipeline uses user-specified mode not provider default
    - **Validates: Requirements 11.3**

- [ ] 9. Visual QA Agent extension for Artisan mode (backend)
  - [ ] 9.1 Update `backend/app/agents/visual_qa.py` for Artisan mode
    - Route to `/preview-artisan` endpoint when `generation_mode == ARTISAN`
    - Add `ARTISAN_FIX_PROMPT` template for full-script fixes: send original artisan_code + issue descriptions to LLM, ask for corrected full script
    - Pass artisan_code and design_spec to `/preview-artisan` for re-rendering after fixes
    - Ensure existing studio-mode and craft-mode Visual QA logic remain unchanged
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 10. Backend API update for new mode names
  - [ ] 10.1 Update `backend/app/api/v1/presentations.py` request validation
    - Update `CreatePresentationRequest.generation_mode` validator to accept "artisan", "studio", "craft", "express"
    - Reject old mode names ("full_code", "code", "hybrid", "json") with helpful error message: `"Mode '<name>' has been renamed. Use: artisan, studio, craft, or express"`
    - _Requirements: 11.1, 11.2_

  - [ ]* 10.2 Write property tests for API mode validation (Hypothesis)
    - Create `backend/tests/test_mode_validation_props.py`
    - **Property 9: API mode validation accepts exactly valid modes** — random strings, verify accepts only artisan/studio/craft/express (case-insensitive, trimmed), rejects old names with helpful message
    - **Validates: Requirements 11.1, 11.2**

  - [ ] 10.3 Update SSE event generation_mode field in backend
    - Update SSE `agent_start` event data to use new mode names ("artisan", "studio", "craft", "express")
    - Search for any hardcoded old mode name strings in SSE-related code and update
    - _Requirements: 13.1_

- [ ] 11. Update existing backend tests for mode rename
  - [ ] 11.1 Update all existing backend test files that reference old mode names
    - Search and replace `GenerationMode.CODE` → `GenerationMode.STUDIO`, `GenerationMode.HYBRID` → `GenerationMode.CRAFT`, `GenerationMode.JSON` → `GenerationMode.EXPRESS` in all test files
    - Update string literals `"code"`, `"hybrid"`, `"json"` used as generation mode values in test assertions
    - Update `test_pipeline_orchestrator.py`, `test_validation_agent.py`, `test_prompt_engineering_agent.py`, `test_presentations_api.py`, and any other test files referencing generation modes
    - Ensure all existing tests pass with the new mode names
    - _Requirements: 14.2, 14.3, 14.4_

- [ ] 12. Checkpoint — backend changes complete
  - Ensure all backend tests pass (`docker compose run --rm backend pytest -v`), ask the user if questions arise.

- [ ] 13. Frontend GenerationModeSelector update
  - [ ] 13.1 Update `frontend/src/components/GenerationModeSelector.tsx`
    - Change `GenerationMode` type to `'artisan' | 'studio' | 'craft' | 'express'`
    - Update `MODE_OPTIONS` array to four options with new keys, labels, descriptions, and icons:
      - artisan / Artisan / "Bespoke AI-designed presentation" / 🎨
      - studio / Studio / "Professional-grade slides" / ✦
      - craft / Craft / "Balanced quality & speed" / ⚡
      - express / Express / "Fastest generation" / ⏱
    - Add `hint` field to `ModeOption` interface with tooltip text for each mode
    - Add tooltip/hover hint UI (info icon ⓘ with title attribute or popover) displaying the hint text
    - Update grid layout from `grid-cols-3` to `grid-cols-4` (or `grid-cols-2 sm:grid-cols-4`)
    - _Requirements: 10.1, 10.2, 10.5_

  - [ ] 13.2 Update `frontend/src/components/PresentationGenerator.tsx`
    - Update default `generationMode` state from `'code'` to `'artisan'`
    - Update the `generationMode` reset in the submit handler from `'code'` to `'artisan'`
    - _Requirements: 10.3_

- [ ] 14. Frontend ProgressIndicator update
  - [ ] 14.1 Update `frontend/src/components/ProgressIndicator.tsx`
    - Change `GenerationMode` type to `'artisan' | 'studio' | 'craft' | 'express'`
    - Update `MODE_DESCRIPTIONS` record with four modes:
      - artisan: llm_provider → "Generating complete pptxgenjs presentation script", validation → "Validating full presentation script"
      - studio: llm_provider → "Generating pptxgenjs slide code with AI", validation → "Validating generated code structure"
      - craft: llm_provider → "Generating slide content and code snippets", validation → "Validating JSON structure and code snippets"
      - express: {} (default descriptions)
    - Update `MODE_BADGE` record with four modes and appropriate labels/colors:
      - artisan: "Artisan Mode" with distinctive color class
      - studio: "Studio Mode" (was "Code Mode")
      - craft: "Craft Mode" (was "Hybrid Mode")
      - express: "Express Mode" (was "JSON Mode")
    - Update `extractGenerationMode()` to accept the four new mode strings
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 15. Frontend types update
  - [ ] 15.1 Update `frontend/src/types/index.ts`
    - Change `GenerationStatus.generation_mode` type from `'code' | 'hybrid' | 'json'` to `'artisan' | 'studio' | 'craft' | 'express'`
    - _Requirements: 13.2_

  - [ ] 15.2 Search and update any remaining old mode name references in frontend
    - Grep for `'code'`, `'hybrid'`, `'json'` used as generation mode values across all frontend `.ts` and `.tsx` files
    - Update any remaining references to use new mode names
    - _Requirements: 14.3_

- [ ] 16. Checkpoint — frontend changes complete
  - Ensure frontend builds without errors, ask the user if questions arise.

- [ ] 17. Final integration wiring and verification
  - [ ] 17.1 Verify end-to-end mode routing
    - Verify that `PresentationGenerator` sends the correct `generation_mode` value to the API
    - Verify that the backend API accepts all four new mode names and rejects old names
    - Verify that the pipeline orchestrator routes artisan mode through the correct prompt template, validation, and pptx-service endpoints
    - Verify that SSE events carry the new mode names
    - Verify that the ProgressIndicator displays correct mode-specific descriptions and badges
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 11.1, 11.3, 13.1, 13.2_

  - [ ]* 17.2 Write integration tests for Artisan pipeline fallback
    - Add tests to `backend/tests/test_pipeline_orchestrator.py`
    - Test artisan validation failure triggers retry then studio fallback
    - Test artisan runtime error triggers retry with error context then studio fallback
    - Test CodeFailureTracker downgrades artisan→studio at 30% failure rate
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 18. Final checkpoint — all tests pass
  - Ensure all backend tests pass (`docker compose run --rm backend pytest -v`), ensure all pptx-service tests pass, ensure frontend builds cleanly. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major component group
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The mode rename (tasks 5, 10, 11, 13–15) must be coordinated — old enum values are replaced everywhere simultaneously
- pptx-service modules are JavaScript/Node.js, backend is Python, frontend is TypeScript/React
