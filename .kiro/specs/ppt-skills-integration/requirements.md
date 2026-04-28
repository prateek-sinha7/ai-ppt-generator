# Requirements Document

## Introduction

This feature integrates five skill collections into the AI Presentation Intelligence Platform:

1. **Theme-Factory Themes (Requirements 1–16):** Replaces the platform's four legacy presentation themes (executive, professional, dark-modern, corporate) with ten new themes sourced from the theme-factory skill collection. The replacement spans the entire stack: frontend token definitions, UI theme selector, backend validation, design agent fallback palettes, industry classifier auto-detection, PPTX export color mappings, and the pptx-service builder. The new default theme is ocean-depths. No database migration is required because the theme field is stored as a plain string.

2. **PPTX Design Rules (Requirements 17–19):** Bakes the pptx skill's design principles into LLM system prompts (`prompt_engineering.py`), the design agent's DesignSpec generation prompt (`design_agent.py`), and the pptx-service builder (`builder.js`) to eliminate common AI-generated slide aesthetics and enforce professional design standards.

3. **Frontend Design Polish (Requirements 20–23):** Applies the frontend-design skill's guidelines to improve UI aesthetics across four key components: ThemeSelector, ProgressIndicator, PresentationGenerator, and PptxPreviewPanel. Adds distinctive visual identity, micro-interactions, and atmospheric styling to avoid generic AI aesthetics.

4. **Canvas-Design Fonts (Requirements 24–25):** Expands the available font pairings in the Design_Agent and installs the corresponding font files in the pptx-service Docker image so that generated PPTX files can use distinctive typography from the canvas-design skill's font collection.

5. **Alternative Export Formats (Requirements 26–31):** Adds PDF, DOCX, and XLSX export alongside the existing PPTX export. Introduces new backend services, API endpoints, Celery tasks, a frontend format selector on the download button, and the required Python dependencies.

6. **LLM-Driven Layout Variants (Requirements 32–36):** Enables the LLM to choose per-slide layout variants instead of using a single fixed layout per slide type. Introduces a `layout_variant` field in the Slide_JSON schema, adds ~15 new layout renderers in the PPTX builder and frontend slide components, and enforces layout variety through the storyboarding agent. This is the key change that makes presentations feel designed rather than templated.

7. **Automated Visual QA Pipeline (Requirements 37–38):** Adds a post-generation visual quality assurance loop inspired by the pptx skill's QA methodology. After the PPTX is built, slide images are rendered and sent to the LLM for visual inspection against a checklist of common issues (overlapping elements, text overflow, low contrast, misalignment). If issues are found, the pipeline adjusts the Slide_JSON and re-renders. This catches the visual bugs that make slides look unprofessional.

## Glossary

- **Theme_Registry**: The set of all recognized theme identifiers across the platform, defined as the single source of truth in `tokens.ts` (frontend) and `VALID_THEME_NAMES` (backend), and mirrored in every layer that references theme names.
- **Token_System**: The design token layer in `frontend/src/styles/tokens.ts` that defines spacing, typography, and theme color palettes consumed by all frontend components.
- **Theme_Selector**: The React component (`ThemeSelector.tsx`) that renders visual theme previews and lets the user pick a theme before generation.
- **Validation_Agent**: The backend module (`validation.py`) that enforces allowed theme names on incoming pipeline data.
- **Design_Agent**: The backend module (`design_agent.py`) that provides fallback `DesignSpec` palettes when the LLM is unavailable.
- **Industry_Classifier**: The backend module (`industry_classifier.py`) that auto-detects the best theme based on industry and audience.
- **PPTX_Export_Service**: The backend module (`pptx_export.py`) that maps theme names to `RGBColor` dictionaries for PowerPoint slide generation.
- **PPTX_Builder**: The Node.js service (`pptx-service/builder.js`) that resolves theme palettes when building PPTX files.
- **Pipeline_Orchestrator**: The backend module (`pipeline_orchestrator.py`) that coordinates the generation pipeline and applies default theme fallbacks.
- **Layout_Engine**: The frontend utility (`layoutEngine.ts`) and backend module (`layout_engine.py`) that resolve layout instructions including theme fallback defaults.
- **Cache_Warming_Task**: The backend service (`cache_warming_task.py`) that pre-warms caches using default theme values.
- **Presentation_Cache**: The backend service (`presentation_cache.py`) that caches presentation data with a default theme reference.
- **Legacy_Themes**: The four themes being removed: `executive`, `professional`, `dark-modern`, and `corporate`.
- **New_Themes**: The ten replacement themes: `ocean-depths`, `sunset-boulevard`, `forest-canopy`, `modern-minimalist`, `golden-hour`, `arctic-frost`, `desert-rose`, `tech-innovation`, `botanical-garden`, and `midnight-galaxy`.
- **Dark_Theme**: A theme whose background color is dark and whose text color is light. Two of the ten New_Themes are dark: `tech-innovation` and `midnight-galaxy`.
- **Light_Theme**: A theme whose background color is light (white or near-white) and whose text color is dark. Eight of the ten New_Themes are light themes.
- **Prompt_Engineering_Module**: The backend module (`prompt_engineering.py`) that defines LLM system prompt templates for Claude, OpenAI, and Groq providers.
- **PPTX_Design_Rules**: A set of slide design principles from the pptx skill that eliminate common AI-generated slide aesthetics, covering accent lines, color dominance, dark/light contrast, visual motifs, visual elements per slide, text alignment, and layout variety.
- **Design_Avoid_Rules**: A set of negative constraints injected into the Design_Agent's LLM prompt to prevent common design mistakes: cream/beige backgrounds, repeated layouts, centered body text, accent lines under titles, and generic blue color choices.
- **Theme_Selector_Component**: The React component (`ThemeSelector.tsx`) that renders mini-slide previews and lets the user pick a theme.
- **Progress_Indicator_Component**: The React component (`ProgressIndicator.tsx`) that displays pipeline step progress during presentation generation.
- **Presentation_Generator_Component**: The React component (`PresentationGenerator.tsx`) that provides the topic input form and theme selection UI.
- **Preview_Panel_Component**: The React component (`PptxPreviewPanel.tsx`) that displays rendered slide images with filmstrip navigation.
- **Font_Pair**: A combination of a header font and a body font used by the Design_Agent when generating a DesignSpec.
- **Canvas_Fonts**: The collection of `.ttf` font files located in `skills/canvas-design/canvas-fonts/` that provide distinctive typography options.
- **PDF_Export_Service**: The backend module (`pdf_export.py`) that generates PDF documents from Slide_JSON using the reportlab library.
- **DOCX_Export_Service**: The backend module (`docx_export.py`) that generates Word documents from Slide_JSON using the python-docx library.
- **XLSX_Export_Service**: The backend module (`xlsx_export.py`) that generates Excel workbooks from Slide_JSON using the openpyxl library.
- **Slide_JSON**: The internal JSON representation of a presentation's slides, containing titles, bullets, charts, tables, and theme metadata.
- **Export_API**: The set of REST endpoints that trigger export generation in PDF, DOCX, or XLSX format and return a signed download URL.
- **Format_Selector**: The UI dropdown on the DownloadButton component that lets the user choose an export format (PPTX, PDF, DOCX, XLSX).
- **MinIO**: The S3-compatible object storage service used to store generated export files.
- **Layout_Variant**: A string identifier that specifies which visual arrangement to use when rendering a slide. The LLM selects a layout_variant per slide from a predefined set of options per slide type.
- **Content_Layout_Variants**: The set of layout variants available for content slides: `numbered-cards`, `icon-grid`, `two-column-text`, `stat-callouts`, `timeline`, `quote-highlight`.
- **Chart_Layout_Variants**: The set of layout variants available for chart slides: `chart-right`, `chart-full`, `chart-top`, `chart-with-kpi`.
- **Table_Layout_Variants**: The set of layout variants available for table slides: `table-full`, `table-with-insights`, `table-highlight`.
- **Comparison_Layout_Variants**: The set of layout variants available for comparison slides: `two-column`, `pros-cons`, `before-after`.
- **Storyboarding_Agent**: The backend module (`storyboarding.py`) that builds the section structure and slide plan, enforcing visual diversity constraints.
- **Visual_QA_Agent**: A post-generation pipeline step that renders PPTX slides to images, sends them to the LLM for visual inspection, and returns a list of detected issues with suggested fixes.
- **Visual_QA_Checklist**: The set of visual defects the Visual_QA_Agent checks for: overlapping elements, text overflow, low-contrast text/icons, insufficient margins, misaligned columns, uneven gaps, text wrapping in narrow boxes, and elements too close together.
- **QA_Fix_Loop**: The iterative cycle where the Visual_QA_Agent detects issues, the pipeline adjusts the Slide_JSON to fix them, the PPTX is re-rendered, and the Visual_QA_Agent re-inspects. The loop runs a maximum of two iterations.

