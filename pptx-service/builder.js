"use strict";
const pptxgen = require("pptxgenjs");
const { iconToBase64 } = require("./icons");
const { getHexawareLogoBase64 } = require("./logo");

// ─── LAYOUT ───────────────────────────────────────────────────────────────────
// LAYOUT_16x9 = 10" × 5.625"
const W = 10;
const H = 5.625;

// ─── SHADOW FACTORY ───────────────────────────────────────────────────────────
// pptxgenjs mutates option objects in-place — always create fresh copies
const mkShadow = () => ({ type: "outer", blur: 8, offset: 3, angle: 135, color: "000000", opacity: 0.20 });
const mkShadowSm = () => ({ type: "outer", blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.12 });

// ─── PALETTE RESOLVER ─────────────────────────────────────────────────────────
// Uses DesignSpec from backend when available, falls back to Hexaware themes.
function resolveDesign(designSpec, theme) {
  // If we have a valid DesignSpec from the backend, use it
  if (designSpec && designSpec.primary_color) {
    console.log(`Using DesignSpec from backend: ${designSpec.palette_name || 'Custom'}`);
    return {
      // Use colors from DesignSpec (remove # prefix if present)
      navy:    designSpec.secondary_color?.replace('#', '') || "000080",
      teal:    designSpec.accent_color?.replace('#', '') || "000080", 
      tealDk:  designSpec.accent_color?.replace('#', '') || "000080",
      blue:    designSpec.secondary_color?.replace('#', '') || "000080", 
      blueLt:  designSpec.secondary_color?.replace('#', '') || "000080", 
      white:   "FFFFFF",
      offwhite:"FFFFFF", 
      slate:   designSpec.text_color?.replace('#', '') || "000000", 
      slateL:  designSpec.text_light_color?.replace('#', '') || "5A5A6A",
      dark:    designSpec.primary_color?.replace('#', '') || "000000", 
      gold:    designSpec.accent_color?.replace('#', '') || "000080", 
      green:   "22C55E",
      red:     "E63946", 
      cardBg:  "FFFFFF", 
      cardBg2: "FFFFFF",
      accent:  designSpec.accent_color?.replace('#', '') || "000080", 
      primary: designSpec.primary_color?.replace('#', '') || "000000", 
      secondary: designSpec.secondary_color?.replace('#', '') || "000080",
      text:    designSpec.text_color?.replace('#', '') || "000000", 
      textLight: designSpec.text_light_color?.replace('#', '') || "5A5A6A", 
      bg:      designSpec.background_color?.replace('#', '') || "FFFFFF", 
      bgDark:  designSpec.background_dark_color?.replace('#', '') || "000000",
      chartColors: designSpec.chart_colors?.map(c => c.replace('#', '')) || ["000080","FF6B35","22C55E","E63946","F5A623","8FA3B8","4A7FE8"],
      fontHeader: designSpec.font_header || "Calibri", 
      fontBody: designSpec.font_body || "Calibri",
    };
  }

  // Fallback to hardcoded Hexaware themes if no DesignSpec
  console.log(`Using fallback theme: ${theme}`);
  const THEMES = {
    // ── Hexaware Corporate ────────────────────────────────────────────────────
    // Deep navy primary, Navy Blue accent, WHITE background on ALL slides.
    hexaware_corporate: {
      // 3 colors only: BLUE=000080 (Navy Blue), BLACK=000000, WHITE=FFFFFF
      navy:    "000080", teal:    "000080", tealDk:  "000080",
      blue:    "000080", blueLt:  "000080", white:   "FFFFFF",
      offwhite:"FFFFFF", slate:   "000000", slateL:  "000000",
      dark:    "000000", gold:    "000080", green:   "000080",
      red:     "000080", cardBg:  "FFFFFF", cardBg2: "FFFFFF",
      accent:  "000080", primary: "000000", secondary:"000080",
      text:    "000000", textLight:"000000", bg:"FFFFFF", bgDark:"FFFFFF",
      chartColors:["000080","000080","000080","000080","000080","000080","000080"],
      fontHeader:"Calibri", fontBody:"Calibri",
    },
    // ── Hexaware Professional ─────────────────────────────────────────────────
    // Near-black primary, Hexaware orange accent, WHITE background on ALL slides.
    hexaware_professional: {
      navy:    "0D0D0D", teal:    "FF6B35", tealDk:  "CC4F1E",
      blue:    "000080", blueLt:  "4A7FE8", white:   "FFFFFF",
      offwhite:"F7F7F7", slate:   "5A5A6A", slateL:  "9A9AAA",
      dark:    "0D0D0D", gold:    "FF6B35", green:   "22C55E",
      red:     "E63946", cardBg:  "FFFFFF", cardBg2: "FFFFFF",
      accent:  "FF6B35", primary: "0D0D0D", secondary:"000080",
      text:    "0D0D0D", textLight:"5A5A6A", bg:"FFFFFF", bgDark:"FFFFFF",
      // Single chart color — all bars/segments use Hexaware orange
      chartColors:["FF6B35","FF6B35","FF6B35","FF6B35","FF6B35","FF6B35","FF6B35"],
      fontHeader:"Arial", fontBody:"Arial",
    },
  };

  // Unknown theme name falls back to hexaware_corporate.
  const resolvedKey = (theme === "hexaware_professional") ? "hexaware_professional" : "hexaware_corporate";
  const base = THEMES[resolvedKey];

  // Font overrides from designSpec if provided
  if (designSpec && (designSpec.font_header || designSpec.font_body)) {
    return {
      ...base,
      fontHeader: designSpec.font_header || base.fontHeader,
      fontBody:   designSpec.font_body   || base.fontBody,
    };
  }
  return base;
}

