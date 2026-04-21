"use strict";
const pptxgen = require("pptxgenjs");
const { iconToBase64 } = require("./icons");

// ─── LAYOUT ───────────────────────────────────────────────────────────────────
// LAYOUT_16x9 = 10" × 5.625"
const W = 10;
const H = 5.625;

// ─── SHADOW FACTORY ───────────────────────────────────────────────────────────
// pptxgenjs mutates option objects in-place — always create fresh copies
const mkShadow = () => ({ type: "outer", blur: 8, offset: 3, angle: 135, color: "000000", opacity: 0.20 });
const mkShadowSm = () => ({ type: "outer", blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.12 });

// ─── PALETTE RESOLVER ─────────────────────────────────────────────────────────
function resolveDesign(designSpec, theme) {
  // Built-in palettes — dark, rich, enterprise-grade
  const THEMES = {
    mckinsey: {
      navy:    "0D1B2A", teal:    "00C9B1", tealDk:  "009B89",
      blue:    "1B4F8A", blueLt:  "2A6FC4", white:   "FFFFFF",
      offwhite:"F0F4F8", slate:   "64748B", slateL:  "94A3B8",
      dark:    "0A0F1A", gold:    "FFB81C", green:   "22C55E",
      red:     "EF4444", cardBg:  "112240", cardBg2: "162B4A",
      accent:  "00C9B1", primary: "0D1B2A", secondary:"1B4F8A",
      text:    "1A1A1A", textLight:"64748B", bg:"F0F4F8", bgDark:"0A0F1A",
      chartColors:["1B4F8A","00C9B1","FFB81C","22C55E","EF4444","818CF8","F97316"],
      fontHeader:"Calibri", fontBody:"Calibri",
    },
    deloitte: {
      navy:    "000000", teal:    "86BC25", tealDk:  "5A8A00",
      blue:    "00B4CC", blueLt:  "33C9DD", white:   "FFFFFF",
      offwhite:"F5F5F5", slate:   "64748B", slateL:  "94A3B8",
      dark:    "000000", gold:    "FF8C00", green:   "86BC25",
      red:     "EF4444", cardBg:  "0A0A0A", cardBg2: "111111",
      accent:  "86BC25", primary: "000000", secondary:"00B4CC",
      text:    "1A1A1A", textLight:"64748B", bg:"FFFFFF", bgDark:"000000",
      chartColors:["86BC25","00B4CC","FF8C00","662D91","009639","EF4444","F97316"],
      fontHeader:"Arial", fontBody:"Arial",
    },
    dark_modern: {
      navy:    "1E2761", teal:    "CADCFC", tealDk:  "7EC8E3",
      blue:    "2A6FC4", blueLt:  "4A8FE4", white:   "FFFFFF",
      offwhite:"E8EDF5", slate:   "94A3B8", slateL:  "CBD5E1",
      dark:    "0A0F1A", gold:    "F5A623", green:   "22C55E",
      red:     "EF4444", cardBg:  "1E2761", cardBg2: "162040",
      accent:  "CADCFC", primary: "1E2761", secondary:"2A6FC4",
      text:    "E8EDF5", textLight:"94A3B8", bg:"0F172A", bgDark:"0A0F1A",
      chartColors:["CADCFC","7EC8E3","A8D8EA","4A8FE4","F5A623","22C55E","EF4444"],
      fontHeader:"Calibri", fontBody:"Calibri",
    },
  };

  const base = THEMES[theme] || THEMES["mckinsey"];
  if (!designSpec || !designSpec.primary_color) return base;

  const h = (v, fb) => {
    if (!v) return fb;
    const s = String(v).replace("#", "");
    return /^[0-9A-Fa-f]{6}$/.test(s) ? s.toUpperCase() : fb;
  };

  return {
    ...base,
    primary:    h(designSpec.primary_color,         base.primary),
    secondary:  h(designSpec.secondary_color,       base.secondary),
    accent:     h(designSpec.accent_color,          base.accent),
    teal:       h(designSpec.accent_color,          base.teal),
    dark:       h(designSpec.background_dark_color, base.dark),
    bgDark:     h(designSpec.background_dark_color, base.bgDark),
    chartColors: Array.isArray(designSpec.chart_colors)
      ? designSpec.chart_colors.map(c => h(c, base.chartColors[0]))
      : base.chartColors,
    fontHeader: designSpec.font_header || base.fontHeader,
    fontBody:   designSpec.font_body   || base.fontBody,
  };
}