## Requirements

### Requirement 1: Remove Legacy Theme Definitions

**User Story:** As a platform maintainer, I want all four Legacy_Themes completely removed from every layer, so that no code path references a deleted theme.

#### Acceptance Criteria

1. WHEN the Token_System is loaded, THE Theme_Registry SHALL contain exactly the ten New_Themes and SHALL NOT contain any Legacy_Theme identifier.
2. WHEN the Validation_Agent checks a theme name, THE Validation_Agent SHALL reject any Legacy_Theme identifier as invalid.
3. WHEN the PPTX_Export_Service resolves a theme, THE PPTX_Export_Service SHALL NOT contain color mappings for any Legacy_Theme.
4. WHEN the PPTX_Builder resolves a theme, THE PPTX_Builder SHALL NOT contain palette entries for any Legacy_Theme.
5. WHEN the Design_Agent provides fallback palettes, THE Design_Agent SHALL NOT contain DesignSpec entries for any Legacy_Theme.

### Requirement 2: Define New Theme Color Tokens

**User Story:** As a frontend developer, I want each of the ten New_Themes defined in the Token_System with complete color palettes, so that all frontend components render correctly.

#### Acceptance Criteria

1. THE Token_System SHALL define a palette object for each of the ten New_Themes containing the keys: `primary`, `secondary`, `accent`, `bg`, `surface`, `text`, `muted`, `border`, and `highlight`.
2. WHEN a Dark_Theme palette is defined, THE Token_System SHALL set the `bg` value to the theme's dark background color and the `text` value to a light readable color.
3. WHEN a Light_Theme palette is defined, THE Token_System SHALL set the `bg` value to a light background color and the `text` value to a dark readable color.
4. THE Token_System SHALL export a `Theme` type that is a union of exactly the ten New_Theme string identifiers.

### Requirement 3: Define New Theme Backend Validation

**User Story:** As a backend developer, I want the Validation_Agent to accept exactly the ten New_Theme names, so that invalid or legacy theme names are rejected at the API boundary.

#### Acceptance Criteria

1. THE Validation_Agent SHALL define `VALID_THEME_NAMES` as a frozen set containing exactly the ten New_Theme identifiers.
2. WHEN a presentation request contains a theme name not in `VALID_THEME_NAMES`, THE Validation_Agent SHALL reject the request with a validation error.
3. THE Validation_Agent SHALL accept both hyphenated (`ocean-depths`) and underscored (`ocean_depths`) forms of each New_Theme name.

### Requirement 4: Define New Theme Fallback Palettes in Design Agent

**User Story:** As a backend developer, I want the Design_Agent to provide complete DesignSpec fallback palettes for all ten New_Themes, so that presentations render correctly when the LLM is unavailable.

#### Acceptance Criteria

