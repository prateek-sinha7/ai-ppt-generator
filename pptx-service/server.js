"use strict";

const express = require("express");
const pptxgen = require("pptxgenjs");
const { buildPptx, resolveDesign } = require("./builder");
const { validateSlideCode } = require("./code-validator");
const { executeSlideCode } = require("./code-executor");
const { validateArtisanCode } = require("./artisan-validator");
const { executeArtisanCode } = require("./artisan-executor");
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

const app = express();
app.use(express.json({ limit: "10mb" }));

// Health check
app.get("/health", (_req, res) => res.json({ status: "ok" }));

// ── POST /build — build PPTX and stream it back ──────────────────────────────
app.post("/build", async (req, res) => {
  console.log(`[${new Date().toISOString()}] POST /build - Received request`);
  const { slides, design_spec, theme } = req.body;
  console.log(`  - Slides: ${slides?.length || 0}, Theme: ${theme || "ocean-depths"}, Design Spec: ${design_spec ? "present" : "none"}`);
  
  if (!Array.isArray(slides)) {
    console.log("  - ERROR: slides is not an array");
    return res.status(400).json({ error: "slides must be an array" });
  }
  try {
    const pptxBuffer = await buildPptx(slides, design_spec || {}, theme || "ocean-depths");
    console.log(`  - SUCCESS: Generated PPTX (${pptxBuffer.length} bytes)`);
    res.set("Content-Type", "application/vnd.openxmlformats-officedocument.presentationml.presentation");
    res.set("Content-Disposition", "attachment; filename=presentation.pptx");
    res.send(pptxBuffer);
  } catch (err) {
    console.error("  - PPTX build error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ── POST /preview — build PPTX, convert to slide images, return base64 JPGs ──
// Returns: { images: ["data:image/jpeg;base64,...", ...], count: number }
app.post("/preview", async (req, res) => {
  console.log(`[${new Date().toISOString()}] POST /preview - Received request`);
  const { slides, design_spec, theme } = req.body;
  console.log(`  - Slides: ${slides?.length || 0}, Theme: ${theme || "ocean-depths"}, Design Spec: ${design_spec ? "present" : "none"}`);
  
  if (!Array.isArray(slides)) {
    console.log("  - ERROR: slides is not an array");
    return res.status(400).json({ error: "slides must be an array" });
  }

  try {
    // 1. Build PPTX
    console.log("  - Building PPTX...");
    const pptxBuffer = await buildPptx(slides, design_spec || {}, theme || "ocean-depths");
    console.log(`  - PPTX built: ${pptxBuffer.length} bytes`);

    // 2. Convert PPTX → PDF → JPEG images
    const { images, count } = await pptxToImages(pptxBuffer);

    console.log(`  - SUCCESS: Returning ${count} images`);
    res.json({ images, count });
  } catch (err) {
    console.error("  - Preview generation error:", err.message);
    console.error("  - Stack:", err.stack);
    res.status(500).json({ error: err.message });
  }
});

// ── Shared helper: build PPTX buffer using code/hybrid rendering pipeline ─────
// Used by both /build-code and /preview-code endpoints.
// Returns { pptxBuffer, successCount, slideErrors } on partial/full success.
// Throws a CodeBuildError with slide_errors if ALL slides fail.
class CodeBuildError extends Error {
  constructor(message, slideErrors) {
    super(message);
    this.name = "CodeBuildError";
    this.slideErrors = slideErrors;
  }
}

async function buildCodePptx(slides, design_spec, theme) {
  const normalizedTheme = (theme || "ocean-depths").replace(/-/g, "_");
  const C = resolveDesign(design_spec || {}, normalizedTheme);

  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "AI-Generated Presentation";

  const slideErrors = [];   // { slideIndex, error }
  let successCount = 0;

  for (let i = 0; i < slides.length; i++) {
    const slide = slides[i];
    const s = pres.addSlide();
    let rendered = false;
    let slideError = null;

    // ── Case 1: slide has render_code → validate + execute ────────────
    if (slide.render_code) {
      console.log(`  - Slide ${i}: has render_code (${slide.render_code.length} chars), validating...`);

      const validation = validateSlideCode(slide.render_code);
      if (validation.valid) {
        console.log(`  - Slide ${i}: validation passed, executing in sandbox...`);
        const result = await executeSlideCode(
          slide.render_code, s, pres, design_spec || {}, normalizedTheme, i,
        );
        if (result.success) {
          console.log(`  - Slide ${i}: code execution succeeded`);
          rendered = true;
        } else {
          console.warn(`  - Slide ${i}: code execution failed: ${result.error}`);
          slideError = result.error;
        }
      } else {
        const errMsgs = validation.errors.map(e => e.message).join("; ");
        console.warn(`  - Slide ${i}: validation failed: ${errMsgs}`);
        slideError = `Validation failed: ${errMsgs}`;
      }
    }

    // ── Case 2 & 3: no render_code, or code failed with JSON fallback ─
    if (!rendered) {
      const hasJsonFields = slide.type && slide.title;
      if (!slide.render_code || hasJsonFields) {
        console.log(`  - Slide ${i}: using JSON fallback rendering (type=${slide.type || "content"})`);
        try {
          renderJsonFallback(s, slide, C);
          rendered = true;
          if (slideError) {
            console.log(`  - Slide ${i}: fallback succeeded after code failure`);
          }
        } catch (fbErr) {
          console.error(`  - Slide ${i}: JSON fallback also failed: ${fbErr.message}`);
          slideError = slideError
            ? `${slideError}; Fallback also failed: ${fbErr.message}`
            : `Fallback failed: ${fbErr.message}`;
        }
      }
    }

    if (rendered) {
      successCount++;
    } else {
      slideErrors.push({
        slideIndex: i,
        slide_id: slide.slide_id || String(i + 1),
        error: slideError || "No render_code and no JSON fields for fallback",
      });
    }
  }

  // ── All slides failed → throw ───────────────────────────────────────
  if (successCount === 0) {
    console.error(`  - ALL ${slides.length} slides failed`);
    throw new CodeBuildError("All slides failed to render", slideErrors);
  }

  if (slideErrors.length > 0) {
    console.warn(`  - ${slideErrors.length}/${slides.length} slides had errors (fallback may have been used)`);
  }

  const pptxBuffer = await pres.write({ outputType: "nodebuffer" });
  console.log(`  - Generated PPTX (${pptxBuffer.length} bytes), ${successCount}/${slides.length} slides rendered`);

  return { pptxBuffer, successCount, slideErrors };
}

// ── Shared helper: convert PPTX buffer → base64 JPEG images ──────────────────
// Used by both /preview and /preview-code endpoints.
// Returns { images: string[], count: number }
async function pptxToImages(pptxBuffer) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "pptx-preview-"));
  console.log(`  - Created temp dir: ${tmpDir}`);

  try {
    const pptxPath = path.join(tmpDir, "presentation.pptx");
    fs.writeFileSync(pptxPath, pptxBuffer);

    // 1. Convert PPTX → PDF using LibreOffice headless
    console.log("  - Converting PPTX to PDF...");
    execSync(
      `libreoffice --headless --convert-to pdf --outdir "${tmpDir}" "${pptxPath}"`,
      { timeout: 60000, stdio: "pipe" }
    );

    const pdfPath = path.join(tmpDir, "presentation.pdf");
    if (!fs.existsSync(pdfPath)) {
      throw new Error("LibreOffice PDF conversion failed");
    }
    console.log("  - PDF created successfully");

    // 2. Convert PDF pages → JPG images using pdftoppm
    console.log("  - Converting PDF to images...");
    const imgPrefix = path.join(tmpDir, "slide");
    execSync(
      `pdftoppm -jpeg -r 150 "${pdfPath}" "${imgPrefix}"`,
      { timeout: 60000, stdio: "pipe" }
    );

    // 3. Collect all slide-*.jpg files in order
    const files = fs.readdirSync(tmpDir)
      .filter(f => f.startsWith("slide-") && f.endsWith(".jpg"))
      .sort();

    if (files.length === 0) {
      throw new Error("No slide images generated");
    }

    console.log(`  - Generated ${files.length} slide images`);
    const images = files.map(f => {
      const data = fs.readFileSync(path.join(tmpDir, f));
      return "data:image/jpeg;base64," + data.toString("base64");
    });

    return { images, count: images.length };
  } finally {
    // Cleanup temp files
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
  }
}

// ── POST /build-code — build PPTX using LLM-generated pptxgenjs code ─────────
// Supports three cases per slide:
//   1. render_code present → validate → execute in sandbox
//   2. render_code absent  → simplified JSON fallback rendering
//   3. render_code fails + JSON fields present → simplified JSON fallback
// Returns PPTX buffer on success, 422 if ALL slides fail.
app.post("/build-code", async (req, res) => {
  console.log(`[${new Date().toISOString()}] POST /build-code - Received request`);
  const { slides, design_spec, theme } = req.body;
  console.log(`  - Slides: ${slides?.length || 0}, Theme: ${theme || "ocean-depths"}, Design Spec: ${design_spec ? "present" : "none"}`);

  if (!Array.isArray(slides) || slides.length === 0) {
    console.log("  - ERROR: slides must be a non-empty array");
    return res.status(400).json({ error: "slides must be a non-empty array" });
  }

  try {
    const { pptxBuffer, successCount } = await buildCodePptx(slides, design_spec, theme);
    console.log(`  - SUCCESS: Generated PPTX (${pptxBuffer.length} bytes), ${successCount}/${slides.length} slides rendered`);

    res.set("Content-Type", "application/vnd.openxmlformats-officedocument.presentationml.presentation");
    res.set("Content-Disposition", "attachment; filename=presentation.pptx");
    res.send(pptxBuffer);
  } catch (err) {
    if (err instanceof CodeBuildError) {
      return res.status(422).json({
        error: "All slides failed to render",
        retry_with_json: true,
        slide_errors: err.slideErrors,
      });
    }
    console.error("  - /build-code error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ── POST /preview-code — build PPTX via code pipeline, convert to images ──────
// Same body as /build-code. Internally renders PPTX using the code/hybrid
// pipeline, then converts to JPEG images via LibreOffice + pdftoppm.
// Returns: { images: ["data:image/jpeg;base64,...", ...], count: number }
app.post("/preview-code", async (req, res) => {
  console.log(`[${new Date().toISOString()}] POST /preview-code - Received request`);
  const { slides, design_spec, theme } = req.body;
  console.log(`  - Slides: ${slides?.length || 0}, Theme: ${theme || "ocean-depths"}, Design Spec: ${design_spec ? "present" : "none"}`);

  if (!Array.isArray(slides) || slides.length === 0) {
    console.log("  - ERROR: slides must be a non-empty array");
    return res.status(400).json({ error: "slides must be a non-empty array" });
  }

  try {
    // 1. Build PPTX using the code/hybrid rendering pipeline
    console.log("  - Building PPTX via code pipeline...");
    const { pptxBuffer, successCount } = await buildCodePptx(slides, design_spec, theme);
    console.log(`  - PPTX built: ${pptxBuffer.length} bytes, ${successCount}/${slides.length} slides rendered`);

    // 2. Convert PPTX → PDF → JPEG images
    const { images, count } = await pptxToImages(pptxBuffer);

    console.log(`  - SUCCESS: Returning ${count} images`);
    res.json({ images, count });
  } catch (err) {
    if (err instanceof CodeBuildError) {
      console.error(`  - ALL ${slides.length} slides failed`);
      return res.status(422).json({
        error: "All slides failed to render",
        retry_with_json: true,
        slide_errors: err.slideErrors,
      });
    }
    console.error("  - /preview-code error:", err.message);
    console.error("  - Stack:", err.stack);
    res.status(500).json({ error: err.message });
  }
});

// ── POST /build-artisan — build PPTX from a full artisan script ───────────────
// The LLM generates a single complete pptxgenjs script that receives a `pres`
// object and calls pres.addSlide() to create all slides.
// Returns PPTX buffer on success, 422 with retry_with_studio on failure.
app.post("/build-artisan", async (req, res) => {
  console.log(`[${new Date().toISOString()}] POST /build-artisan - Received request`);
  const { artisan_code, design_spec, theme } = req.body;
  console.log(`  - Code length: ${artisan_code?.length || 0}, Theme: ${theme || "ocean-depths"}, Design Spec: ${design_spec ? "present" : "none"}`);

  if (!artisan_code) {
    console.log("  - ERROR: artisan_code is missing");
    return res.status(400).json({ error: "artisan_code is required" });
  }

  try {
    // 1. Validate the artisan code via AST-based static analysis
    const validation = validateArtisanCode(artisan_code);
    if (!validation.valid) {
      const errMsgs = validation.errors.map(e => e.message).join("; ");
      console.warn(`  - Validation failed: ${errMsgs}`);
      return res.status(422).json({
        error: `Artisan validation failed: ${errMsgs}`,
        retry_with_studio: true,
      });
    }

    // 2. Execute the artisan code in a sandboxed VM
    console.log("  - Validation passed, executing in sandbox...");
    const { result, pres } = await executeArtisanCode(artisan_code, design_spec || {}, theme || "ocean-depths");

    if (!result.success) {
      console.warn(`  - Execution failed: ${result.error}`);
      return res.status(422).json({
        error: `Artisan execution failed: ${result.error}`,
        retry_with_studio: true,
      });
    }

    // 3. Generate PPTX buffer from the populated presentation object
    console.log(`  - Execution succeeded, ${result.slideCount} slides created. Writing PPTX...`);
    const pptxBuffer = await pres.write({ outputType: "nodebuffer" });
    console.log(`  - SUCCESS: Generated PPTX (${pptxBuffer.length} bytes)`);

    res.set("Content-Type", "application/vnd.openxmlformats-officedocument.presentationml.presentation");
    res.set("Content-Disposition", "attachment; filename=presentation.pptx");
    res.send(pptxBuffer);
  } catch (err) {
    console.error("  - /build-artisan unexpected error:", err);
    res.status(500).json({ error: err.message });
  }
});

// ── POST /preview-artisan — build PPTX from artisan script, convert to images ─
// Same body as /build-artisan. Internally builds PPTX via the artisan executor,
// then converts to JPEG images via LibreOffice + pdftoppm.
// Returns: { images: ["data:image/jpeg;base64,...", ...], count: number }
app.post("/preview-artisan", async (req, res) => {
  console.log(`[${new Date().toISOString()}] POST /preview-artisan - Received request`);
  const { artisan_code, design_spec, theme } = req.body;
  console.log(`  - Code length: ${artisan_code?.length || 0}, Theme: ${theme || "ocean-depths"}, Design Spec: ${design_spec ? "present" : "none"}`);

  if (!artisan_code) {
    console.log("  - ERROR: artisan_code is missing");
    return res.status(400).json({ error: "artisan_code is required" });
  }

  try {
    // 1. Validate the artisan code
    const validation = validateArtisanCode(artisan_code);
    if (!validation.valid) {
      const errMsgs = validation.errors.map(e => e.message).join("; ");
      console.warn(`  - Validation failed: ${errMsgs}`);
      return res.status(422).json({
        error: `Artisan validation failed: ${errMsgs}`,
        retry_with_studio: true,
      });
    }

    // 2. Execute the artisan code in a sandboxed VM
    console.log("  - Validation passed, executing in sandbox...");
    const { result, pres } = await executeArtisanCode(artisan_code, design_spec || {}, theme || "ocean-depths");

    if (!result.success) {
      console.warn(`  - Execution failed: ${result.error}`);
      return res.status(422).json({
        error: `Artisan execution failed: ${result.error}`,
        retry_with_studio: true,
      });
    }

    // 3. Generate PPTX buffer from the populated presentation object
    console.log(`  - Execution succeeded, ${result.slideCount} slides created. Writing PPTX...`);
    const pptxBuffer = await pres.write({ outputType: "nodebuffer" });
    console.log(`  - PPTX built: ${pptxBuffer.length} bytes`);

    // 4. Convert PPTX → PDF → JPEG images
    const { images, count } = await pptxToImages(pptxBuffer);

    console.log(`  - SUCCESS: Returning ${count} images`);
    res.json({ images, count });
  } catch (err) {
    console.error("  - /preview-artisan error:", err.message);
    console.error("  - Stack:", err.stack);
    res.status(500).json({ error: err.message });
  }
});

// ── JSON Fallback Renderer ────────────────────────────────────────────────────
// Simplified renderer for slides without render_code or when code execution
// fails. Handles the main slide types (title, content, chart, table, etc.)
// with basic but presentable layouts using the resolved palette.
function renderJsonFallback(s, slide, C) {
  const type = slide.type || "content";
  s.background = { color: C.bg };

  switch (type) {
    case "title":
      renderFallbackTitle(s, slide, C);
      break;
    default:
      renderFallbackContent(s, slide, C);
      break;
  }
}

function renderFallbackTitle(s, slide, C) {
  // Dark background for title slides
  s.background = { color: C.bgDark };

  // Main title
  s.addText(slide.title || "Untitled", {
    x: 0.7, y: 1.2, w: 8.6, h: 1.5,
    fontSize: 36, bold: true,
    color: C.bg,
    fontFace: C.fontHeader,
    align: "left",
    valign: "bottom",
  });

  // Subtitle from content
  const subtitle = slide.content?.subtitle
    || slide.content?.tagline
    || (typeof slide.content === "string" ? slide.content : "");
  if (subtitle) {
    s.addText(subtitle, {
      x: 0.7, y: 2.9, w: 8.6, h: 0.8,
      fontSize: 18,
      color: C.slateL,
      fontFace: C.fontBody,
      align: "left",
      valign: "top",
    });
  }

  // Accent bar
  s.addShape("rect", {
    x: 0.7, y: 2.7, w: 2.0, h: 0.06,
    fill: { color: C.accent },
    line: { color: C.accent },
  });
}

function renderFallbackContent(s, slide, C) {
  // Title bar
  if (slide.title) {
    s.addText(slide.title, {
      x: 0.5, y: 0.3, w: 9.0, h: 0.7,
      fontSize: 24, bold: true,
      color: C.primary,
      fontFace: C.fontHeader,
      align: "left",
      valign: "middle",
    });
  }

  // Content area — extract bullets or text
  const content = slide.content || {};
  let bullets = [];

  if (Array.isArray(content.bullets)) {
    bullets = content.bullets;
  } else if (Array.isArray(content)) {
    bullets = content.map(item => (typeof item === "string" ? item : JSON.stringify(item)));
  } else if (typeof content === "string") {
    bullets = content.split("\n").filter(Boolean);
  } else if (content.text) {
    bullets = Array.isArray(content.text) ? content.text : [content.text];
  } else if (content.description) {
    bullets = [content.description];
  }

  if (bullets.length > 0) {
    const textItems = bullets.map(b => ({
      text: typeof b === "string" ? b : String(b),
      options: {
        fontSize: 16,
        color: C.text,
        fontFace: C.fontBody,
        bullet: true,
        breakLine: true,
        paraSpaceAfter: 8,
      },
    }));

    s.addText(textItems, {
      x: 0.7, y: 1.3, w: 8.6, h: 3.8,
      valign: "top",
    });
  }
}

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`pptx-service listening on :${PORT}`));
