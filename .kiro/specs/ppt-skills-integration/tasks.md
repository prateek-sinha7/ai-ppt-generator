# Implementation Plan: PPT Skills Integration

## Overview

This plan integrates seven skill collections into the AI Presentation Intelligence Platform, organized by dependency order. Each integration builds on the previous one: Theme Factory is the foundation, followed by PPTX Design Rules, Canvas-Design Fonts, Frontend Design Polish, LLM-Driven Layout Variants, Alternative Export Formats, and finally the Automated Visual QA Pipeline.

## Tasks

- [x] 1. Integration 1: Theme Factory — Frontend Token & Type Changes
  - [x] 1.1 Replace legacy theme palettes in `frontend/src/styles/tokens.ts` with 10 new theme palettes
    - Remove the 4 legacy palette entries (executive, professional, dark-modern, corporate)
    - Add 10 new palette entries (ocean-depths, sunset-boulevard, forest-canopy, modern-minimalist, golden-hour, arctic-frost, desert-rose, tech-innovation, botanical-garden, midnight-galaxy) each with 9 keys: primary, secondary, accent, bg, surface, text, muted, border, highlight
    - Ensure dark themes (tech-innovation, midnight-galaxy) have dark bg and light text values
    - The exported `Theme` type and `VALID_THEME_NAMES` set automatically update since they derive from the `themes` object
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4_

  - [x] 1.2 Update `Theme` type in `frontend/src/types/index.ts` to union of 10 new theme identifiers
    - Replace the `Theme` type union with the 10 new theme string literals
    - _Requirements: 10.1, 10.2_

  - [x] 1.3 Update `frontend/src/utils/themeUtils.ts` with new bgDarkMap and getThemeColors
    - Replace the 4-entry `bgDarkMap` with 10 new entries using the design document's bgDark values
    - Ensure `getThemeColors` returns complete `SlideColors` for all 10 themes with chartColors containing at least 4 entries
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 1.4 Update `frontend/src/components/ThemeSelector.tsx` with 10 new theme options
    - Replace `THEME_OPTIONS` array with 10 entries (labels, descriptions for each new theme)
    - Update grid layout from `sm:grid-cols-4` to `sm:grid-cols-5`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 1.5 Update default theme in `frontend/src/components/PresentationWorkflow.tsx` and `frontend/src/utils/layoutEngine.ts`
    - Change default theme state from `'corporate'` to `'ocean-depths'` in PresentationWorkflow
    - Change default theme fallback to `'ocean-depths'` in layoutEngine.ts
    - _Requirements: 8.1, 8.3_

  - [ ]* 1.6 Write property test for frontend theme palette completeness (Property 1)
    - **Property 1: Theme palette structural completeness (frontend)**
    - Using fast-check, generate theme names from the Token_System registry and verify all 9 required keys are present with valid CSS hex color strings
    - **Validates: Requirements 2.1**

  - [ ]* 1.7 Update frontend token tests in `frontend/src/test/tokens.test.ts`
    - Assert Token_System contains exactly the 10 new theme identifiers
    - Verify each palette contains all required color keys
    - **Validates: Requirements 16.1, 16.2, 16.3**

  - [ ]* 1.8 Write property test for getThemeColors completeness (Property 6)
    - **Property 6: getThemeColors returns complete SlideColors**
    - Using fast-check, generate theme names from the Token_System registry and verify `getThemeColors` returns a `SlideColors` object with all required fields populated (`primary`, `secondary`, `accent`, `bg`, `bgDark`, `surface`, `text`, `muted`, `border`, `highlight`, `chartColors`) and `chartColors` contains at least 4 entries
    - **Validates: Requirements 11.2**