// ─── SHARED HEADER BAR ────────────────────────────────────────────────────────
// ─── SHARED HEADER BAR ────────────────────────────────────────────────────────
// BLUE header bar, WHITE title text — used on all non-title slides
function addSectionHeader(s, sectionLabel, C) {
  s.addShape("rect", { x:0, y:0, w:W, h:0.82, fill:{color:C.teal}, line:{color:C.teal} });
  s.addShape("rect", { x:0, y:0.82, w:W, h:0.04, fill:{color:"000000"}, line:{color:"000000"} });
  if (sectionLabel) {
    s.addText(sectionLabel, {
      x:0.45, y:0.1, w:W-0.9, h:0.62,
      fontSize:14, bold:true, color:"FFFFFF",
      fontFace:C.fontHeader, charSpacing:2, valign:"middle", margin:0,
    });
  }
}

// ─── MAIN ENTRY POINT ─────────────────────────────────────────────────────────
async function buildPptx(slides, designSpec, theme, metadata) {
  const C = resolveDesign(designSpec, theme);
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "AI-Generated Presentation";

  console.log(`\n=== Building PPTX with ${slides.length} slides ===`);
  console.log(`Theme: ${theme}`);
  console.log(`Design Spec:`, designSpec ? JSON.stringify(designSpec).substring(0, 200) : 'none');
  console.log(`Resolved Colors:`, {
    secondary: C.secondary,
    accent: C.accent,
    primary: C.primary,
    chartColors: C.chartColors
  });
  
  // Log first slide structure for debugging
  if (slides.length > 0) {
    console.log(`\nFirst slide structure:`);
    console.log(`  - type: ${slides[0].type}`);
    console.log(`  - title: ${slides[0].title}`);
    console.log(`  - content keys: ${Object.keys(slides[0].content || {}).join(', ')}`);
  }

  for (let i = 0; i < slides.length; i++) {
    const slide = slides[i];
    const type  = slide.type || "content";
    const isLast = i === slides.length - 1;
    const pSlide = pres.addSlide();

    console.log(`\nSlide ${i + 1}/${slides.length}: type="${type}", title="${slide.title || '(no title)'}"`);

    // All slides use white background (C.bg = FFFFFF for both themes)
    pSlide.background = { color: C.bg };

    switch (type) {
      case "title":      await buildTitle(pSlide, slide, C, metadata || {}); break;
      case "chart":      await buildChart(pSlide, slide, C, pres); break;
      case "table":      await buildTable(pSlide, slide, C); break;
      case "comparison": await buildComparison(pSlide, slide, C); break;
      case "metric":     await buildMetric(pSlide, slide, C); break;
      default:           await buildContent(pSlide, slide, C, isLast); break;
    }
  }

  console.log(`\n=== PPTX build complete ===\n`);
  return await pres.write({ outputType: "nodebuffer" });
}