1. THE Design_Agent SHALL define a `FALLBACK_PALETTES` dictionary containing a `DesignSpec` entry for each of the ten New_Themes.
2. WHEN the Design_Agent looks up a fallback palette by theme name, THE Design_Agent SHALL return a DesignSpec whose `primary_color`, `secondary_color`, `accent_color`, `background_color`, and `background_dark_color` match the theme-factory color specifications.
3. WHEN the Design_Agent looks up a fallback palette for a Dark_Theme, THE Design_Agent SHALL return a DesignSpec whose `background_color` is the dark background and whose `text_color` is a light readable value.

### Requirement 5: Define New Theme PPTX Export Colors

**User Story:** As a backend developer, I want the PPTX_Export_Service to map all ten New_Themes to complete RGBColor dictionaries, so that exported PowerPoint files use the correct colors.

#### Acceptance Criteria

1. THE PPTX_Export_Service SHALL define a color dictionary for each of the ten New_Themes containing the keys: `primary`, `secondary`, `accent`, `accent2`, `text`, `text_light`, `background`, `surface`, `divider`, `kpi_bg`, `kpi_text`, `header_bar`, and `chart_colors`.
2. WHEN the PPTX_Export_Service resolves a theme name, THE PPTX_Export_Service SHALL return the matching color dictionary for any of the ten New_Themes.
3. IF an unrecognized theme name is provided, THEN THE PPTX_Export_Service SHALL fall back to the `ocean-depths` color dictionary.

### Requirement 6: Define New Theme PPTX Builder Palettes

**User Story:** As a platform developer, I want the PPTX_Builder to contain palette entries for all ten New_Themes, so that the Node.js PPTX generation service renders slides with correct colors.

#### Acceptance Criteria

1. THE PPTX_Builder SHALL define a `THEMES` object containing a palette entry for each of the ten New_Themes.
2. WHEN the PPTX_Builder resolves a theme, THE PPTX_Builder SHALL return the matching palette for any of the ten New_Themes.
3. IF an unrecognized theme name is provided, THEN THE PPTX_Builder SHALL fall back to the `ocean-depths` palette.

### Requirement 7: Update Industry Classifier Theme Selection

**User Story:** As a product owner, I want the Industry_Classifier to map industries and audiences to the most appropriate New_Theme, so that auto-detected themes match the presentation context.

#### Acceptance Criteria

1. WHEN the Industry_Classifier selects a theme for a technology or fintech industry, THE Industry_Classifier SHALL return `tech-innovation`.
2. WHEN the Industry_Classifier selects a theme for a healthcare or pharmaceutical industry, THE Industry_Classifier SHALL return `arctic-frost`.
3. WHEN the Industry_Classifier selects a theme for a finance, insurance, or consulting industry, THE Industry_Classifier SHALL return `ocean-depths`.
4. WHEN the Industry_Classifier selects a theme for a sustainability or wellness industry, THE Industry_Classifier SHALL return `forest-canopy`.
5. WHEN the Industry_Classifier selects a theme for a creative, marketing, or advertising industry, THE Industry_Classifier SHALL return `sunset-boulevard`.
6. WHEN the Industry_Classifier selects a theme for a fashion or beauty industry, THE Industry_Classifier SHALL return `desert-rose`.
7. WHEN the Industry_Classifier selects a theme for a hospitality or artisan industry, THE Industry_Classifier SHALL return `golden-hour`.
8. WHEN the Industry_Classifier selects a theme for a food or agriculture industry, THE Industry_Classifier SHALL return `botanical-garden`.
9. WHEN the Industry_Classifier selects a theme for an entertainment or gaming industry, THE Industry_Classifier SHALL return `midnight-galaxy`.
10. WHEN the Industry_Classifier cannot match an industry to a specific theme, THE Industry_Classifier SHALL return `ocean-depths` as the default.
11. WHEN the Industry_Classifier selects a theme for an executive audience in a general business context, THE Industry_Classifier SHALL return `modern-minimalist`.

### Requirement 8: Update Default Theme to ocean-depths

**User Story:** As a product owner, I want ocean-depths to be the platform-wide default theme replacing corporate, so that new presentations use the updated branding.

#### Acceptance Criteria

1. WHEN the PresentationWorkflow initializes theme state, THE PresentationWorkflow SHALL set the default theme to `ocean-depths`.
2. WHEN the Pipeline_Orchestrator applies a fallback theme, THE Pipeline_Orchestrator SHALL use `ocean-depths` as the default.
3. WHEN the Layout_Engine resolves a theme from layout instructions and no valid theme is specified, THE Layout_Engine SHALL fall back to `ocean-depths`.
4. WHEN the Cache_Warming_Task uses a default theme value, THE Cache_Warming_Task SHALL use `ocean-depths`.
5. WHEN the Presentation_Cache uses a default theme value, THE Presentation_Cache SHALL use `ocean-depths`.
6. WHEN the PPTX_Builder encounters a missing or unrecognized theme, THE PPTX_Builder SHALL fall back to `ocean-depths`.
7. WHEN the backend Layout_Engine applies default theme parameters, THE Layout_Engine SHALL use `ocean-depths`.

### Requirement 9: Update Theme Selector UI

**User Story:** As a user, I want to see all ten New_Themes in the Theme_Selector with visual previews, so that I can choose the right theme for my presentation.

#### Acceptance Criteria

1. THE Theme_Selector SHALL display exactly ten theme options, one for each New_Theme.
2. THE Theme_Selector SHALL render a mini slide preview for each theme using that theme's color palette from the Token_System.
3. THE Theme_Selector SHALL arrange theme options in a grid with five columns on screens wider than the small breakpoint.
4. WHEN a user selects a theme, THE Theme_Selector SHALL pass the selected New_Theme identifier to the parent component.
5. THE Theme_Selector SHALL display a human-readable label and a short description for each New_Theme.

### Requirement 10: Update Frontend Type Definitions

**User Story:** As a frontend developer, I want the TypeScript `Theme` type to be a union of exactly the ten New_Theme identifiers, so that type checking catches references to removed themes at compile time.