- [x] 2. Integration 1: Theme Factory — Backend Validation, Design Agent, Industry Classifier
  - [x] 2.1 Update `backend/app/agents/validation.py` with 10 new theme names
    - Replace `VALID_THEME_NAMES` frozenset with the 10 new theme identifiers
    - Add underscore/hyphen normalization (accept both `ocean-depths` and `ocean_depths`)
    - _Requirements: 1.2, 3.1, 3.2, 3.3_

  - [x] 2.2 Replace `FALLBACK_PALETTES` in `backend/app/agents/design_agent.py` with 10 new DesignSpec entries
    - Remove 4 legacy palette entries
    - Add 10 new DesignSpec entries with colors from the design document's theme color specifications
    - Each entry must include primary_color, secondary_color, accent_color, background_color, background_dark_color, text_color, text_light_color, chart_colors, font_header, font_body, motif, palette_name
    - _Requirements: 1.5, 4.1, 4.2, 4.3_

  - [x] 2.3 Rewrite `_select_theme()` in `backend/app/agents/industry_classifier.py` with new industry→theme mappings
    - Map technology/fintech → tech-innovation, healthcare/pharmaceutical → arctic-frost, finance/insurance/consulting → ocean-depths, sustainability/wellness → forest-canopy, creative/marketing/advertising → sunset-boulevard, fashion/beauty → desert-rose, hospitality/artisan → golden-hour, food/agriculture → botanical-garden, entertainment/gaming → midnight-galaxy, executive+general → modern-minimalist, default → ocean-depths
    - _Requirements: 7.1–7.11_

  - [ ]* 2.4 Write property test for invalid theme name rejection (Property 3)
    - **Property 3: Invalid theme name rejection**
    - Using Hypothesis, generate random strings not in the valid set and verify the Validation_Agent rejects them
    - **Validates: Requirements 3.2**

- [x] 3. Integration 1: Theme Factory — PPTX Export, Pipeline, Services
  - [x] 3.1 Replace `ThemeColors` class in `backend/app/services/pptx_export.py` with 10 new color dictionaries
    - Remove 4 legacy theme color entries (EXECUTIVE, PROFESSIONAL, DARK_MODERN, CORPORATE)
    - Add 10 new theme color dictionaries each with 13 keys: primary, secondary, accent, accent2, text, text_light, background, surface, divider, kpi_bg, kpi_text, header_bar, chart_colors (7 RGBColor values)
    - Update `get_theme()` fallback to `ocean-depths`
    - _Requirements: 1.3, 5.1, 5.2, 5.3_

  - [x] 3.2 Update default theme references in backend services
    - `backend/app/agents/pipeline_orchestrator.py` — change default theme fallback to `'ocean-depths'`
    - `backend/app/agents/layout_engine.py` — change default theme fallback to `'ocean-depths'`
    - `backend/app/services/cache_warming_task.py` — change default theme to `'ocean-depths'`
    - `backend/app/services/presentation_cache.py` — change default theme to `'ocean-depths'`
    - `backend/app/services/industry_classifier_service.py` — change fallback theme to `'ocean-depths'`
    - `backend/app/worker/tasks.py` — update default theme reference to `'ocean-depths'`
    - _Requirements: 8.2, 8.3, 8.4, 8.5, 8.7, 14.1, 14.2_

  - [x] 3.3 Update `backend/app/api/v1/presentations.py` theme validation
    - Update theme validator with 10 new theme names
    - Default to `ocean-depths` when theme is omitted
    - Return 422 for legacy theme names
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 3.4 Update `backend/app/api/v1/export_templates_admin.py` theme colors
    - Replace `theme_colors` dict with 10 new entries
    - Fallback to `ocean-depths` for unrecognized themes
    - _Requirements: 13.1, 13.2, 13.3_

  - [ ]* 3.5 Write property test for ocean-depths fallback in PPTX export (Property 4)
    - **Property 4: Ocean-depths fallback (backend export)**
    - Using Hypothesis, generate random invalid theme strings and verify ocean-depths color dictionary is returned
    - **Validates: Requirements 5.3**

  - [ ]* 3.6 Write property test for PPTX export color dict completeness (Property 2)
    - **Property 2: Theme color dictionary structural completeness (backend export)**
    - Using Hypothesis, generate theme names from registry and verify all 13 required keys present with chart_colors containing at least 4 RGBColor values
    - **Validates: Requirements 5.1**

