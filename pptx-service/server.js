"use strict";

const express = require("express");
const { buildPptx } = require("./builder");
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
  console.log(`  - Slides: ${slides?.length || 0}, Theme: ${theme || "mckinsey"}, Design Spec: ${design_spec ? "present" : "none"}`);
  
  if (!Array.isArray(slides)) {
    console.log("  - ERROR: slides is not an array");
    return res.status(400).json({ error: "slides must be an array" });
  }
  try {
    const pptxBuffer = await buildPptx(slides, design_spec || {}, theme || "mckinsey");
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
// Returns: { images: ["data:image/jpeg;base64,...", ...] }
app.post("/preview", async (req, res) => {
  console.log(`[${new Date().toISOString()}] POST /preview - Received request`);
  const { slides, design_spec, theme } = req.body;
  console.log(`  - Slides: ${slides?.length || 0}, Theme: ${theme || "mckinsey"}, Design Spec: ${design_spec ? "present" : "none"}`);
  
  if (!Array.isArray(slides)) {
    console.log("  - ERROR: slides is not an array");
    return res.status(400).json({ error: "slides must be an array" });
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "pptx-preview-"));
  console.log(`  - Created temp dir: ${tmpDir}`);

  try {
    // 1. Build PPTX
    console.log("  - Building PPTX...");
    const pptxBuffer = await buildPptx(slides, design_spec || {}, theme || "mckinsey");
    console.log(`  - PPTX built: ${pptxBuffer.length} bytes`);
    const pptxPath = path.join(tmpDir, "presentation.pptx");
    fs.writeFileSync(pptxPath, pptxBuffer);

    // 2. Convert PPTX → PDF using LibreOffice headless
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

    // 3. Convert PDF pages → JPG images using pdftoppm
    console.log("  - Converting PDF to images...");
    const imgPrefix = path.join(tmpDir, "slide");
    execSync(
      `pdftoppm -jpeg -r 150 "${pdfPath}" "${imgPrefix}"`,
      { timeout: 60000, stdio: "pipe" }
    );

    // 4. Collect all slide-*.jpg files in order
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

    console.log(`  - SUCCESS: Returning ${images.length} images`);
    res.json({ images, count: images.length });

  } catch (err) {
    console.error("  - Preview generation error:", err.message);
    console.error("  - Stack:", err.stack);
    res.status(500).json({ error: err.message });
  } finally {
    // Cleanup temp files
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`pptx-service listening on :${PORT}`));