#### Acceptance Criteria

1. THE `Theme` type in `frontend/src/types/index.ts` SHALL be a union of exactly the ten New_Theme string literal types.
2. WHEN a component references a Legacy_Theme identifier, THE TypeScript compiler SHALL report a type error.

### Requirement 11: Update Theme Utility Functions

**User Story:** As a frontend developer, I want `themeUtils.ts` to provide correct bgDark values and color resolution for all ten New_Themes, so that slide rendering uses the right dark backgrounds.

#### Acceptance Criteria

1. THE `bgDarkMap` in `themeUtils.ts` SHALL contain an entry for each of the ten New_Themes mapping to the appropriate dark background hex color.
2. WHEN `getThemeColors` is called with a New_Theme identifier, THE function SHALL return a complete `SlideColors` object with all required fields populated.
3. WHEN `getThemeColors` is called with a Dark_Theme identifier, THE function SHALL return a `SlideColors` object whose `bgDark` value matches the theme's dark background color.

### Requirement 12: Update Backend API Theme Validation

**User Story:** As a backend developer, I want the presentations API endpoint to validate theme names against the ten New_Themes, so that API requests with legacy or invalid themes are rejected.

#### Acceptance Criteria

1. WHEN a presentation creation request includes a theme value, THE presentations API SHALL validate the theme against the set of ten New_Theme identifiers.
2. IF a presentation creation request includes a Legacy_Theme name, THEN THE presentations API SHALL return a 422 validation error.
3. WHEN a presentation creation request omits the theme field, THE presentations API SHALL default to `ocean-depths`.

### Requirement 13: Update Export Templates Admin Theme Colors

**User Story:** As a backend developer, I want the export templates admin endpoint to use the ten New_Theme color mappings, so that template previews render with correct colors.

#### Acceptance Criteria

1. THE export templates admin module SHALL define a `theme_colors` dictionary containing color entries for each of the ten New_Themes.
2. WHEN the export templates admin resolves colors for a theme, THE module SHALL return the correct color values for any of the ten New_Themes.
3. IF an unrecognized theme is provided, THEN THE export templates admin module SHALL fall back to the `ocean-depths` color entry.

### Requirement 14: Update Backend Service Defaults

**User Story:** As a backend developer, I want all backend services that reference a default theme to use ocean-depths, so that the system is internally consistent.

#### Acceptance Criteria

1. WHEN the Industry_Classifier_Service applies a fallback theme, THE Industry_Classifier_Service SHALL use `ocean-depths`.
2. WHEN the worker tasks module references a default theme in documentation or defaults, THE worker tasks module SHALL reference `ocean-depths`.

### Requirement 15: Update All Backend Tests

**User Story:** As a developer, I want all backend tests to use New_Theme identifiers in assertions and fixtures, so that the test suite passes after the theme replacement.

#### Acceptance Criteria

1. WHEN a backend test asserts a theme value, THE test SHALL use a New_Theme identifier.
2. WHEN a backend test provides a theme in a fixture or request payload, THE test SHALL use a New_Theme identifier.
3. WHEN a backend test validates the set of allowed themes, THE test SHALL assert exactly the ten New_Theme identifiers.
4. THE backend test suite SHALL pass with zero theme-related failures after all theme replacements are applied.

### Requirement 16: Update Frontend Tests

**User Story:** As a frontend developer, I want the frontend token tests to validate the ten New_Themes, so that the test suite confirms the theme replacement is complete.

#### Acceptance Criteria

1. WHEN the token test validates theme names, THE test SHALL assert that the Token_System contains exactly the ten New_Theme identifiers.
2. WHEN the token test validates theme palette structure, THE test SHALL verify each New_Theme palette contains all required color keys.
3. THE frontend test suite SHALL pass with zero theme-related failures after all theme replacements are applied.

---

## Skill 2: PPTX Design Rules

### Requirement 17: Integrate PPTX Design Rules into LLM Prompts

**User Story:** As a product owner, I want the pptx skill's design principles embedded in every LLM system prompt, so that AI-generated slide content follows professional design standards and avoids hallmarks of AI-generated slides.

#### Acceptance Criteria

1. THE Prompt_Engineering_Module SHALL include the following rule in the Claude system prompt template: "NEVER use accent lines under titles — these are a hallmark of AI-generated slides."
2. THE Prompt_Engineering_Module SHALL include the following rule in the Claude system prompt template: "One color should dominate (60-70% visual weight), with 1-2 supporting tones and one sharp accent."
3. THE Prompt_Engineering_Module SHALL include the following rule in the Claude system prompt template: "Dark backgrounds for title + conclusion slides, light for content (sandwich structure)."
4. THE Prompt_Engineering_Module SHALL include the following rule in the Claude system prompt template: "Pick ONE distinctive visual motif and repeat it across every slide."
5. THE Prompt_Engineering_Module SHALL include the following rule in the Claude system prompt template: "Every slide needs a visual element — text-only slides are forgettable."
6. THE Prompt_Engineering_Module SHALL include the following rule in the Claude system prompt template: "Don't center body text — left-align paragraphs and lists; center only titles."
7. THE Prompt_Engineering_Module SHALL include the following rule in the Claude system prompt template: "Don't repeat the same layout — vary columns, cards, and callouts across slides."
8. THE Prompt_Engineering_Module SHALL include the same seven PPTX_Design_Rules in the OpenAI system prompt template.
9. THE Prompt_Engineering_Module SHALL include the same seven PPTX_Design_Rules in the Groq system prompt template.

### Requirement 18: Integrate Design Avoid Rules into Design Agent

**User Story:** As a product owner, I want the Design_Agent's LLM prompt to include explicit "Avoid" rules, so that the generated DesignSpec steers away from common design mistakes.

#### Acceptance Criteria