// ─── SHARED HEADER BAR ────────────────────────────────────────────────────────
// Dark header with section label — used on all non-title slides
function addSectionHeader(s, sectionLabel, C) {
  s.addShape("rect", { x:0, y:0, w:W, h:0.82, fill:{color:C.dark}, line:{color:C.dark} });
  s.addShape("rect", { x:0, y:0.82, w:W, h:0.05, fill:{color:C.teal}, line:{color:C.teal} });
  if (sectionLabel) {
    s.addText(sectionLabel, {
      x:0.45, y:0.1, w:W-0.9, h:0.62,
      fontSize:14, bold:true, color:C.teal,
      fontFace:C.fontHeader, charSpacing:2, valign:"middle", margin:0,
    });
  }
}

// ─── MAIN ENTRY POINT ─────────────────────────────────────────────────────────
async function buildPptx(slides, designSpec, theme) {
  const C = resolveDesign(designSpec, theme);
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "AI-Generated Presentation";

  console.log(`\n=== Building PPTX with ${slides.length} slides ===`);
  console.log(`Theme: ${theme}`);
  console.log(`Design Spec:`, designSpec ? JSON.stringify(designSpec).substring(0, 200) : 'none');
  
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

    // Dark background for title + last slide; light for everything else
    const useDark = (type === "title" || isLast);
    pSlide.background = { color: useDark ? C.bgDark : C.bg };

    switch (type) {
      case "title":      await buildTitle(pSlide, slide, C); break;
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

// ─── TITLE SLIDE ──────────────────────────────────────────────────────────────
async function buildTitle(s, slide, C) {
  const content  = slide.content || {};
  const subtitle = content.subtitle || "";
  const bullets  = content.bullets || [];
  const iconName = content.icon_name || null;
  
  // Check if this is a "Thank You" slide for special styling
  const isThankYou = slide.title && (
    slide.title.toLowerCase().includes("thank you") ||
    slide.title.toLowerCase().includes("thank-you") ||
    slide.title.toLowerCase().includes("thanks")
  );

  // Left teal accent stripe
  s.addShape("rect", { x:0, y:0, w:0.12, h:H, fill:{color:C.teal}, line:{color:C.teal} });

  // Decorative glowing circles (right side) - pushed further right to avoid overlap
  if (isThankYou) {
    // Extra decorative elements for Thank You slide
    s.addShape("ellipse", { x:7.2, y:-1.0, w:5.0, h:5.0, fill:{color:C.teal, transparency:88}, line:{color:C.teal, transparency:70, width:2} });
    s.addShape("ellipse", { x:7.8, y:-0.2, w:3.5, h:3.5, fill:{color:C.teal, transparency:91}, line:{color:C.teal, transparency:78, width:1.5} });
    s.addShape("ellipse", { x:8.3, y:0.5,  w:2.0, h:2.0, fill:{color:C.teal, transparency:85}, line:{color:C.teal, transparency:75, width:1} });
  } else {
    s.addShape("ellipse", { x:7.5, y:-0.8, w:4.5, h:4.5, fill:{color:C.teal, transparency:90}, line:{color:C.teal, transparency:75, width:1.5} });
    s.addShape("ellipse", { x:8.0, y:0.0,  w:3.0, h:3.0, fill:{color:C.teal, transparency:93}, line:{color:C.teal, transparency:82, width:1} });
  }

  // Icon (top-right) - larger for Thank You slide
  if (iconName) {
    const iconSize = isThankYou ? 1.5 : 1.2;
    const iconX = isThankYou ? 8.3 : 8.5;
    const iconY = isThankYou ? 0.4 : 0.5;
    const ic = await iconToBase64(iconName, "#" + C.teal, 512);
    if (ic) s.addImage({ data:ic, x:iconX, y:iconY, w:iconSize, h:iconSize });
  }

  // Main title - centered and larger for Thank You slide
  const titleText = slide.title || "Presentation";
  const titleWordCount = titleText.split(/\s+/).length;
  
  if (isThankYou) {
    // Thank You slide: centered, extra large, with glow effect
    s.addText(titleText, {
      x:1.5, y:2.0, w:7.0, h:1.5,
      fontSize:48, bold:true, color:"FFFFFF",
      fontFace:C.fontHeader, charSpacing:4,
      align:"center", valign:"middle", margin:0,
    });
  } else {
    // Regular title slide
    const fontSize = titleWordCount > 10 ? 28 : 32;
    s.addText(titleText, {
      x:0.45, y:1.0, w:6.8, h:1.8,
      fontSize, bold:true, color:"FFFFFF",
      fontFace:C.fontHeader, charSpacing:titleWordCount > 10 ? 1 : 3,
      margin:0, valign:"top",
    });
  }

  // Subtitle - centered for Thank You slide
  if (subtitle) {
    if (isThankYou) {
      s.addText(subtitle, {
        x:1.5, y:3.6, w:7.0, h:0.6,
        fontSize:20, color:C.teal, fontFace:C.fontBody, 
        align:"center", valign:"middle", margin:0,
      });
    } else {
      s.addText(subtitle, {
        x:0.45, y:2.9, w:6.8, h:0.5,
        fontSize:16, color:C.teal, fontFace:C.fontBody, italic:true, margin:0,
      });
    }
  }

  // Thin divider - only for non-Thank You slides
  if (!isThankYou) {
    s.addShape("rect", { x:0.45, y:3.5, w:3.8, h:0.04, fill:{color:C.teal}, line:{color:C.teal} });
  }

  // KPI badge cards (up to 4 bullets) - adjusted position
  const kpis = bullets.slice(0, 4);
  if (kpis.length > 0 && !isThankYou) {
    kpis.forEach((kpi, i) => {
      const bx = 0.45 + i * 2.35;
      s.addShape("rect", {
        x:bx, y:3.8, w:2.15, h:1.5,
        fill:{color:C.cardBg}, line:{color:C.teal, width:1},
        shadow:mkShadow(),
      });
      s.addText(kpi, {
        x:bx, y:3.85, w:2.15, h:1.4,
        fontSize:11, color:"FFFFFF", align:"center", valign:"middle",
        fontFace:C.fontBody, margin:6,
      });
    });
  } else if (subtitle && !isThankYou) {
    s.addText(subtitle, {
      x:0.45, y:3.7, w:6.8, h:0.4,
      fontSize:12, color:C.slateL, fontFace:C.fontBody, margin:0,
    });
  }

  // Bottom accent strip
  s.addShape("rect", { x:0, y:H-0.07, w:W, h:0.07, fill:{color:C.teal}, line:{color:C.teal} });

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── CONTENT SLIDE ────────────────────────────────────────────────────────────
async function buildContent(s, slide, C, isDark) {
  const content   = slide.content || {};
  const bullets   = content.bullets || [];
  const iconName  = content.icon_name || null;
  const highlight = content.highlight_text || null;
  const textColor = isDark ? "FFFFFF" : C.navy;

  addSectionHeader(s, null, C);

  // Title in header
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  // Icon circle (top-right of content area)
  let iconW = 0;
  if (iconName) {
    const ic = await iconToBase64(iconName, "#" + C.teal, 256);
    if (ic) {
      s.addShape("ellipse", {
        x:W-1.55, y:0.92, w:1.15, h:1.15,
        fill:{color:C.navy, transparency:10}, line:{color:C.teal, width:1.5},
        shadow:mkShadowSm(),
      });
      s.addImage({ data:ic, x:W-1.42, y:1.05, w:0.88, h:0.88 });
      iconW = 1.65;
    }
  }

  // Numbered bullet cards
  const contentW = W - 0.8 - iconW;
  const hasHighlight = !!highlight;
  const maxBullets = hasHighlight ? 4 : 5;

  bullets.slice(0, maxBullets).forEach((bullet, i) => {
    const by = 0.97 + i * 0.88;
    if (by + 0.78 > H - (hasHighlight ? 0.95 : 0.15)) return;

    const cardBg = isDark ? C.cardBg : "FFFFFF";
    const cardBorder = isDark ? C.teal : "E2E8F0";

    s.addShape("rect", {
      x:0.4, y:by, w:contentW, h:0.78,
      fill:{color:cardBg}, line:{color:cardBorder, width:0.5},
      shadow:mkShadowSm(),
    });
    // Number badge (primary color block)
    s.addShape("rect", { x:0.4, y:by, w:0.52, h:0.78, fill:{color:C.navy}, line:{color:C.navy} });
    s.addText(String(i + 1), {
      x:0.4, y:by, w:0.52, h:0.78,
      fontSize:13, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
    });
    s.addText(bullet, {
      x:1.0, y:by+0.08, w:contentW-0.68, h:0.62,
      fontSize:11.5, color:textColor, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // Highlight callout bar at bottom
  if (highlight) {
    s.addShape("rect", {
      x:0.4, y:H-0.82, w:W-0.8, h:0.68,
      fill:{color:C.teal}, line:{color:C.teal},
      shadow:mkShadow(),
    });
    s.addText("▶  " + highlight, {
      x:0.4, y:H-0.82, w:W-0.8, h:0.68,
      fontSize:11, bold:true, color:C.dark,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:6,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── CHART SLIDE ──────────────────────────────────────────────────────────────
async function buildChart(s, slide, C, pres) {
  const content   = slide.content || {};
  const chartType = (content.chart_type || "bar").toLowerCase();
  const chartData = content.chart_data || [];
  const highlight = content.highlight_text || null;
  const bullets   = content.bullets || [];

  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  // Layout: left 38% = insight bullets, right 60% = chart
  const leftW  = W * 0.37;
  const chartX = leftW + 0.6;
  const chartY = 0.92;
  const chartW = W - chartX - 0.25;
  const chartH = H - chartY - (highlight ? 0.95 : 0.3);

  // ── Chart ──
  if (chartData.length > 0) {
    const labels = chartData.map(d => String(d.label || d.name || ""));
    const values = chartData.map(d => Number(d.value || d.y || 0));

    let pptxType, chartOpts;

    if (chartType === "pie" || chartType === "donut") {
      pptxType = pres.charts.PIE;
      chartOpts = {
        x:chartX, y:chartY, w:chartW, h:chartH,
        chartColors: C.chartColors,
        chartArea: { fill:{color:C.bg}, roundedCorners:false },
        showLegend:true, legendPos:"b",
        showPercent:true,
        dataLabelColor:C.navy, dataLabelFontSize:10,
      };
    } else if (chartType === "line" || chartType === "line_smooth") {
      pptxType = pres.charts.LINE;
      chartOpts = {
        x:chartX, y:chartY, w:chartW, h:chartH,
        chartColors: C.chartColors,
        chartArea: { fill:{color:C.bg}, roundedCorners:false },
        catAxisLabelColor:C.slate, valAxisLabelColor:C.slate,
        valGridLine:{color:"E2E8F0", size:0.5}, catGridLine:{style:"none"},
        lineSize:2.5, lineSmooth:true,
        showValue:false, showLegend:false,
      };
    } else if (chartType === "area" || chartType === "stacked_area") {
      pptxType = pres.charts.AREA;
      chartOpts = {
        x:chartX, y:chartY, w:chartW, h:chartH,
        chartColors: C.chartColors,
        chartArea: { fill:{color:C.bg}, roundedCorners:false },
        catAxisLabelColor:C.slate, valAxisLabelColor:C.slate,
        valGridLine:{color:"E2E8F0", size:0.5}, catGridLine:{style:"none"},
        showValue:false, showLegend:false,
      };
    } else if (chartType === "stacked_bar") {
      pptxType = pres.charts.BAR;
      chartOpts = {
        x:chartX, y:chartY, w:chartW, h:chartH,
        barDir:"col", barGrouping:"stacked",
        chartColors: C.chartColors,
        chartArea: { fill:{color:C.bg}, roundedCorners:false },
        catAxisLabelColor:C.slate, valAxisLabelColor:C.slate,
        valGridLine:{color:"E2E8F0", size:0.5}, catGridLine:{style:"none"},
        showValue:false, showLegend:true, legendPos:"b",
      };
    } else {
      // Default: clustered column
      pptxType = pres.charts.BAR;
      chartOpts = {
        x:chartX, y:chartY, w:chartW, h:chartH,
        barDir:"col", barGapWidthPct:45,
        chartColors: C.chartColors,
        chartArea: { fill:{color:C.bg}, roundedCorners:false },
        catAxisLabelColor:C.slate, valAxisLabelColor:C.slate,
        valGridLine:{color:"E2E8F0", size:0.5}, catGridLine:{style:"none"},
        showValue:true, dataLabelPosition:"outEnd",
        dataLabelColor:C.navy, dataLabelFontSize:9,
        showLegend:false,
      };
    }

    s.addChart(pptxType, [{ name: slide.title || "Data", labels, values }], chartOpts);
  }

  // ── Left insight bullets with accent left border ──
  if (bullets.length > 0) {
    bullets.slice(0, 5).forEach((b, i) => {
      const by = 0.97 + i * 0.82;
      if (by + 0.72 > H - (highlight ? 1.05 : 0.25)) return;
      s.addShape("rect", {
        x:0.3, y:by, w:leftW, h:0.72,
        fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:0.5},
        shadow:mkShadowSm(),
      });
      s.addShape("rect", { x:0.3, y:by, w:0.07, h:0.72, fill:{color:C.teal}, line:{color:C.teal} });
      s.addText(b, {
        x:0.44, y:by+0.07, w:leftW-0.22, h:0.58,
        fontSize:10, color:C.navy, fontFace:C.fontBody, valign:"middle", margin:0,
      });
    });
  }

  // ── Insight callout ──
  if (highlight) {
    s.addShape("rect", {
      x:0.3, y:H-0.82, w:leftW, h:0.68,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadow(),
    });
    s.addText(highlight, {
      x:0.3, y:H-0.82, w:leftW, h:0.68,
      fontSize:9.5, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:5,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── TABLE SLIDE ──────────────────────────────────────────────────────────────
async function buildTable(s, slide, C) {
  const content   = slide.content || {};
  const tableData = content.table_data || {};
  const headers   = tableData.headers || [];
  const rows      = tableData.rows    || [];
  const highlight = content.highlight_text || null;
  const bullets   = content.bullets || [];

  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  if (headers.length > 0 && rows.length > 0) {
    const hasBullets = bullets.length > 0;
    const tableW = hasBullets ? W * 0.62 : W - 0.8;
    const tableY = 0.92;
    const tableH = H - tableY - (highlight ? 0.95 : 0.3);
    const colW   = tableW / headers.length;

    const headerRow = headers.map(h => ({
      text: String(h),
      options: {
        fill:{color:C.navy}, color:"FFFFFF", bold:true,
        fontSize:11, fontFace:C.fontBody,
        align:"center", valign:"middle",
        border:{pt:0},
      },
    }));

    const dataRows = rows.map((row, ri) =>
      (Array.isArray(row) ? row : [row]).map(cell => ({
        text: String(cell ?? ""),
        options: {
          fill:{color: ri % 2 === 0 ? "F8F9FA" : "FFFFFF"},
          color:C.navy, fontSize:10, fontFace:C.fontBody,
          align:"center", valign:"middle",
          border:{pt:0.5, color:"E2E8F0"},
        },
      }))
    );

    s.addTable([headerRow, ...dataRows], {
      x:0.4, y:tableY, w:tableW, h:tableH,
      colW: Array(headers.length).fill(colW),
    });

    // Right panel: insight bullets
    if (hasBullets) {
      const rx = 0.4 + tableW + 0.3;
      const rw = W - rx - 0.25;
      bullets.slice(0, 5).forEach((b, i) => {
        const by = tableY + i * 0.82;
        if (by + 0.72 > H - (highlight ? 1.0 : 0.25)) return;
        s.addShape("rect", {
          x:rx, y:by, w:rw, h:0.72,
          fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:0.5},
          shadow:mkShadowSm(),
        });
        s.addShape("rect", { x:rx, y:by, w:0.07, h:0.72, fill:{color:C.teal}, line:{color:C.teal} });
        s.addText(b, {
          x:rx+0.14, y:by+0.07, w:rw-0.22, h:0.58,
          fontSize:10, color:C.navy, fontFace:C.fontBody, valign:"middle", margin:0,
        });
      });
    }
  }

  if (highlight) {
    s.addShape("rect", {
      x:0.4, y:H-0.82, w:W-0.8, h:0.68,
      fill:{color:C.teal}, line:{color:C.teal},
      shadow:mkShadow(),
    });
    s.addText("▶  " + highlight, {
      x:0.4, y:H-0.82, w:W-0.8, h:0.68,
      fontSize:11, bold:true, color:C.dark,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:6,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── COMPARISON SLIDE ─────────────────────────────────────────────────────────
async function buildComparison(s, slide, C) {
  const content = slide.content || {};
  const comp    = content.comparison_data || {};
  const highlight = content.highlight_text || null;

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

  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  const colW = (W - 1.0) / 2;
  const colY = 0.92;
  const colH = H - colY - (highlight ? 0.95 : 0.3);

  // ── Left column ──
  s.addShape("rect", {
    x:0.3, y:colY, w:colW, h:colH,
    fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:1},
    shadow:mkShadow(),
  });
  s.addShape("rect", { x:0.3, y:colY, w:colW, h:0.55, fill:{color:C.navy}, line:{color:C.navy} });
  s.addText(leftH, {
    x:0.3, y:colY, w:colW, h:0.55,
    fontSize:14, bold:true, color:"FFFFFF",
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  leftItems.slice(0, 6).forEach((item, i) => {
    const iy = colY + 0.62 + i * 0.68;
    if (iy + 0.6 > H - (highlight ? 1.0 : 0.25)) return;
    s.addShape("rect", {
      x:0.35, y:iy, w:colW-0.1, h:0.6,
      fill:{color:"F8FAFC"}, line:{color:"E2E8F0", width:0.5},
    });
    s.addText([
      { text:"›  ", options:{color:C.navy, bold:true} },
      { text:String(item), options:{color:C.navy} },
    ], {
      x:0.42, y:iy+0.05, w:colW-0.24, h:0.5,
      fontSize:10.5, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // ── Right column ──
  const rx = 0.3 + colW + 0.4;
  s.addShape("rect", {
    x:rx, y:colY, w:colW, h:colH,
    fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:1},
    shadow:mkShadow(),
  });
  s.addShape("rect", { x:rx, y:colY, w:colW, h:0.55, fill:{color:C.teal}, line:{color:C.teal} });
  s.addText(rightH, {
    x:rx, y:colY, w:colW, h:0.55,
    fontSize:14, bold:true, color:C.dark,
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  rightItems.slice(0, 6).forEach((item, i) => {
    const iy = colY + 0.62 + i * 0.68;
    if (iy + 0.6 > H - (highlight ? 1.0 : 0.25)) return;
    s.addShape("rect", {
      x:rx+0.05, y:iy, w:colW-0.1, h:0.6,
      fill:{color:"F8FAFC"}, line:{color:"E2E8F0", width:0.5},
    });
    s.addText([
      { text:"›  ", options:{color:C.teal, bold:true} },
      { text:String(item), options:{color:C.navy} },
    ], {
      x:rx+0.12, y:iy+0.05, w:colW-0.24, h:0.5,
      fontSize:10.5, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // Vertical divider
  s.addShape("rect", {
    x:0.3 + colW + 0.18, y:colY, w:0.04, h:colH,
    fill:{color:"CBD5E1"}, line:{color:"CBD5E1"},
  });

  if (highlight) {
    s.addShape("rect", {
      x:0.3, y:H-0.82, w:W-0.6, h:0.68,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadow(),
    });
    s.addText(highlight, {
      x:0.3, y:H-0.82, w:W-0.6, h:0.68,
      fontSize:10, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:5,
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
    fill:{color:C.navy}, line:{color:C.teal, width:1.5},
    shadow:mkShadow(),
  });

  // Icon
  if (iconName) {
    const ic = await iconToBase64(iconName, "#" + C.teal, 256);
    if (ic) s.addImage({ data:ic, x:0.3+cardW/2-0.4, y:1.05, w:0.8, h:0.8 });
  }

  // Big number
  s.addText(val, {
    x:0.3, y:1.95, w:cardW, h:1.4,
    fontSize:56, bold:true, color:"FFFFFF",
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
    const trendColor = trend.includes("+") || trend.includes("▲") || trend.toLowerCase().includes("up")
      ? "22C55E"
      : trend.includes("-") || trend.includes("▼") || trend.toLowerCase().includes("down")
      ? "EF4444"
      : C.gold;
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
    if (by + 0.95 > H - 0.15) return;
    s.addShape("rect", {
      x:rx, y:by, w:rw, h:0.95,
      fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:0.5},
      shadow:mkShadowSm(),
    });
    s.addShape("rect", { x:rx, y:by, w:0.5, h:0.95, fill:{color:C.navy}, line:{color:C.navy} });
    s.addText(String(i + 1), {
      x:rx, y:by, w:0.5, h:0.95,
      fontSize:14, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
    });
    s.addText(b, {
      x:rx+0.58, y:by+0.08, w:rw-0.68, h:0.79,
      fontSize:11, color:C.navy, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

module.exports = { buildPptx };