// ─── TITLE SLIDE ──────────────────────────────────────────────────────────────────────────────────────────────
async function buildTitle(s, slide, C, metadata) {
  const content  = slide.content || {};
  const subtitle = content.subtitle || "";
  const bullets  = content.bullets || [];

  const preparedBy     = (metadata && metadata.prepared_by)    || "Hexaware";
  const preparedDate   = (metadata && metadata.date)           || new Date().toLocaleDateString("en-US", { year:"numeric", month:"long", day:"numeric" });
  const classification = (metadata && metadata.classification) || "Confidential - Internal Use Only";

  const isThankYou = slide.title && (
    slide.title.toLowerCase().includes("thank you") ||
    slide.title.toLowerCase().includes("thank-you") ||
    slide.title.toLowerCase().includes("thanks")
  );

  // Chrome: left stripe + top bar
  s.addShape("rect", { x:0, y:0, w:0.12, h:H, fill:{color:C.teal}, line:{color:C.teal} });
  s.addShape("rect", { x:0.12, y:0, w:W-0.12, h:0.06, fill:{color:C.teal}, line:{color:C.teal} });

  // Logo top-right corner - larger size, perfectly aligned with borders
  const logoData = await getHexawareLogoBase64(180, 45); // Larger logo: 180x45 pixels
  if (logoData) s.addImage({ data: logoData, x: W - 1.8, y: 0.02, w: 1.75, h: 0.45 }); // Larger dimensions, aligned to top-right

  // ─── LAYOUT (H = 5.625") ────────────────────────────────────────────────────
  //
  //  Title        y=0.55  h=1.60   ← tall box, text never overflows
  //  Subtitle     y=2.25  h=0.40   ← 0.10" gap after title box ends at 2.15"
  //  Divider      y=2.75  h=0.04
  //  KPI cards    y=3.00  h=1.80   ← uses the big empty middle space
  //  Info row     y=4.90  h=0.35   ← bottom, above copyright
  //  Copyright    y=5.445 h=0.18   ← inside teal strip
  //
  // ────────────────────────────────────────────────────────────────────────────

  if (isThankYou) {
    s.addText(slide.title || "Thank You", {
      x:0.45, y:1.6, w:9.1, h:1.6,
      fontSize:52, bold:true, color:C.primary,
      fontFace:C.fontHeader, align:"center", valign:"middle", margin:0,
    });
    if (subtitle) {
      s.addText(subtitle, {
        x:0.45, y:3.3, w:9.1, h:0.5,
        fontSize:20, color:C.teal, fontFace:C.fontBody,
        align:"center", valign:"middle", margin:0,
      });
    }
  } else {
    const titleText  = slide.title || "Presentation";
    const titleWords = titleText.split(/\s+/).length;
    // Font size scales down for longer titles — box is always 1.60" tall
    const titleFontSize = titleWords > 12 ? 22 : titleWords > 8 ? 26 : 32;

    // Title — 1.60" tall box guarantees no overflow into subtitle
    s.addText(titleText, {
      x:0.45, y:0.55, w:7.8, h:1.60,
      fontSize:titleFontSize, bold:true, color:C.primary,
      fontFace:C.fontHeader, valign:"middle", margin:0,
    });

    // Subtitle — starts at y=2.25, always 0.10" below the title box
    if (subtitle) {
      s.addText(subtitle, {
        x:0.45, y:2.25, w:7.8, h:0.40,
        fontSize:14, color:C.teal, fontFace:C.fontBody, italic:true,
        valign:"middle", margin:0,
      });
    }

    // Divider
    s.addShape("rect", { x:0.45, y:2.75, w:9.1, h:0.04, fill:{color:C.teal}, line:{color:C.teal} });

    // KPI cards — use the large empty space in the middle
    const kpis = bullets.slice(0, 4);
    if (kpis.length > 0) {
      const kpiY = 3.00;
      const kpiH = 1.80;   // tall — uses the empty space
      const kpiW = (9.1 - (kpis.length - 1) * 0.15) / kpis.length;
      kpis.forEach((kpi, i) => {
        const bx = 0.45 + i * (kpiW + 0.15);
        s.addShape("rect", {
          x:bx, y:kpiY, w:kpiW, h:kpiH,
          fill:{color:"FFFFFF"}, line:{color:C.navy, width:2},
          shadow:mkShadow(),
        });
        s.addText(kpi, {
          x:bx+0.10, y:kpiY+0.10, w:kpiW-0.20, h:kpiH-0.20,
          fontSize:12, bold:false, color:C.navy,
          align:"center", valign:"middle",
          fontFace:C.fontBody, margin:8,
        });
      });
    }

    // Info row — bottom of slide, above copyright strip
    const infoItems = [
      { label: "Prepared by:",    value: preparedBy },
      { label: "Date:",           value: preparedDate },
      { label: "Classification:", value: classification },
    ];
    infoItems.forEach((item, i) => {
      s.addText([
        { text: item.label + "  ", options: { bold: true,  color: C.primary, fontSize: 9 } },
        { text: item.value,        options: { bold: false, color: C.text,    fontSize: 9 } },
      ], {
        x: 0.45 + i * 3.05, y: 4.90, w: 3.0, h: 0.35,
        fontFace: C.fontBody, valign: "middle", margin: 0,
      });
    });
  }

  // Copyright strip
  s.addShape("rect", { x:0, y:H-0.18, w:W, h:0.18, fill:{color:C.teal}, line:{color:C.teal} });
  s.addText("Copyright \u00A9 2026 Hexaware Technologies Limited. All rights reserved.", {
    x:0.18, y:H-0.18, w:W-0.36, h:0.18,
    fontSize:7, bold:false, color:"FFFFFF", fontFace:C.fontBody,
    align:"left", valign:"middle", margin:0,
  });

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── CONTENT SLIDE ──────────────────────────────────────────────────────────────────────────────
async function buildContent(s, slide, C, isDark) {
  const content   = slide.content || {};
  const bullets   = content.bullets || [];
  const iconName  = content.icon_name || null;
  const highlight = content.highlight_text || null;

  addSectionHeader(s, null, C);

  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  let iconW = 0;
  if (iconName) {
    const ic = await iconToBase64(iconName, "#000080", 256);
    if (ic) {
      s.addShape("ellipse", {
        x:W-1.55, y:0.92, w:1.15, h:1.15,
        fill:{color:"FFFFFF"}, line:{color:C.secondary, width:1.5},
        shadow:mkShadowSm(),
      });
      s.addImage({ data:ic, x:W-1.42, y:1.05, w:0.88, h:0.88 });
      iconW = 1.65;
    }
  }

  // Bullet cards — white bg, blue left border, black text
  const contentW = W - 0.8 - iconW;
  const hasHighlight = !!highlight;
  const maxBullets = 4; // Fixed to match layout validation limit

  bullets.slice(0, maxBullets).forEach((bullet, i) => {
    const by = 0.97 + i * 0.88;
    // Improved overflow check - ensure bullet card fits completely
    if (by + 0.78 > H - (hasHighlight ? 1.0 : 0.2)) return;

    s.addShape("rect", {
      x:0.4, y:by, w:contentW, h:0.78,
      fill:{color:"FFFFFF"}, line:{color:C.secondary, width:0.5},
      shadow:mkShadowSm(),
    });
    // Blue left accent strip (6px ≈ 0.06")
    s.addShape("rect", { x:0.4, y:by, w:0.06, h:0.78, fill:{color:C.secondary}, line:{color:C.secondary} });
    // Number badge — white bg, Navy Blue border and number
    s.addShape("rect", { x:0.52, y:by+0.13, w:0.38, h:0.52, fill:{color:"FFFFFF"}, line:{color:C.secondary, width:1.5} });
    s.addText(String(i + 1), {
      x:0.52, y:by+0.13, w:0.38, h:0.52,
      fontSize:12, bold:true, color:"000080",
      align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
    });
    // Extract bullet text - handle string, dict with 'text' key, or any object
    let bulletText = "";
    if (typeof bullet === 'string') {
      bulletText = bullet;
    } else if (typeof bullet === 'object' && bullet !== null) {
      // Try to extract text from object
      bulletText = bullet.text || bullet.content || bullet.value || JSON.stringify(bullet);
    } else {
      bulletText = String(bullet);
    }
    // Truncate bullet text to prevent overflow
    const truncatedText = bulletText.split(' ').slice(0, 8).join(' ');
    s.addText(truncatedText, {
      x:1.0, y:by+0.08, w:contentW-0.68, h:0.62,
      fontSize:11.5, color:"000000", fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  if (highlight) {
    s.addShape("rect", {
      x:0.4, y:H-0.95, w:W-0.8, h:0.80,  // Increased height for better text fit
      fill:{color:"FFFFFF"}, line:{color:C.secondary, width:1},
      shadow:mkShadow(),
    });
    // Navy Blue left accent strip (0.12" wide)
    s.addShape("rect", {
      x:0.3, y:H-0.95, w:0.12, h:0.80,
      fill:{color:"000080"}, line:{color:"000080"},

    });
    // Truncate highlight text to prevent overflow
    const truncatedHighlight = highlight.split(' ').slice(0, 15).join(' ');
    s.addText("▶  " + truncatedHighlight, {
      x:0.4, y:H-0.95, w:W-0.8, h:0.80,
      fontSize:11, bold:true, color:"000080",
      align:"left", valign:"middle", fontFace:C.fontBody, margin:6,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── CHART SLIDE ──────────────────────────────────────────────────────────────────────────────
async function buildChart(s, slide, C, pres) {
  const content   = slide.content || {};
  const chartType = (content.chart_type || "bar").toLowerCase();
  const chartData = content.chart_data || [];
  const highlight = content.highlight_text || null;
  const bullets   = content.bullets || [];
  const hasBullets = bullets.length > 0;

  // ── Header bar ──
  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  // ── Layout ──
  // With bullets: left panel 32% (insight cards) + right 65% (chart card)
  // Without bullets: full-width chart card
  const panelTop = 0.97;
  const panelH   = H - panelTop - (highlight ? 0.95 : 0.25);  // Increased bottom margin for highlight
  const leftW    = hasBullets ? 3.0 : 0;
  const gap      = hasBullets ? 0.25 : 0;
  const chartX   = 0.3 + leftW + gap;
  const chartW   = W - chartX - 0.3;
  const chartY   = panelTop;
  const chartH   = panelH;

  // ── Chart card: white bg, blue border, blue top accent ──
  if (chartData.length > 0) {
    // Card background
    s.addShape("rect", {
      x:chartX, y:chartY, w:chartW, h:chartH,
      fill:{color:"FFFFFF"}, line:{color:C.secondary, width:1},
      shadow:mkShadow(),
    });
    // Navy Blue left accent strip (0.12" wide)
    s.addShape("rect", {
      x:0.3, y:H-0.95, w:0.12, h:0.80,
      fill:{color:"000080"}, line:{color:"000080"},

    });
    // Blue top accent bar on chart card
    s.addShape("rect", {
      x:chartX, y:chartY, w:chartW, h:0.06,
      fill:{color:C.secondary}, line:{color:C.secondary},
    });

    const labels = chartData.map(d => String(d.label || d.name || ""));
    const values = chartData.map(d => Number(d.value || d.y || 0));

    // Inner chart area — inset from card edges
    const cx = chartX + 0.15;
    const cy = chartY + 0.18;
    const cw = chartW - 0.30;
    const ch = chartH - 0.30;

    let pptxType, chartOpts;
    const baseOpts = {
      x:cx, y:cy, w:cw, h:ch,
      chartColors: C.chartColors,
      chartArea: { fill:{color:"FFFFFF"}, roundedCorners:false },
      plotArea: { fill:{color:"FFFFFF"} },
      catAxisLabelColor:"000000", valAxisLabelColor:"000000",
      catAxisLabelFontSize:9, valAxisLabelFontSize:9,
      valGridLine:{color:"DDDDDD", size:0.5, style:"dash"},
      catGridLine:{style:"none"},
      valAxisLineShow:false, catAxisLineShow:true,
      showLegend:false,
    };

    if (chartType === "pie" || chartType === "donut") {
      pptxType = pres.charts.PIE;
      chartOpts = { ...baseOpts,
        showLegend:true, legendPos:"b", legendFontSize:9, legendColor:"000000",
        showPercent:true, dataLabelFontSize:10, dataLabelColor:"FFFFFF",
        dataLabelPosition:"bestFit",
      };
    } else if (chartType === "line" || chartType === "line_smooth") {
      pptxType = pres.charts.LINE;
      chartOpts = { ...baseOpts,
        lineSize:3, lineSmooth:(chartType === "line_smooth"),
        showValue:true, dataLabelFontSize:8, dataLabelColor:"000000",
        dataLabelPosition:"t",
        showMarker:true,
      };
    } else if (chartType === "area" || chartType === "stacked_area") {
      pptxType = pres.charts.AREA;
      chartOpts = { ...baseOpts, showValue:false };
    } else if (chartType === "stacked_bar") {
      pptxType = pres.charts.BAR;
      chartOpts = { ...baseOpts,
        barDir:"col", barGrouping:"stacked",
        showValue:true, dataLabelFontSize:8, dataLabelColor:"FFFFFF",
        dataLabelPosition:"ctr",
        showLegend:true, legendPos:"b", legendFontSize:9,
      };
    } else {
      // Default: column bar — clean, value labels on top
      pptxType = pres.charts.BAR;
      chartOpts = { ...baseOpts,
        barDir:"col", barGapWidthPct:55,
        showValue:true, dataLabelPosition:"outEnd",
        dataLabelFontSize:9, dataLabelColor:"000000",
        dataLabelBold:true,
      };
    }

    s.addChart(pptxType, [{ name: slide.title || "Data", labels, values }], chartOpts);
  }

  // ── Left insight panel ──
  if (hasBullets) {
    bullets.slice(0, 4).forEach((b, i) => {  // Limit to 4 bullets max
      const by = panelTop + i * ((panelH - 0.1) / Math.min(bullets.length, 4));  // Use 4 instead of 5
      const bh = (panelH - 0.1) / Math.min(bullets.length, 4) - 0.08;
      // Strict overflow check - use >= to prevent touching boundaries
      if (by + bh >= H - (highlight ? 0.95 : 0.25)) return;

      // Card: white bg, blue left accent bar
      s.addShape("rect", {
        x:0.3, y:by, w:leftW, h:bh,
        fill:{color:"FFFFFF"}, line:{color:C.secondary, width:0.5},
        shadow:mkShadowSm(),
      });
      // Blue left accent
      s.addShape("rect", { x:0.3, y:by, w:0.06, h:bh, fill:{color:C.secondary}, line:{color:C.secondary} });
      // Extract bullet text - handle string, dict with 'text' key, or any object
      let bulletText = "";
      if (typeof b === 'string') {
        bulletText = b;
      } else if (typeof b === 'object' && b !== null) {
        bulletText = b.text || b.content || b.value || JSON.stringify(b);
      } else {
        bulletText = String(b);
      }
      // Truncate bullet text to prevent overflow
      const truncatedText = bulletText.split(' ').slice(0, 8).join(' ');
      s.addText(truncatedText, {
        x:0.42, y:by+0.06, w:leftW-0.18, h:bh-0.12,
        fontSize:9.5, color:"000000", fontFace:C.fontBody, valign:"middle", margin:0,
      });
    });
  }

  // ── Highlight callout strip ──
  if (highlight) {
    s.addShape("rect", {
      x:0.42, y:H-0.95, w:W-0.72, h:0.80,  // Increased height for better text fit
      fill:{color:"FFFFFF"}, line:{color:"000080", width:1},
      shadow:mkShadow(),
    });
    // Navy Blue left accent strip (0.12" wide)
    s.addShape("rect", {
      x:0.3, y:H-0.95, w:0.12, h:0.80,
      fill:{color:"000080"}, line:{color:"000080"},

    });
    // Truncate highlight text to prevent overflow
    const truncatedHighlight = highlight.split(' ').slice(0, 15).join(' ');
    s.addText("▶  " + truncatedHighlight, {
      x:0.42, y:H-0.95, w:W-0.72, h:0.80,
      fontSize:10.5, bold:true, color:"000080",
      align:"left", valign:"middle", fontFace:C.fontBody, margin:6,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── TABLE SLIDE ──────────────────────────────────────────────────────────────────────────────
async function buildTable(s, slide, C) {
  const content   = slide.content || {};
  const tableData = content.table_data || {};
  const headers   = tableData.headers || [];
  const rows      = tableData.rows    || [];
  const highlight = content.highlight_text || null;
  const bullets   = content.bullets || [];

  // ── Header bar ──
  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  if (headers.length > 0 && rows.length > 0) {
    const tableY  = 0.97;
    const tableH  = H - tableY - (highlight ? 0.95 : 0.25) - (bullets.length > 0 ? 0 : 0);  // Increased bottom margin
    const tableW  = W - 0.6;
    const maxRows = highlight ? 6 : 8;  // Reduced max rows to prevent overflow
    const limitedRows = rows.slice(0, maxRows);
    const colCount = headers.length;

    // Column widths: first col slightly wider (row labels)
    const firstColW = tableW * 0.28;
    const restColW  = (tableW - firstColW) / Math.max(colCount - 1, 1);
    const colWidths = [firstColW, ...Array(Math.max(colCount - 1, 0)).fill(restColW)];

    // ── Table card: white bg, blue border, blue top accent ──
    s.addShape("rect", {
      x:0.3, y:tableY, w:tableW, h:tableH,
      fill:{color:"FFFFFF"}, line:{color:C.secondary, width:1},
      shadow:mkShadow(),
    });
    // Navy Blue left accent strip (0.12" wide)
    s.addShape("rect", {
      x:0.3, y:H-0.95, w:0.12, h:0.80,
      fill:{color:"000080"}, line:{color:"000080"},

    });
    s.addShape("rect", {
      x:0.3, y:tableY, w:tableW, h:0.06,
      fill:{color:C.secondary}, line:{color:C.secondary},
    });

    // ── Header row ──
    const headerRow = headers.map((h, ci) => ({
      text: String(h),
      options: {
        fill:{color:"FFFFFF"}, color:"000080", bold:true,
        fontSize:11, fontFace:C.fontBody,
        align: ci === 0 ? "left" : "center",
        valign:"middle",
        margin:[0, 8, 0, 8],
        border:{pt:0},
      },
    }));

    // ── Data rows: alternating white / very light blue tint ──
    const dataRows = limitedRows.map((row, ri) => {
      const rowArr = Array.isArray(row) ? row : [row];
      return rowArr.map((cell, ci) => ({
        text: String(cell ?? ""),
        options: {
          fill:{color: ri % 2 === 0 ? "FFFFFF" : "EEF3FF"},
          color:"000000",
          bold: ci === 0,   // first column bold (row label)
          fontSize:10, fontFace:C.fontBody,
          align: ci === 0 ? "left" : "center",
          valign:"middle",
          margin:[0, 8, 0, 8],
          border:{pt:0.5, color:C.secondary},
        },
      }));
    });

    s.addTable([headerRow, ...dataRows], {
      x:0.3, y:tableY, w:tableW, h:tableH,
      colW: colWidths,
      rowH: 0.42,
    });
  }

  // ── Bullet insights as a horizontal strip below table ──
  if (bullets.length > 0 && !highlight) {
    const stripY = H - 0.72;
    const bw = (W - 0.6 - (bullets.length - 1) * 0.12) / Math.min(bullets.length, 4);
    bullets.slice(0, 4).forEach((b, i) => {
      const bx = 0.3 + i * (bw + 0.12);
      // White bg, blue left border, black text
      s.addShape("rect", {
        x:bx, y:stripY, w:bw, h:0.54,
        fill:{color:"FFFFFF"}, line:{color:C.secondary, width:0.5},
        shadow:mkShadowSm(),
      });
      s.addShape("rect", {
        x:bx, y:stripY, w:0.06, h:0.54,
        fill:{color:C.secondary}, line:{color:C.secondary},
      });
      // Extract bullet text - handle string, dict with 'text' key, or any object
      let bulletText = "";
      if (typeof b === 'string') {
        bulletText = b;
      } else if (typeof b === 'object' && b !== null) {
        bulletText = b.text || b.content || b.value || JSON.stringify(b);
      } else {
        bulletText = String(b);
      }
      s.addText(bulletText, {
        x:bx+0.12, y:stripY+0.04, w:bw-0.20, h:0.46,
        fontSize:8.5, color:"000000", fontFace:C.fontBody,
        align:"left", valign:"middle", margin:4,
      });
    });
  }

  // ── Highlight callout strip ──
  if (highlight) {
    s.addShape("rect", {
      x:0.42, y:H-0.95, w:W-0.72, h:0.80,  // Increased height for better text fit
      fill:{color:"FFFFFF"}, line:{color:"000080", width:1},
      shadow:mkShadow(),
    });
    // Navy Blue left accent strip (0.12" wide)
    s.addShape("rect", {
      x:0.3, y:H-0.95, w:0.12, h:0.80,
      fill:{color:"000080"}, line:{color:"000080"},

    });
    // Truncate highlight text to prevent overflow
    const truncatedHighlight = highlight.split(' ').slice(0, 15).join(' ');
    s.addText("▶  " + truncatedHighlight, {
      x:0.42, y:H-0.95, w:W-0.72, h:0.80,
      fontSize:10.5, bold:true, color:"000080",
      align:"left", valign:"middle", fontFace:C.fontBody, margin:6,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── COMPARISON SLIDE ─────────────────────────────────────────────────────────
async function buildComparison(s, slide, C) {
  const content = slide.content || {};
  const comp    = content.comparison_data || {};
  const highlight = content.highlight_text || null;

  console.log(`[DEBUG] Comparison slide data:`, JSON.stringify(comp, null, 2));

  let leftH = "", rightH = "", leftItems = [], rightItems = [];
  if (comp.left_column) {
    leftH = comp.left_column.heading || comp.left_column.title || "";
    leftItems = comp.left_column.bullets || comp.left_column.items || [];
  } else {
    leftH = comp.left_title || "Option A";
    leftItems = comp.left || [];
  }
  if (comp.right_column) {
    rightH = comp.right_column.heading || comp.right_column.title || "";
    rightItems = comp.right_column.bullets || comp.right_column.items || [];
  } else {
    rightH = comp.right_title || "Option B";
    rightItems = comp.right || [];
  }

  console.log(`[DEBUG] Extracted leftItems:`, JSON.stringify(leftItems));
  console.log(`[DEBUG] Extracted rightItems:`, JSON.stringify(rightItems));

  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  const colW = (W - 1.0) / 2;
  const colY = 0.92;
  const colH = H - colY - (highlight ? 0.95 : 0.25);  // Increased bottom margin for highlight

  // ── Left column ──
  s.addShape("rect", {
    x:0.3, y:colY, w:colW, h:colH,
    fill:{color:"FFFFFF"}, line:{color:"000080", width:1},
  });
  s.addShape("rect", { x:0.3, y:colY, w:colW, h:0.55, fill:{color:"FFFFFF"}, line:{color:"000080", width:2} });
  s.addText(leftH, {
    x:0.3, y:colY, w:colW, h:0.55,
    fontSize:14, bold:true, color:"000080",
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  leftItems.slice(0, 4).forEach((item, i) => {  // Limit to 4 items max
    const iy = colY + 0.62 + i * 0.55;
    // Strict overflow check - use >= to prevent touching boundaries
    if (iy + 0.50 >= colY + colH) return;
    s.addShape("rect", {
      x:0.35, y:iy, w:colW-0.1, h:0.50,
      fill:{color:"FFFFFF"}, line:{color:"000080", width:0.5},
    });
    // Extract item text - handle string, dict with 'text' key, or any object
    let itemText = "";
    if (typeof item === 'string') {
      itemText = item;
    } else if (typeof item === 'object' && item !== null) {
      itemText = item.text || item.content || item.value || JSON.stringify(item);
    } else {
      itemText = String(item);
    }
    // Truncate item text to prevent overflow
    const truncatedText = itemText.split(' ').slice(0, 8).join(' ');
    console.log(`[DEBUG] Left item ${i}: type=${typeof item}, value=${JSON.stringify(item)}, extracted=${truncatedText}`);
    s.addText([
      { text:"›  ", options:{color:"000080", bold:true} },
      { text:truncatedText, options:{color:"000000"} },
    ], {
      x:0.42, y:iy+0.04, w:colW-0.24, h:0.42,
      fontSize:10.5, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // ── Right column ──
  const rx = 0.3 + colW + 0.4;
  s.addShape("rect", {
    x:rx, y:colY, w:colW, h:colH,
    fill:{color:"FFFFFF"}, line:{color:"000080", width:1},
  });
  s.addShape("rect", { x:rx, y:colY, w:colW, h:0.55, fill:{color:"FFFFFF"}, line:{color:"000080", width:2} });
  s.addText(rightH, {
    x:rx, y:colY, w:colW, h:0.55,
    fontSize:14, bold:true, color:"000080",
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  rightItems.slice(0, 4).forEach((item, i) => {  // Limit to 4 items max
    const iy = colY + 0.62 + i * 0.55;
    // Strict overflow check - use >= to prevent touching boundaries
    if (iy + 0.50 >= colY + colH) return;
    s.addShape("rect", {
      x:rx+0.05, y:iy, w:colW-0.1, h:0.50,
      fill:{color:"FFFFFF"}, line:{color:"000080", width:0.5},
    });
    // Extract item text - handle string, dict with 'text' key, or any object
    let itemText = "";
    if (typeof item === 'string') {
      itemText = item;
    } else if (typeof item === 'object' && item !== null) {
      itemText = item.text || item.content || item.value || JSON.stringify(item);
    } else {
      itemText = String(item);
    }
    // Truncate item text to prevent overflow
    const truncatedText = itemText.split(' ').slice(0, 8).join(' ');
    console.log(`[DEBUG] Right item ${i}: type=${typeof item}, value=${JSON.stringify(item)}, extracted=${truncatedText}`);
    s.addText([
      { text:"›  ", options:{color:"000080", bold:true} },
      { text:truncatedText, options:{color:"000000"} },
    ], {
      x:rx+0.12, y:iy+0.04, w:colW-0.24, h:0.42,
      fontSize:10.5, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // Vertical divider - Navy Blue line only (no fill)
  s.addShape("line", {
    x:0.3 + colW + 0.20, y:colY, w:0, h:colH,
    line:{color:"000080", width:2},
  });

  if (highlight) {
    s.addShape("rect", {
      x:0.42, y:H-0.95, w:W-0.72, h:0.80,  // Increased height for better text fit
      fill:{color:"FFFFFF"}, line:{color:"000080", width:1},
      shadow:mkShadow(),
    });
    // Navy Blue left accent strip (0.12" wide)
    s.addShape("rect", {
      x:0.3, y:H-0.95, w:0.12, h:0.80,
      fill:{color:"000080"}, line:{color:"000080"},

    });
    // Truncate highlight text to prevent overflow
    const truncatedHighlight = highlight.split(' ').slice(0, 15).join(' ');
    s.addText("▶  " + truncatedHighlight, {
      x:0.42, y:H-0.95, w:W-0.72, h:0.80,
      fontSize:10.5, bold:true, color:"000080",
      align:"left", valign:"middle", fontFace:C.fontBody, margin:6,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── METRIC SLIDE ─────────────────────────────────────────────────────────────
async function buildMetric(s, slide, C) {
  const content = slide.content || {};
  const val     = content.metric_value || "—";
  const label   = content.metric_label || "";
  const trend   = content.metric_trend || "";
  const bullets = content.bullets || [];
  const iconName = content.icon_name || null;

  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  // ── Big KPI card (left 44%) ──
  const cardW = W * 0.44;
  const cardH = H - 1.05;
  s.addShape("rect", {
    x:0.3, y:0.92, w:cardW, h:cardH,
    fill:{color:"FFFFFF"}, line:{color:"000080", width:2},
    shadow:mkShadow(),
    });
    // Navy Blue left accent strip (0.12" wide)
    s.addShape("rect", {
      x:0.3, y:H-0.95, w:0.12, h:0.80,
      fill:{color:"000080"}, line:{color:"000080"},

  });

  // Icon — white circle, blue icon
  if (iconName) {
    const ic = await iconToBase64(iconName, "#FFFFFF", 256);
    if (ic) {
      s.addShape("ellipse", {
        x:0.3+cardW/2-0.5, y:1.00, w:1.0, h:1.0,
        fill:{color:"FFFFFF"}, line:{color:"000080", width:1.5},
      });
      s.addImage({ data:ic, x:0.3+cardW/2-0.4, y:1.05, w:0.8, h:0.8 });
    }
  }

  // Big number
  s.addText(val, {
    x:0.3, y:1.95, w:cardW, h:1.4,
    fontSize:56, bold:true, color:"000080",
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  // Label
  if (label) {
    s.addText(label, {
      x:0.3, y:3.4, w:cardW, h:0.5,
      fontSize:13, color:C.teal, align:"center", fontFace:C.fontBody, margin:0,
    });
  }

  // Trend badge
  if (trend) {
    const trendColor = "000080";
    s.addShape("rect", {
      x:0.3+cardW/2-1.0, y:3.95, w:2.0, h:0.38,
      fill:{color:trendColor, transparency:15}, line:{color:trendColor, width:0.5},
    });
    s.addText(trend, {
      x:0.3+cardW/2-1.0, y:3.95, w:2.0, h:0.38,
      fontSize:11, bold:true, color:"FFFFFF",
      align:"center", valign:"middle", fontFace:C.fontBody, margin:0,
    });
  }

  // ── Right: context bullets as numbered cards ──
  const rx = 0.3 + cardW + 0.4;
  const rw = W - rx - 0.25;
  bullets.slice(0, 4).forEach((b, i) => {
    const by = 0.97 + i * 1.08;
    // Strict overflow check - use >= to prevent touching boundaries
    if (by + 0.95 >= H - 0.25) return;  // Increased bottom margin from 0.15 to 0.25
    // White bg, blue left border, black text
    s.addShape("rect", {
      x:rx, y:by, w:rw, h:0.95,
      fill:{color:"FFFFFF"}, line:{color:"000080", width:0.5},
      shadow:mkShadowSm(),
    });
    // Blue left accent strip
    s.addShape("rect", { x:rx, y:by, w:0.06, h:0.95, fill:{color:"000080"}, line:{color:"000080"} });
    // Number badge — white bg, Navy Blue border and number
    s.addShape("rect", { x:rx+0.12, y:by+0.22, w:0.45, h:0.50, fill:{color:"FFFFFF"}, line:{color:"000080", width:1.5} });
    s.addText(String(i + 1), {
      x:rx+0.12, y:by+0.22, w:0.45, h:0.50,
      fontSize:13, bold:true, color:"000080",
      align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
    });
    // Extract bullet text - handle string, dict with 'text' key, or any object
    let bulletText = "";
    if (typeof b === 'string') {
      bulletText = b;
    } else if (typeof b === 'object' && b !== null) {
      bulletText = b.text || b.content || b.value || JSON.stringify(b);
    } else {
      bulletText = String(b);
    }
    // Truncate bullet text to prevent overflow
    const truncatedText = bulletText.split(' ').slice(0, 8).join(' ');
    s.addText(truncatedText, {
      x:rx+0.65, y:by+0.08, w:rw-0.75, h:0.79,
      fontSize:11, color:"000000", fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

module.exports = { buildPptx };