1. WHEN the Design_Agent constructs the LLM prompt for DesignSpec generation, THE Design_Agent SHALL include the rule: "No cream or beige backgrounds."
2. WHEN the Design_Agent constructs the LLM prompt for DesignSpec generation, THE Design_Agent SHALL include the rule: "No repeated layouts across slides."
3. WHEN the Design_Agent constructs the LLM prompt for DesignSpec generation, THE Design_Agent SHALL include the rule: "No centered body text — left-align paragraphs and lists."
4. WHEN the Design_Agent constructs the LLM prompt for DesignSpec generation, THE Design_Agent SHALL include the rule: "No accent lines under titles."
5. WHEN the Design_Agent constructs the LLM prompt for DesignSpec generation, THE Design_Agent SHALL include the rule: "Pick colors specific to the topic, not generic blue."

### Requirement 19: Apply pptxgenjs Best Practices to Builder

**User Story:** As a platform developer, I want the PPTX_Builder to follow pptxgenjs best practices, so that generated slides render correctly without silent failures.

#### Acceptance Criteria

1. WHEN the PPTX_Builder creates a text box that is aligned with a shape edge, THE PPTX_Builder SHALL set `margin: 0` on the text box options to prevent padding misalignment.
2. WHEN the PPTX_Builder applies letter spacing to text, THE PPTX_Builder SHALL use the `charSpacing` property and SHALL NOT use a `letterSpacing` property (which is silently ignored by pptxgenjs).
3. THE PPTX_Builder SHALL create fresh shadow option objects per slide element call by using a factory function, and SHALL NOT reuse a single shared shadow object across multiple calls.

---

## Skill 3: Frontend Design Polish

### Requirement 20: Improve ThemeSelector Aesthetics

**User Story:** As a user, I want the theme selector to have a bold, distinctive visual design, so that choosing a theme feels engaging and each theme card is visually memorable.

#### Acceptance Criteria

1. THE Theme_Selector_Component SHALL render mini-slide previews with increased visual contrast between the theme's primary, accent, and background colors.
2. WHEN a user hovers over a theme card, THE Theme_Selector_Component SHALL apply a CSS transition-based hover animation that scales or elevates the card.
3. THE Theme_Selector_Component SHALL give each theme card a distinctive visual identity using the theme's own color palette for the card border or background accent.
4. THE Theme_Selector_Component SHALL avoid generic AI aesthetics by using context-specific color choices and distinctive card styling rather than uniform gray borders.

### Requirement 21: Improve ProgressIndicator Aesthetics

**User Story:** As a user, I want the progress indicator to feel dynamic and polished, so that waiting for generation feels engaging rather than static.

#### Acceptance Criteria

1. WHEN a pipeline step completes, THE Progress_Indicator_Component SHALL reveal the completed step with a staggered animation using CSS `animation-delay` so that steps appear sequentially rather than all at once.
2. THE Progress_Indicator_Component SHALL apply a subtle motion animation to the progress bar fill, such as a shimmer or pulse effect during active generation.
3. THE Progress_Indicator_Component SHALL use distinctive step styling with visual differentiation between pending, running, completed, and error states that goes beyond simple color changes.
4. THE Progress_Indicator_Component SHALL avoid generic AI aesthetics by using a distinctive color palette and typography rather than default blue-on-white styling.

### Requirement 22: Improve PresentationGenerator Aesthetics

**User Story:** As a user, I want the presentation input form to feel premium and inviting, so that the first interaction with the platform makes a strong impression.

#### Acceptance Criteria

1. THE Presentation_Generator_Component SHALL establish a clear visual hierarchy in the input form with distinct sizing and weight for the heading, description, label, and input elements.
2. THE Presentation_Generator_Component SHALL use distinctive typography for the page heading that differs from the default system font stack.
3. THE Presentation_Generator_Component SHALL apply an atmospheric background treatment such as a gradient, subtle pattern, or layered effect rather than a plain white background.
4. THE Presentation_Generator_Component SHALL style the submit button with a gradient or multi-tone treatment that reinforces the platform's visual identity.

### Requirement 23: Improve PptxPreviewPanel Aesthetics

**User Story:** As a user, I want the slide preview panel to feel smooth and cinematic, so that reviewing generated slides is a polished experience.

#### Acceptance Criteria

1. WHEN the Preview_Panel_Component transitions between slides, THE Preview_Panel_Component SHALL apply a CSS transition with a smooth opacity or transform animation lasting between 200ms and 500ms.
2. WHEN a user hovers over a filmstrip thumbnail, THE Preview_Panel_Component SHALL apply a hover effect that visually elevates or highlights the thumbnail with a scale transform or border glow.
3. WHILE the Preview_Panel_Component is in a loading state, THE Preview_Panel_Component SHALL display a polished loading animation with smooth motion rather than a static spinner.
4. THE Preview_Panel_Component SHALL use consistent transition timing across all interactive elements (slide navigation, thumbnail selection, fullscreen toggle).

---

## Skill 4: Canvas-Design Fonts

### Requirement 24: Expand Font Pairings in Design Agent

**User Story:** As a product owner, I want the Design_Agent to offer additional distinctive font pairings from the canvas-design skill, so that generated presentations have more typographic variety.

#### Acceptance Criteria

1. THE Design_Agent SHALL include the font pair "Instrument Sans / Calibri" in the `AVAILABLE_FONT_PAIRS` table.
2. THE Design_Agent SHALL include the font pair "Work Sans / Calibri Light" in the `AVAILABLE_FONT_PAIRS` table.
3. THE Design_Agent SHALL include the font pair "Lora / Calibri" in the `AVAILABLE_FONT_PAIRS` table.
4. THE Design_Agent SHALL include the font pair "Outfit / Calibri" in the `AVAILABLE_FONT_PAIRS` table.
5. THE Design_Agent SHALL include the font pair "Crimson Pro / Calibri" in the `AVAILABLE_FONT_PAIRS` table.

### Requirement 25: Install Canvas-Design Fonts in pptx-service

**User Story:** As a platform developer, I want the pptx-service Docker image to include the canvas-design font files, so that generated PPTX files can embed the new font pairings.