- [x] 4. Integration 1: Theme Factory — PPTX Builder & Server
  - [x] 4.1 Replace `THEMES` object in `pptx-service/builder.js` with 10 new palette entries
    - Remove 4 legacy palette entries (executive, professional, dark_modern, corporate)
    - Add 10 new palette entries with all required keys: navy, teal, tealDk, blue, blueLt, white, offwhite, slate, slateL, dark, gold, green, red, cardBg, cardBg2, accent, primary, secondary, text, textLight, bg, bgDark, chartColors, fontHeader, fontBody
    - Update `resolveDesign` fallback from `corporate` to `ocean-depths`
    - _Requirements: 1.4, 6.1, 6.2, 6.3, 8.6_

  - [x] 4.2 Update `pptx-service/server.js` default theme parameter to `'ocean-depths'`
    - _Requirements: 8.6_

  - [ ]* 4.3 Write property test for ocean-depths fallback in PPTX builder (Property 5)
    - **Property 5: Ocean-depths fallback (PPTX builder)**
    - Generate random invalid theme strings and verify ocean-depths palette is returned by `resolveDesign`
    - **Validates: Requirements 6.3, 8.6**

- [x] 5. Integration 1: Theme Factory — Backend Test Updates
  - [x] 5.1 Update all backend test files to use new theme identifiers
    - Replace all legacy theme references (executive, professional, dark-modern, dark_modern, corporate) with new theme identifiers in assertions, fixtures, and request payloads across all test files in `backend/tests/`
    - Ensure tests asserting the set of allowed themes use exactly the 10 new theme identifiers
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 6. Checkpoint — Theme Factory complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Integration 2: PPTX Design Rules
  - [x] 7.1 Add 7 PPTX design rules to all LLM system prompt templates in `backend/app/agents/prompt_engineering.py`
    - Add to CLAUDE_TEMPLATE.system_prompt: (1) no accent lines under titles, (2) one dominant color 60-70%, (3) dark backgrounds for title+conclusion / light for content, (4) one visual motif repeated, (5) every slide needs a visual element, (6) left-align body text not center, (7) vary layouts across slides
    - Add the same 7 rules to OPENAI_TEMPLATE.system_prompt
    - Add the same 7 rules to GROQ_TEMPLATE.system_prompt
    - _Requirements: 17.1–17.9_

  - [x] 7.2 Add 5 "Avoid" rules to Design Agent LLM prompt in `backend/app/agents/design_agent.py`
    - Add to `_build_prompt()`: (1) no cream/beige backgrounds, (2) no repeated layouts, (3) no centered body text, (4) no accent lines under titles, (5) pick topic-specific colors not generic blue
    - _Requirements: 18.1–18.5_

  - [x] 7.3 Apply pptxgenjs best practices in `pptx-service/builder.js`
    - Ensure `margin: 0` on text boxes aligned with shape edges
    - Use `charSpacing` property (not `letterSpacing`) for letter spacing
    - Ensure `mkShadow()` factory is used per element call (verify no shared shadow object reuse)
    - _Requirements: 19.1, 19.2, 19.3_

  - [ ]* 7.4 Write property test for design rules in all provider prompts (Property 7)
    - **Property 7: Design rules present in all provider prompts**
    - Using Hypothesis, generate provider types and verify all 7 PPTX design rules are present in the system prompt template
    - **Validates: Requirements 17.1–17.9**

- [x] 8. Checkpoint — PPTX Design Rules complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Integration 3: Canvas-Design Fonts
  - [x] 9.1 Add 5 new font pairs to `AVAILABLE_FONT_PAIRS` in `backend/app/agents/design_agent.py`
    - Add: Instrument Sans / Calibri, Work Sans / Calibri Light, Lora / Calibri, Outfit / Calibri, Crimson Pro / Calibri
    - _Requirements: 24.1–24.5_

  - [x] 9.2 Copy canvas-design font files to `pptx-service/fonts/` directory
    - Copy .ttf files from `skills/canvas-design/canvas-fonts/` for: InstrumentSans (Regular, Bold, Italic, BoldItalic), WorkSans (Regular, Bold, Italic, BoldItalic), Lora (Regular, Bold, Italic, BoldItalic), Outfit (Regular, Bold), CrimsonPro (Regular, Bold, Italic)
    - _Requirements: 25.1_

  - [x] 9.3 Update `pptx-service/Dockerfile` to install canvas-design fonts
    - Add `COPY fonts/ /usr/share/fonts/custom/` before the CMD instruction
    - Add `RUN fc-cache -f -v` after the COPY to register fonts with the system font cache
    - _Requirements: 25.2, 25.3, 25.4_