#### Acceptance Criteria

1. THE pptx-service directory SHALL contain `.ttf` font files for Instrument Sans, Work Sans, Lora, Outfit, and Crimson Pro in Regular, Bold, and Italic variants, copied from `skills/canvas-design/canvas-fonts/`.
2. THE pptx-service Dockerfile SHALL copy the font files into the container's font directory.
3. THE pptx-service Dockerfile SHALL run `fc-cache -f -v` after copying fonts to register the new fonts with the system font cache.
4. WHEN the PPTX_Builder generates a slide using one of the new font pairings, THE pptx-service container SHALL have the corresponding font available for embedding.

---

## Skill 5: Alternative Export Formats

### Requirement 26: Add PDF Export Service

**User Story:** As a user, I want to export my presentation as a PDF, so that I can share it in a universally readable format without requiring PowerPoint.

#### Acceptance Criteria

1. THE PDF_Export_Service SHALL be implemented in `backend/app/services/pdf_export.py`.
2. WHEN the PDF_Export_Service receives Slide_JSON, THE PDF_Export_Service SHALL generate a PDF document with one page per slide.
3. WHEN a slide contains a title, THE PDF_Export_Service SHALL render the title on the corresponding PDF page using the theme's primary color.
4. WHEN a slide contains bullet points, THE PDF_Export_Service SHALL render the bullets as a formatted list on the corresponding PDF page.
5. WHEN a slide contains chart data, THE PDF_Export_Service SHALL render a chart visualization on the corresponding PDF page.
6. WHEN a slide contains table data, THE PDF_Export_Service SHALL render a formatted table on the corresponding PDF page.
7. THE PDF_Export_Service SHALL apply the presentation's theme colors to page backgrounds, text, and accent elements.

### Requirement 27: Add DOCX Export Service

**User Story:** As a user, I want to export my presentation as a Word document, so that I can edit the content in a word processor.

#### Acceptance Criteria

1. THE DOCX_Export_Service SHALL be implemented in `backend/app/services/docx_export.py`.
2. WHEN the DOCX_Export_Service receives Slide_JSON, THE DOCX_Export_Service SHALL generate a Word document using the python-docx library.
3. WHEN a slide contains a title, THE DOCX_Export_Service SHALL render the title as a Word heading styled with the theme's primary color.
4. WHEN a slide contains bullet points, THE DOCX_Export_Service SHALL render the bullets as a Word bulleted list.
5. WHEN a slide contains table data, THE DOCX_Export_Service SHALL render a formatted Word table with theme-colored header row.
6. THE DOCX_Export_Service SHALL insert a page break between each slide's content to maintain slide-per-page structure.

### Requirement 28: Add XLSX Export Service

**User Story:** As a user, I want to export chart and table data from my presentation as an Excel workbook, so that I can analyze the data in a spreadsheet.

#### Acceptance Criteria

1. THE XLSX_Export_Service SHALL be implemented in `backend/app/services/xlsx_export.py`.
2. WHEN the XLSX_Export_Service receives Slide_JSON, THE XLSX_Export_Service SHALL generate an Excel workbook using the openpyxl library.
3. WHEN a slide contains chart data, THE XLSX_Export_Service SHALL create a worksheet named after the slide title containing the chart's data series in tabular form.
4. WHEN a slide contains table data, THE XLSX_Export_Service SHALL create a worksheet named after the slide title containing the table rows and columns.
5. THE XLSX_Export_Service SHALL apply theme-colored header formatting to the first row of each worksheet.
6. IF no slides contain chart or table data, THEN THE XLSX_Export_Service SHALL generate a workbook with a single summary worksheet listing slide titles and types.

### Requirement 29: Add Export API Endpoints and Celery Tasks

**User Story:** As a backend developer, I want dedicated API endpoints and Celery tasks for each export format, so that export generation runs asynchronously and returns a download URL.

#### Acceptance Criteria

1. THE Export_API SHALL expose `POST /presentations/{id}/export/pdf` to trigger PDF export generation.
2. THE Export_API SHALL expose `POST /presentations/{id}/export/docx` to trigger DOCX export generation.
3. THE Export_API SHALL expose `POST /presentations/{id}/export/xlsx` to trigger XLSX export generation.
4. WHEN an export endpoint is called, THE Export_API SHALL enqueue a Celery task (`export_pdf_task`, `export_docx_task`, or `export_xlsx_task`) and return a job identifier.
5. WHEN a Celery export task completes, THE task SHALL upload the generated file to MinIO and store a signed download URL.
6. WHEN a Celery export task fails, THE task SHALL record the error and return a failure status.
7. IF the requested presentation does not exist, THEN THE Export_API SHALL return a 404 error.

### Requirement 30: Add Format Selector to Download Button

**User Story:** As a user, I want to choose between PPTX, PDF, DOCX, and XLSX when downloading my presentation, so that I can get the format I need.

#### Acceptance Criteria

1. THE Format_Selector SHALL be added to the DownloadButton component as a dropdown menu.
2. THE Format_Selector SHALL offer four options: PPTX (default), PDF, DOCX, and XLSX.
3. WHEN the user selects PPTX, THE DownloadButton SHALL trigger the existing PPTX download flow.
4. WHEN the user selects PDF, THE DownloadButton SHALL call the `POST /presentations/{id}/export/pdf` endpoint and download the resulting file.
5. WHEN the user selects DOCX, THE DownloadButton SHALL call the `POST /presentations/{id}/export/docx` endpoint and download the resulting file.
6. WHEN the user selects XLSX, THE DownloadButton SHALL call the `POST /presentations/{id}/export/xlsx` endpoint and download the resulting file.
7. WHILE an export is in progress, THE Format_Selector SHALL display a loading state and disable further selections.

### Requirement 31: Add Export Dependencies

**User Story:** As a backend developer, I want the required Python libraries for PDF, DOCX, and XLSX generation added to the project dependencies, so that the export services can be imported and used.