- [x] 10. Integration 4: Frontend Design Polish
  - [x] 10.1 Improve `frontend/src/components/ThemeSelector.tsx` aesthetics
    - Add CSS transition-based hover animation (scale/elevation) on theme cards
    - Give each theme card a distinctive visual identity using the theme's own color palette for card border or background accent
    - Increase visual contrast between theme's primary, accent, and background colors in mini-slide previews
    - Avoid generic AI aesthetics — use context-specific color choices
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

  - [x] 10.2 Improve `frontend/src/components/ProgressIndicator.tsx` aesthetics
    - Add staggered step reveal animations using CSS `animation-delay` for sequential step appearance
    - Add shimmer or pulse effect on progress bar fill during active generation
    - Add distinctive step styling with visual differentiation beyond simple color changes for pending/running/completed/error states
    - Use a distinctive color palette and typography instead of default blue-on-white
    - _Requirements: 21.1, 21.2, 21.3, 21.4_

  - [x] 10.3 Improve `frontend/src/components/PresentationGenerator.tsx` aesthetics
    - Establish clear visual hierarchy with distinct sizing/weight for heading, description, label, input
    - Use distinctive typography for the page heading (e.g., display font from tokens)
    - Apply atmospheric background treatment (gradient, subtle pattern, or layered effect)
    - Style submit button with gradient or multi-tone treatment
    - _Requirements: 22.1, 22.2, 22.3, 22.4_

  - [x] 10.4 Improve `frontend/src/components/PptxPreviewPanel.tsx` aesthetics
    - Apply CSS transition (200-500ms) for smooth slide transitions
    - Add hover effect on filmstrip thumbnails (scale transform or border glow)
    - Display polished loading animation with smooth motion instead of static spinner
    - Use consistent transition timing across all interactive elements
    - _Requirements: 23.1, 23.2, 23.3, 23.4_

- [x] 11. Checkpoint — Fonts & Frontend Polish complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Integration 5: LLM-Driven Layout Variants — Backend
  - [x] 12.1 Add layout variant validation to `backend/app/agents/validation.py`
    - Add `layout_variant` optional string field validation on each slide object
    - Define per-type variant sets: CONTENT_LAYOUT_VARIANTS, CHART_LAYOUT_VARIANTS, TABLE_LAYOUT_VARIANTS, COMPARISON_LAYOUT_VARIANTS
    - Define DEFAULT_LAYOUT_VARIANTS mapping
    - Auto-correct invalid variants to the default for that slide type
    - Accept slides without layout_variant (backward compatible)
    - _Requirements: 32.1–32.7_

  - [x] 12.2 Add layout variant instructions to LLM prompts in `backend/app/agents/prompt_engineering.py`
    - Add to all 3 provider templates: list of available layout variants per slide type, instruction to select one per slide, instruction to vary layouts and never repeat same variant for consecutive same-type slides, guidance on which variant fits which content type, instruction to include `layout_variant` field in JSON output
    - _Requirements: 33.1–33.6_

  - [x] 12.3 Add layout variant diversity enforcement to `backend/app/agents/storyboarding.py`
    - Enforce that no two consecutive slides of the same type share a layout_variant
    - _Requirements: 36.7_

  - [ ]* 12.4 Write property test for layout variant validation and normalization (Property 11)
    - **Property 11: Layout variant validation and normalization**
    - Using Hypothesis, generate slides with random layout_variant values and verify valid variants are accepted unchanged, invalid/missing variants are normalized to defaults
    - **Validates: Requirements 32.2–32.7**

  - [ ]* 12.5 Write property test for no consecutive duplicate layout variants (Property 12)
    - **Property 12: No consecutive duplicate layout variants**
    - Using Hypothesis, generate presentation plans and verify no two consecutive same-type slides share a layout_variant
    - **Validates: Requirements 36.7**