#### Acceptance Criteria

1. THE `backend/pyproject.toml` SHALL include `reportlab` as a runtime dependency.
2. THE `backend/pyproject.toml` SHALL include `python-docx` as a runtime dependency.
3. THE `backend/pyproject.toml` SHALL include `openpyxl` as a runtime dependency.
4. THE `backend/pyproject.toml` SHALL include `matplotlib` as a runtime dependency for chart rendering in PDF export.
5. IF the export libraries require system-level dependencies, THEN THE `backend/Dockerfile` SHALL install those system packages.

---

## Skill 6: LLM-Driven Layout Variants

### Requirement 32: Add Layout Variant Field to Slide_JSON Schema

**User Story:** As a platform developer, I want a `layout_variant` field in the Slide_JSON schema, so that the LLM can specify which visual arrangement to use for each slide.

#### Acceptance Criteria

1. THE Slide_JSON schema in the Validation_Agent SHALL include an optional `layout_variant` string field on each slide object.
2. THE Validation_Agent SHALL accept the following Content_Layout_Variants: `numbered-cards`, `icon-grid`, `two-column-text`, `stat-callouts`, `timeline`, `quote-highlight`.
3. THE Validation_Agent SHALL accept the following Chart_Layout_Variants: `chart-right`, `chart-full`, `chart-top`, `chart-with-kpi`.
4. THE Validation_Agent SHALL accept the following Table_Layout_Variants: `table-full`, `table-with-insights`, `table-highlight`.
5. THE Validation_Agent SHALL accept the following Comparison_Layout_Variants: `two-column`, `pros-cons`, `before-after`.
6. IF a slide does not include a `layout_variant` field, THEN THE Validation_Agent SHALL NOT reject the slide and the builder SHALL use the default variant for that slide type.
7. IF a slide includes a `layout_variant` that is not in the valid set for its slide type, THEN THE Validation_Agent SHALL auto-correct it to the default variant for that slide type.

### Requirement 33: Guide LLM to Select Layout Variants

**User Story:** As a product owner, I want the LLM system prompts to instruct the model to choose a layout_variant per slide, so that generated presentations have varied, non-repetitive layouts.

#### Acceptance Criteria

1. THE Prompt_Engineering_Module SHALL include instructions in the Claude system prompt template that list all available layout variants per slide type and instruct the LLM to select one per slide.
2. THE Prompt_Engineering_Module SHALL include the instruction: "Vary layouts across slides. Never use the same layout_variant for two consecutive slides of the same type."
3. THE Prompt_Engineering_Module SHALL include the instruction: "Choose the layout_variant that best fits the content — use stat-callouts for data-heavy content, icon-grid for feature lists, timeline for sequential processes, quote-highlight for key takeaways."
4. THE Prompt_Engineering_Module SHALL include the same layout variant instructions in the OpenAI system prompt template.
5. THE Prompt_Engineering_Module SHALL include the same layout variant instructions in the Groq system prompt template.
6. THE Prompt_Engineering_Module SHALL instruct the LLM to include the `layout_variant` field in each slide's JSON output.

### Requirement 34: Implement Content Slide Layout Variants in PPTX Builder

**User Story:** As a platform developer, I want the PPTX_Builder to render content slides using the LLM-selected layout variant, so that content slides have visual variety instead of always using numbered bullet cards.

#### Acceptance Criteria

1. WHEN the PPTX_Builder renders a content slide with `layout_variant` set to `numbered-cards`, THE PPTX_Builder SHALL render the current numbered bullet card layout (existing default behavior).
2. WHEN the PPTX_Builder renders a content slide with `layout_variant` set to `icon-grid`, THE PPTX_Builder SHALL render bullets as a 2×2 or 2×3 grid where each cell contains an icon circle, a bold title, and a description line.
3. WHEN the PPTX_Builder renders a content slide with `layout_variant` set to `two-column-text`, THE PPTX_Builder SHALL split the bullet content into two equal columns with a vertical divider between them.
4. WHEN the PPTX_Builder renders a content slide with `layout_variant` set to `stat-callouts`, THE PPTX_Builder SHALL render up to 4 large numbers (48-60pt) with small labels below, arranged horizontally across the slide.
5. WHEN the PPTX_Builder renders a content slide with `layout_variant` set to `timeline`, THE PPTX_Builder SHALL render bullets as numbered steps connected by a horizontal line, with step labels above and descriptions below.
6. WHEN the PPTX_Builder renders a content slide with `layout_variant` set to `quote-highlight`, THE PPTX_Builder SHALL render the first bullet as a large centered quote (24-28pt italic) with remaining bullets as attribution or context below.
7. IF a content slide has no `layout_variant` or an unrecognized variant, THEN THE PPTX_Builder SHALL fall back to the `numbered-cards` layout.

### Requirement 35: Implement Chart, Table, and Comparison Layout Variants in PPTX Builder

**User Story:** As a platform developer, I want the PPTX_Builder to render chart, table, and comparison slides using the LLM-selected layout variant, so that data slides also have visual variety.

#### Acceptance Criteria

1. WHEN the PPTX_Builder renders a chart slide with `layout_variant` set to `chart-right`, THE PPTX_Builder SHALL render the current layout with insight bullets on the left and chart on the right (existing default behavior).
2. WHEN the PPTX_Builder renders a chart slide with `layout_variant` set to `chart-full`, THE PPTX_Builder SHALL render the chart at full slide width with the title overlaid on the chart area.
3. WHEN the PPTX_Builder renders a chart slide with `layout_variant` set to `chart-top`, THE PPTX_Builder SHALL render the chart on the top half of the slide and insight bullets below.
4. WHEN the PPTX_Builder renders a chart slide with `layout_variant` set to `chart-with-kpi`, THE PPTX_Builder SHALL render a large KPI number on the left and the chart on the right.
5. WHEN the PPTX_Builder renders a table slide with `layout_variant` set to `table-full`, THE PPTX_Builder SHALL render the table at full slide width (existing default behavior).
6. WHEN the PPTX_Builder renders a table slide with `layout_variant` set to `table-with-insights`, THE PPTX_Builder SHALL render the table on the left with insight bullets on the right.
7. WHEN the PPTX_Builder renders a table slide with `layout_variant` set to `table-highlight`, THE PPTX_Builder SHALL render the table with one row highlighted in the theme's accent color and a callout box pointing to the highlighted row.
8. WHEN the PPTX_Builder renders a comparison slide with `layout_variant` set to `two-column`, THE PPTX_Builder SHALL render the current two-column layout (existing default behavior).
9. WHEN the PPTX_Builder renders a comparison slide with `layout_variant` set to `pros-cons`, THE PPTX_Builder SHALL render the left column with green checkmark icons and the right column with red X icons before each bullet.
10. WHEN the PPTX_Builder renders a comparison slide with `layout_variant` set to `before-after`, THE PPTX_Builder SHALL render the left column with a muted/grayed-out style and the right column with the theme's accent color to visually emphasize the "after" state.
11. IF a chart, table, or comparison slide has no `layout_variant` or an unrecognized variant, THEN THE PPTX_Builder SHALL fall back to the default variant for that slide type.

### Requirement 36: Implement Layout Variants in Frontend Slide Components

**User Story:** As a frontend developer, I want the frontend slide preview components to render layout variants matching the PPTX builder, so that the browser preview matches the downloaded PPTX.

#### Acceptance Criteria

1. THE `SlideData` interface in `frontend/src/types/index.ts` SHALL include an optional `layout_variant` string field.
2. WHEN the ContentSlide component receives a slide with a `layout_variant`, THE ContentSlide component SHALL render the corresponding layout variant (icon-grid, two-column-text, stat-callouts, timeline, quote-highlight).
3. WHEN the ChartSlide component receives a slide with a `layout_variant`, THE ChartSlide component SHALL render the corresponding layout variant (chart-full, chart-top, chart-with-kpi).
4. WHEN the TableSlide component receives a slide with a `layout_variant`, THE TableSlide component SHALL render the corresponding layout variant (table-with-insights, table-highlight).
5. WHEN the ComparisonSlide component receives a slide with a `layout_variant`, THE ComparisonSlide component SHALL render the corresponding layout variant (pros-cons, before-after).
6. IF a slide component receives no `layout_variant` or an unrecognized variant, THEN THE component SHALL render the default layout for that slide type.
7. THE Storyboarding_Agent SHALL enforce that no two consecutive slides of the same type use the same layout_variant.

---

## Skill 7: Automated Visual QA Pipeline

### Requirement 37: Implement Visual QA Agent

**User Story:** As a product owner, I want every generated presentation to be visually inspected by an LLM before delivery, so that common visual defects like overlapping elements, text overflow, and low-contrast text are caught and fixed automatically.

#### Acceptance Criteria

1. THE Visual_QA_Agent SHALL be implemented as a new pipeline step that runs after the PPTX is built by the pptx-service.
2. WHEN the Visual_QA_Agent runs, THE Visual_QA_Agent SHALL call the pptx-service `/preview` endpoint to render all slides as JPEG images.
3. WHEN the Visual_QA_Agent receives slide images, THE Visual_QA_Agent SHALL send the images to the LLM along with the Visual_QA_Checklist prompt that instructs the LLM to inspect for:
   - Overlapping elements (text through shapes, lines through words, stacked elements)
   - Text overflow or cut off at edges or box boundaries
   - Elements too close together (less than 0.3 inch gaps)
   - Uneven gaps (large empty area in one place, cramped in another)
   - Insufficient margin from slide edges (less than 0.5 inch)
   - Columns or similar elements not aligned consistently
   - Low-contrast text (light text on light backgrounds or dark text on dark backgrounds)
   - Low-contrast icons (dark icons on dark backgrounds without a contrasting circle)
   - Text boxes too narrow causing excessive wrapping
4. WHEN the LLM returns a list of issues, THE Visual_QA_Agent SHALL parse the response into a structured list of issues, each containing the slide number, issue type, and description.
5. IF the LLM reports zero issues, THEN THE Visual_QA_Agent SHALL mark the presentation as visually approved and proceed without changes.
6. IF the LLM reports one or more issues, THEN THE Visual_QA_Agent SHALL attempt to fix the issues by adjusting the Slide_JSON (trimming long titles, reducing bullet count, adjusting layout_variant, or flagging unfixable issues).
7. THE Visual_QA_Agent SHALL publish `agent_start` and `agent_complete` SSE events so the frontend progress indicator displays the QA step.

### Requirement 38: Implement QA Fix Loop with Re-render

**User Story:** As a product owner, I want the Visual QA pipeline to re-render and re-inspect after applying fixes, so that fixes don't introduce new visual problems.

#### Acceptance Criteria

1. WHEN the Visual_QA_Agent applies fixes to the Slide_JSON, THE Visual_QA_Agent SHALL re-build the PPTX via the pptx-service and re-render slide images.
2. WHEN the Visual_QA_Agent re-renders slide images, THE Visual_QA_Agent SHALL re-inspect only the slides that were modified in the previous fix pass.
3. THE QA_Fix_Loop SHALL run a maximum of two iterations to prevent infinite loops.
4. IF the QA_Fix_Loop reaches the maximum iteration count and issues remain, THEN THE Visual_QA_Agent SHALL log the remaining issues and proceed with the best available version.
5. THE Visual_QA_Agent SHALL record the total number of issues found, issues fixed, and remaining issues in the pipeline context for observability.
6. WHEN the QA_Fix_Loop completes, THE Visual_QA_Agent SHALL update the presentation's slides in the database with the corrected Slide_JSON.
7. THE Visual_QA_Agent SHALL complete within a latency budget of 60 seconds, including all LLM calls and re-render cycles.