- [x] 13. Integration 5: LLM-Driven Layout Variants — PPTX Builder
  - [x] 13.1 Add ~12 new layout renderer functions to `pptx-service/builder.js`
    - Content variants: `renderIconGrid`, `renderTwoColumnText`, `renderStatCallouts`, `renderTimeline`, `renderQuoteHighlight`
    - Chart variants: `renderChartFull`, `renderChartTop`, `renderChartWithKpi`
    - Table variants: `renderTableWithInsights`, `renderTableHighlight`
    - Comparison variants: `renderProsCons`, `renderBeforeAfter`
    - Wire variant dispatch into existing slide rendering logic with fallback to default layouts
    - _Requirements: 34.1–34.7, 35.1–35.11_

- [x] 14. Integration 5: LLM-Driven Layout Variants — Frontend
  - [x] 14.1 Add `layout_variant` field to `frontend/src/types/index.ts`
    - Add optional `layout_variant?: string` to `SlideData` interface
    - _Requirements: 36.1_

  - [x] 14.2 Add layout variant rendering to `frontend/src/components/slides/ContentSlide.tsx`
    - Implement variant rendering for: icon-grid, two-column-text, stat-callouts, timeline, quote-highlight
    - Fall back to default (numbered-cards) for missing/unrecognized variants
    - _Requirements: 36.2, 36.6_

  - [x] 14.3 Add layout variant rendering to `frontend/src/components/slides/ChartSlide.tsx`
    - Implement variant rendering for: chart-full, chart-top, chart-with-kpi
    - Fall back to default (chart-right) for missing/unrecognized variants
    - _Requirements: 36.3, 36.6_

  - [x] 14.4 Add layout variant rendering to `frontend/src/components/slides/TableSlide.tsx`
    - Implement variant rendering for: table-with-insights, table-highlight
    - Fall back to default (table-full) for missing/unrecognized variants
    - _Requirements: 36.4, 36.6_

  - [x] 14.5 Add layout variant rendering to `frontend/src/components/slides/ComparisonSlide.tsx`
    - Implement variant rendering for: pros-cons, before-after
    - Fall back to default (two-column) for missing/unrecognized variants
    - _Requirements: 36.5, 36.6_

- [x] 15. Checkpoint — Layout Variants complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Integration 6: Alternative Export Formats — Dependencies & Services
  - [x] 16.1 Add export dependencies to `backend/pyproject.toml` and update Dockerfile if needed
    - Add reportlab, python-docx, openpyxl, matplotlib as runtime dependencies
    - Verify if reportlab or matplotlib require system-level packages (e.g., fonts, image libraries); if so, update `backend/Dockerfile` to install them
    - _Requirements: 31.1–31.5_

  - [x] 16.2 Create `backend/app/services/pdf_export.py`
    - Implement PDF_Export_Service using reportlab + matplotlib
    - Generate one page per slide with title (theme primary color), bullets, chart visualizations (matplotlib), and formatted tables
    - Apply theme colors to page backgrounds, text, and accent elements
    - _Requirements: 26.1–26.7_

  - [x] 16.3 Create `backend/app/services/docx_export.py`
    - Implement DOCX_Export_Service using python-docx
    - Render titles as Word headings with theme primary color, bullets as bulleted lists, tables with theme-colored header row
    - Insert page breaks between slides (N-1 page breaks for N slides)
    - _Requirements: 27.1–27.6_

  - [x] 16.4 Create `backend/app/services/xlsx_export.py`
    - Implement XLSX_Export_Service using openpyxl
    - Create worksheets for slides with chart data or table data, named after slide title (truncate to 31 chars)
    - Apply theme-colored header formatting
    - Generate summary worksheet if no data slides exist
    - _Requirements: 28.1–28.6_

  - [ ]* 16.5 Write property test for PDF page count equals slide count (Property 8)
    - **Property 8: PDF page count equals slide count**
    - Using Hypothesis, generate random Slide_JSON with 1-25 slides and verify PDF has exactly N pages
    - **Validates: Requirements 26.2**

  - [ ]* 16.6 Write property test for DOCX page breaks (Property 9)
    - **Property 9: DOCX slide separation**
    - Using Hypothesis, generate random Slide_JSON with 2-25 slides and verify exactly N-1 page breaks
    - **Validates: Requirements 27.6**

  - [ ]* 16.7 Write property test for XLSX worksheets per data slide (Property 10)
    - **Property 10: XLSX worksheet per data slide**
    - Using Hypothesis, generate random Slide_JSON with mixed types and verify worksheets match data slides
    - **Validates: Requirements 28.3, 28.4**

- [x] 17. Integration 6: Alternative Export Formats — API, Tasks, Frontend
  - [x] 17.1 Add export API endpoints to `backend/app/api/v1/presentations.py`
    - Add `POST /presentations/{id}/export/pdf`, `/docx`, `/xlsx` endpoints
    - Add `GET /presentations/{id}/export/status?job_id=...&format=...` endpoint
    - Enqueue Celery tasks and return job identifier
    - Return 404 for non-existent presentations
    - _Requirements: 29.1–29.4, 29.7_

  - [x] 17.2 Add Celery export tasks to `backend/app/worker/tasks.py`
    - Add `export_pdf_task`, `export_docx_task`, `export_xlsx_task`
    - Each task: generate file → upload to MinIO → store signed download URL
    - Handle failures with error recording
    - _Requirements: 29.4–29.6_

  - [x] 17.3 Add format selector to `frontend/src/components/DownloadButton.tsx`
    - Add dropdown menu with 4 options: PPTX (default), PDF, DOCX, XLSX
    - PPTX triggers existing download flow
    - PDF/DOCX/XLSX call the corresponding export endpoint, poll for status, then download
    - Show loading state and disable further selections during export
    - _Requirements: 30.1–30.7_

  - [x] 17.4 Add export API functions to `frontend/src/services/api.ts`
    - Add `exportPdf()`, `exportDocx()`, `exportXlsx()` functions
    - Add `getExportStatus()` polling function
    - _Requirements: 30.4, 30.5, 30.6_

- [x] 18. Checkpoint — Alternative Export Formats complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Integration 7: Automated Visual QA Pipeline
  - [x] 19.1 Create `backend/app/agents/visual_qa.py`
    - Implement Visual_QA_Agent as a post-generation pipeline step
    - Call pptx-service `/preview` endpoint to render slides as JPEG images
    - Send images to LLM with Visual_QA_Checklist prompt (check for overlapping elements, text overflow, low contrast, misalignment, spacing, wrapping, margin issues)
    - Parse LLM response into structured `VisualQAIssue` list
    - If issues found: apply fixes to Slide_JSON (trim titles, reduce bullets, change layout_variant, flag unfixable)
    - Implement QA_Fix_Loop: max 2 iterations, re-render and re-inspect modified slides only
    - Publish `agent_start` and `agent_complete` SSE events
    - Update presentation slides in database with corrected Slide_JSON
    - Enforce 60-second latency budget
    - Record total issues found, fixed, and remaining in pipeline context
    - _Requirements: 37.1–37.7, 38.1–38.7_

  - [x] 19.2 Add Visual QA step to `backend/app/agents/pipeline_orchestrator.py`
    - Add `VISUAL_QA` to `AgentName` enum
    - Add `AgentName.VISUAL_QA` to `PIPELINE_SEQUENCE` after `QUALITY_SCORING`
    - Add 60-second latency budget for the QA step
    - _Requirements: 37.1_

  - [x] 19.3 Add `visual_qa` step to `frontend/src/components/ProgressIndicator.tsx`
    - Add `visual_qa` entry to `AGENT_PIPELINE` array with displayName "Visual QA" and description "Inspecting slides for visual defects"
    - _Requirements: 37.7_

  - [ ]* 19.4 Write property test for Visual QA issue parser (Property 13)
    - **Property 13: Visual QA issue parser produces structured output**
    - Using Hypothesis, generate random issue JSON in the expected format and verify the parser produces valid `VisualQAIssue` objects with valid slide_number (≥1), valid issue_type, and non-empty description
    - **Validates: Requirements 37.4**

- [x] 20. Final checkpoint — All integrations complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each integration
- Property tests validate universal correctness properties from the design document (13 properties total: 12 backend + 1 frontend)
- Unit tests validate specific examples and edge cases
- The implementation order follows the dependency chain: Theme Factory → Design Rules → Fonts → Frontend Polish → Layout Variants → Export Formats → Visual QA
