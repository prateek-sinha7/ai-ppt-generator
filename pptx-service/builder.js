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
// Built-in palettes — dark, rich, enterprise-grade
const THEMES = {
    ocean_depths: {
      navy:    "1A2332", teal:    "2D8B8B", tealDk:  "1F6B6B",
      blue:    "2D8B8B", blueLt:  "5BA3A3", white:   "FFFFFF",
      offwhite:"F1FAEE", slate:   "6B7280", slateL:  "94A3B8",
      dark:    "0D1520", gold:    "A8DADC", green:   "2D8B8B",
      red:     "EF4444", cardBg:  "0D1520", cardBg2: "142030",
      accent:  "A8DADC", primary: "1A2332", secondary:"2D8B8B",
      text:    "1A2332", textLight:"6B7280", bg:"F1FAEE", bgDark:"0D1520",
      chartColors:["1A2332","2D8B8B","A8DADC","5BA3A3","3D6B6B","82C0C0","6B7280"],
      fontHeader:"Georgia", fontBody:"Calibri",
    },
    sunset_boulevard: {
      navy:    "264653", teal:    "E76F51", tealDk:  "C45A3E",
      blue:    "F4A261", blueLt:  "F7BC82", white:   "FFFFFF",
      offwhite:"FDF8F3", slate:   "6B7280", slateL:  "94A3B8",
      dark:    "1A2F3A", gold:    "E9C46A", green:   "2A9D8F",
      red:     "E76F51", cardBg:  "1A2F3A", cardBg2: "223A48",
      accent:  "E9C46A", primary: "264653", secondary:"E76F51",
      text:    "264653", textLight:"6B7280", bg:"FFFFFF", bgDark:"1A2F3A",
      chartColors:["E76F51","F4A261","E9C46A","264653","2A9D8F","B45A41","6B7280"],
      fontHeader:"Georgia", fontBody:"Calibri",
    },
    forest_canopy: {
      navy:    "2D4A2B", teal:    "A4AC86", tealDk:  "7D8471",
      blue:    "7D8471", blueLt:  "8B9B78", white:   "FFFFFF",
      offwhite:"FAF9F6", slate:   "6B7280", slateL:  "94A3B8",
      dark:    "1A2D1A", gold:    "A4AC86", green:   "5A7A58",
      red:     "8B6B4A", cardBg:  "1A2D1A", cardBg2: "223822",
      accent:  "A4AC86", primary: "2D4A2B", secondary:"7D8471",
      text:    "2D4A2B", textLight:"6B7280", bg:"FAF9F6", bgDark:"1A2D1A",
      chartColors:["2D4A2B","7D8471","A4AC86","5A7A58","8B9B78","4A6A48","6B7280"],
      fontHeader:"Cambria", fontBody:"Calibri",
    },
    modern_minimalist: {
      navy:    "36454F", teal:    "708090", tealDk:  "505A64",
      blue:    "708090", blueLt:  "8896A0", white:   "FFFFFF",
      offwhite:"F5F5F5", slate:   "708090", slateL:  "A0A0A0",
      dark:    "1A2028", gold:    "D3D3D3", green:   "708090",
      red:     "808080", cardBg:  "1A2028", cardBg2: "222A32",
      accent:  "D3D3D3", primary: "36454F", secondary:"708090",
      text:    "36454F", textLight:"708090", bg:"FFFFFF", bgDark:"1A2028",
      chartColors:["36454F","708090","A0A0A0","505A64","8896A0","283840","B0B0B0"],
      fontHeader:"Calibri", fontBody:"Calibri Light",
    },
    golden_hour: {
      navy:    "4A403A", teal:    "F4A900", tealDk:  "C48800",
      blue:    "C1666B", blueLt:  "D4888C", white:   "FFFFFF",
      offwhite:"FAF6F0", slate:   "6B7280", slateL:  "94A3B8",
      dark:    "2A2420", gold:    "F4A900", green:   "D4B896",
      red:     "C1666B", cardBg:  "2A2420", cardBg2: "342E28",
      accent:  "D4B896", primary: "4A403A", secondary:"C1666B",
      text:    "4A403A", textLight:"6B7280", bg:"FFFFFF", bgDark:"2A2420",
      chartColors:["F4A900","C1666B","D4B896","8B6914","A0524E","B89060","6B7280"],
      fontHeader:"Georgia", fontBody:"Calibri",
    },
    arctic_frost: {
      navy:    "2C3E50", teal:    "4A6FA5", tealDk:  "3D5A80",
      blue:    "4A6FA5", blueLt:  "7A9CC6", white:   "FFFFFF",
      offwhite:"FAFAFA", slate:   "6B7280", slateL:  "94A3B8",
      dark:    "2A3A50", gold:    "D4E4F7", green:   "5580A8",
      red:     "C0C0C0", cardBg:  "2A3A50", cardBg2: "324460",
      accent:  "D4E4F7", primary: "4A6FA5", secondary:"C0C0C0",
      text:    "2C3E50", textLight:"6B7280", bg:"FAFAFA", bgDark:"2A3A50",
      chartColors:["4A6FA5","7A9CC6","A8C4E0","5580A8","3D5A80","6490B8","6B7280"],
      fontHeader:"Calibri", fontBody:"Calibri Light",
    },
    desert_rose: {
      navy:    "5D2E46", teal:    "D4A5A5", tealDk:  "B87D6D",
      blue:    "B87D6D", blueLt:  "C89898", white:   "FFFFFF",
      offwhite:"FAF5F0", slate:   "6B7280", slateL:  "94A3B8",
      dark:    "3A1A2A", gold:    "E8D5C4", green:   "9B6B6B",
      red:     "B87D6D", cardBg:  "3A1A2A", cardBg2: "482234",
      accent:  "E8D5C4", primary: "5D2E46", secondary:"B87D6D",
      text:    "5D2E46", textLight:"6B7280", bg:"FFFFFF", bgDark:"3A1A2A",
      chartColors:["D4A5A5","B87D6D","E8D5C4","5D2E46","9B6B6B","AA8C8C","6B7280"],
      fontHeader:"Georgia", fontBody:"Calibri",
    },
    tech_innovation: {
      navy:    "1E1E1E", teal:    "0066FF", tealDk:  "0050CC",
      blue:    "0066FF", blueLt:  "3388FF", white:   "FFFFFF",
      offwhite:"2A2A2A", slate:   "9CA3AF", slateL:  "B0B8C4",
      dark:    "0A0A0A", gold:    "00FFFF", green:   "00CCCC",
      red:     "FF4444", cardBg:  "0A0A0A", cardBg2: "141414",
      accent:  "00FFFF", primary: "1E1E1E", secondary:"0066FF",
      text:    "FFFFFF", textLight:"9CA3AF", bg:"1E1E1E", bgDark:"0A0A0A",
      chartColors:["0066FF","00FFFF","00CCCC","3388FF","66DDFF","00AAAA","9CA3AF"],
      fontHeader:"Calibri", fontBody:"Calibri Light",
    },
    botanical_garden: {
      navy:    "2A3A2A", teal:    "4A7C59", tealDk:  "3A6248",
      blue:    "F9A620", blueLt:  "FABC50", white:   "FFFFFF",
      offwhite:"F5F3ED", slate:   "6B7280", slateL:  "94A3B8",
      dark:    "2A3A2A", gold:    "F9A620", green:   "4A7C59",
      red:     "B7472A", cardBg:  "2A3A2A", cardBg2: "324432",
      accent:  "F9A620", primary: "4A7C59", secondary:"B7472A",
      text:    "3A3A3A", textLight:"6B7280", bg:"F5F3ED", bgDark:"2A3A2A",
      chartColors:["4A7C59","F9A620","B7472A","6B9B78","D4881A","5A9068","6B7280"],
      fontHeader:"Cambria", fontBody:"Calibri",
    },
    midnight_galaxy: {
      navy:    "2B1E3E", teal:    "A490C2", tealDk:  "7A6AA0",
      blue:    "4A4E8F", blueLt:  "6B6FAF", white:   "FFFFFF",
      offwhite:"362A4E", slate:   "9CA3AF", slateL:  "B0B8C4",
      dark:    "1A1028", gold:    "E6E6FA", green:   "A490C2",
      red:     "C47090", cardBg:  "1A1028", cardBg2: "221838",
      accent:  "E6E6FA", primary: "2B1E3E", secondary:"4A4E8F",
      text:    "E6E6FA", textLight:"9CA3AF", bg:"2B1E3E", bgDark:"1A1028",
      chartColors:["4A4E8F","A490C2","E6E6FA","6B6FAF","C4B8D8","5A5EA0","9CA3AF"],
      fontHeader:"Calibri", fontBody:"Calibri Light",
    },
  };

function resolveDesign(designSpec, theme) {
  const base = THEMES[theme] || THEMES["ocean_depths"];
  if (!designSpec || !designSpec.primary_color) return base;

  const h = (v, fb) => {
    if (!v) return fb;
    const s = String(v).replace("#", "");
    return /^[0-9A-Fa-f]{6}$/.test(s) ? s.toUpperCase() : fb;
  };

  // Let the LLM's designSpec override ALL color fields — not just a subset.
  // The base theme provides structural defaults; designSpec refines everything.
  const text      = h(designSpec.text_color,            base.text);
  const textLight = h(designSpec.text_light_color,      base.textLight);
  const bg        = h(designSpec.background_color,      base.bg);
  const bgDark    = h(designSpec.background_dark_color, base.bgDark);
  const primary   = h(designSpec.primary_color,         base.primary);
  const secondary = h(designSpec.secondary_color,       base.secondary);
  const accent    = h(designSpec.accent_color,          base.accent);

  return {
    ...base,
    primary,
    secondary,
    accent,
    teal:       accent,
    tealDk:     h(designSpec.secondary_color, base.tealDk),
    navy:       primary,
    dark:       bgDark,
    bgDark,
    bg,
    text,
    textLight,
    slate:      textLight,
    slateL:     textLight,
    cardBg:     bgDark,
    cardBg2:    bgDark,
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

    // Always use light background — LLM controls colors via designSpec
    pSlide.background = { color: C.bg };

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
    // Thank You slide: centered, extra large
    s.addText(titleText, {
      x:1.5, y:2.0, w:7.0, h:1.5,
      fontSize:48, bold:true, color:C.navy,
      fontFace:C.fontHeader, charSpacing:4,
      align:"center", valign:"middle", margin:0,
    });
  } else {
    // Regular title slide — dynamic height to prevent subtitle overlap
    const titleCharCount = titleText.length;
    let fontSize, charsPerLine, lineHeight;
    if (titleWordCount > 12) {
      fontSize = 24; charsPerLine = 55; lineHeight = 0.55;
    } else if (titleWordCount > 10) {
      fontSize = 28; charsPerLine = 48; lineHeight = 0.62;
    } else {
      fontSize = 32; charsPerLine = 42; lineHeight = 0.70;
    }

    const estimatedLines = Math.ceil(titleCharCount / charsPerLine);
    const estimatedTextHeight = estimatedLines * lineHeight;
    // Add padding and ensure minimum height
    const titleHeight = Math.max(estimatedTextHeight + 0.3, 1.4);
    const titleY = 1.0;

    s.addText(titleText, {
      x:0.45, y:titleY, w:6.8, h:titleHeight,
      fontSize, bold:true, color:C.navy,
      fontFace:C.fontHeader, charSpacing:titleWordCount > 10 ? 1 : 3,
      margin:0, valign:"top",
    });

    // Subtitle always starts AFTER the title box ends + safe margin
    var subtitleY = titleY + titleHeight + 0.2;
    // Clamp so subtitle never goes below 3.0 (leaves room for KPI cards)
    subtitleY = Math.min(subtitleY, 3.0);
  }

  // Subtitle - centered for Thank You slide, positioned below title for regular slides
  if (subtitle) {
    if (isThankYou) {
      s.addText(subtitle, {
        x:1.5, y:3.6, w:7.0, h:0.6,
        fontSize:20, color:C.teal, fontFace:C.fontBody, 
        align:"center", valign:"middle", margin:0,
      });
    } else {
      // Position subtitle below title with proper spacing
      s.addText(subtitle, {
        x:0.45, y:subtitleY, w:6.8, h:0.5,
        fontSize:16, color:C.teal, fontFace:C.fontBody, italic:true, margin:0,
      });
    }
  }

  // Thin divider - only for non-Thank You slides, positioned below subtitle
  if (!isThankYou && subtitle) {
    const dividerY = subtitleY + 0.58; // Below subtitle
    if (dividerY < 3.6) {
      s.addShape("rect", { x:0.45, y:dividerY, w:3.8, h:0.04, fill:{color:C.teal}, line:{color:C.teal} });
    }
  } else if (!isThankYou) {
    // No subtitle, use default position
    s.addShape("rect", { x:0.45, y:3.5, w:3.8, h:0.04, fill:{color:C.teal}, line:{color:C.teal} });
  }

  // KPI badge cards — position below divider, always at least 0.2" below subtitle
  const kpiY = subtitle ? Math.max(subtitleY + 0.75, 3.7) : 3.8;
  const kpiH = H - kpiY - 0.1;
  const kpis = bullets.slice(0, 4);
  if (kpis.length > 0 && !isThankYou && kpiH > 0.5) {
    kpis.forEach((kpi, i) => {
      const bx = 0.45 + i * 2.35;
      s.addShape("rect", {
        x:bx, y:kpiY, w:2.15, h:kpiH,
        fill:{color:C.cardBg}, line:{color:C.teal, width:1},
        shadow:mkShadow(),
      });
      s.addText(kpi, {
        x:bx, y:kpiY + 0.05, w:2.15, h:kpiH - 0.1,
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

// ─── CONTENT SLIDE VARIANTS ───────────────────────────────────────────────────

// Helper: extract bullet text from string or object
function bulletText(bullet) {
  return typeof bullet === 'string' ? bullet : (bullet?.text || String(bullet));
}

// icon-grid: 2×2 grid with colored icon circles + bold title + description
async function buildContentIconGrid(s, slide, C, isDark) {
  const content = slide.content || {};
  const bullets = content.bullets || [];
  const textColor = C.text;
  const items = bullets.slice(0, 4);
  const cols = 2;
  const cellW = (W - 1.0) / cols;
  const cellH = (H - 0.92 - 0.3) / 2;

  for (let i = 0; i < items.length; i++) {
    const bullet = items[i];
    const col = i % cols;
    const row = Math.floor(i / cols);
    const cx = 0.4 + col * (cellW + 0.2);
    const cy = 0.97 + row * (cellH + 0.1);

    // Support rich item format: { icon, title, description } or plain string
    let title, desc, iconName;
    if (typeof bullet === 'object' && bullet.title) {
      title = bullet.title;
      desc = bullet.description || "";
      iconName = bullet.icon || null;
    } else {
      const text = bulletText(bullet);
      const sepIdx = text.search(/[:\u2013\u2014–—-]\s/);
      if (sepIdx > 0) {
        title = text.substring(0, sepIdx).trim();
        desc = text.substring(sepIdx + 1).replace(/^\s+/, "");
      } else {
        title = text;
        desc = "";
      }
      iconName = null;
    }

    // Icon circle — use per-item icon if available, otherwise numbered
    if (iconName) {
      const ic = await iconToBase64(iconName, "#" + C.teal, 256);
      if (ic) {
        s.addShape("ellipse", {
          x:cx + 0.1, y:cy, w:0.65, h:0.65,
          fill:{color:C.navy, transparency:90}, line:{color:C.teal, width:1.5},
          shadow:mkShadowSm(),
        });
        s.addImage({ data:ic, x:cx + 0.18, y:cy + 0.08, w:0.49, h:0.49 });
      } else {
        // Fallback to numbered circle
        s.addShape("ellipse", {
          x:cx + 0.1, y:cy, w:0.65, h:0.65,
          fill:{color:C.teal, transparency:15}, line:{color:C.teal, width:1.5},
          shadow:mkShadowSm(),
        });
        s.addText(String(i + 1), {
          x:cx + 0.1, y:cy, w:0.65, h:0.65,
          fontSize:18, bold:true, color:C.dark,
          align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
        });
      }
    } else {
      // Numbered circle (default)
      s.addShape("ellipse", {
        x:cx + 0.1, y:cy, w:0.65, h:0.65,
        fill:{color:C.teal, transparency:15}, line:{color:C.teal, width:1.5},
        shadow:mkShadowSm(),
      });
      s.addText(String(i + 1), {
        x:cx + 0.1, y:cy, w:0.65, h:0.65,
        fontSize:18, bold:true, color:C.dark,
        align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
      });
    }

    // Bold title
    s.addText(title, {
      x:cx + 0.85, y:cy, w:cellW - 1.0, h:0.35,
      fontSize:12, bold:true, color:textColor,
      fontFace:C.fontHeader, valign:"middle", margin:0,
    });

    // Description
    if (desc) {
      s.addText(desc, {
        x:cx + 0.85, y:cy + 0.35, w:cellW - 1.0, h:cellH - 0.45,
        fontSize:10, color:C.slate,
        fontFace:C.fontBody, valign:"top", margin:0,
      });
    }
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// two-column-text: split bullets into two equal columns with vertical divider
function buildContentTwoColumn(s, slide, C, isDark) {
  const content = slide.content || {};
  const bullets = content.bullets || [];
  const textColor = C.text;
  const colW = (W - 1.2) / 2;
  const mid = Math.ceil(bullets.length / 2);
  const leftBullets = bullets.slice(0, mid);
  const rightBullets = bullets.slice(mid);

  // Left column bullets
  leftBullets.slice(0, 5).forEach((bullet, i) => {
    const by = 0.97 + i * 0.82;
    if (by + 0.72 > H - 0.25) return;
    const cardBg = "FFFFFF";
    s.addShape("rect", {
      x:0.3, y:by, w:colW, h:0.72,
      fill:{color:cardBg}, line:{color:"E2E8F0", width:0.5},
      shadow:mkShadowSm(),
    });
    s.addShape("rect", { x:0.3, y:by, w:0.07, h:0.72, fill:{color:C.teal}, line:{color:C.teal} });
    s.addText(bulletText(bullet), {
      x:0.44, y:by + 0.07, w:colW - 0.22, h:0.58,
      fontSize:10.5, color:textColor, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // Vertical divider
  const divX = 0.3 + colW + 0.12;
  s.addShape("rect", {
    x:divX, y:0.97, w:0.04, h:H - 0.97 - 0.3,
    fill:{color:"CBD5E1"}, line:{color:"CBD5E1"},
  });

  // Right column bullets
  const rx = divX + 0.28;
  rightBullets.slice(0, 5).forEach((bullet, i) => {
    const by = 0.97 + i * 0.82;
    if (by + 0.72 > H - 0.25) return;
    const cardBg = "FFFFFF";
    s.addShape("rect", {
      x:rx, y:by, w:colW, h:0.72,
      fill:{color:cardBg}, line:{color:"E2E8F0", width:0.5},
      shadow:mkShadowSm(),
    });
    s.addShape("rect", { x:rx, y:by, w:0.07, h:0.72, fill:{color:C.teal}, line:{color:C.teal} });
    s.addText(bulletText(bullet), {
      x:rx + 0.14, y:by + 0.07, w:colW - 0.22, h:0.58,
      fontSize:10.5, color:textColor, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// stat-callouts: up to 4 large numbers with small labels, arranged horizontally
function buildContentStatCallouts(s, slide, C, isDark) {
  const content = slide.content || {};
  const bullets = content.bullets || [];
  const items = bullets.slice(0, 4);
  const count = items.length || 1;
  const cardW = (W - 0.8 - (count - 1) * 0.2) / count;
  const cardY = 1.2;
  const cardH = H - cardY - 0.4;

  items.forEach((bullet, i) => {
    const text = bulletText(bullet);
    const cx = 0.4 + i * (cardW + 0.2);

    // Extract number and label — look for a leading number/percentage/currency
    let num = "", label = text;
    const numMatch = text.match(/^([\$€£¥]?\s*[\d,.]+[%+\-×xKMBT]*)/);
    if (numMatch) {
      num = numMatch[1].trim();
      label = text.substring(numMatch[0].length).replace(/^[\s:\-–—]+/, "").trim();
    } else {
      // Try splitting on colon
      const sepIdx = text.indexOf(":");
      if (sepIdx > 0 && sepIdx < 20) {
        num = text.substring(0, sepIdx).trim();
        label = text.substring(sepIdx + 1).trim();
      }
    }

    // Card background
    const cardBg = "FFFFFF";
    s.addShape("rect", {
      x:cx, y:cardY, w:cardW, h:cardH,
      fill:{color:cardBg}, line:{color:"E2E8F0", width:1},
      shadow:mkShadow(),
    });

    // Accent top bar
    s.addShape("rect", { x:cx, y:cardY, w:cardW, h:0.06, fill:{color:C.teal}, line:{color:C.teal} });

    // Large number
    s.addText(num || "—", {
      x:cx, y:cardY + 0.2, w:cardW, h:1.2,
      fontSize:48, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
    });

    // Small label
    s.addText(label || text, {
      x:cx + 0.1, y:cardY + 1.5, w:cardW - 0.2, h:cardH - 1.7,
      fontSize:11, color:C.slate,
      align:"center", valign:"top", fontFace:C.fontBody, margin:0,
    });
  });

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// timeline: horizontal numbered steps connected by a line
function buildContentTimeline(s, slide, C, isDark) {
  const content = slide.content || {};
  const bullets = content.bullets || [];
  const textColor = C.text;
  const items = bullets.slice(0, 5);
  const count = items.length || 1;
  const stepW = (W - 1.0) / count;
  const lineY = 2.6;
  const circleR = 0.35;

  // Horizontal connecting line
  const lineX1 = 0.5 + stepW / 2;
  const lineX2 = 0.5 + stepW * (count - 1) + stepW / 2;
  if (count > 1) {
    s.addShape("rect", {
      x:lineX1, y:lineY + circleR / 2 - 0.025, w:lineX2 - lineX1, h:0.05,
      fill:{color:C.teal, transparency:30}, line:{color:C.teal, transparency:30},
    });
  }

  items.forEach((bullet, i) => {
    const text = bulletText(bullet);
    const cx = 0.5 + i * stepW + stepW / 2;

    // Split on first colon/dash for label/description
    let label = text, desc = "";
    const sepIdx = text.search(/[:\u2013\u2014–—-]\s/);
    if (sepIdx > 0) {
      label = text.substring(0, sepIdx).trim();
      desc = text.substring(sepIdx + 1).replace(/^\s+/, "");
    }

    // Step circle
    s.addShape("ellipse", {
      x:cx - circleR, y:lineY, w:circleR * 2, h:circleR * 2,
      fill:{color:C.navy}, line:{color:C.teal, width:2},
      shadow:mkShadowSm(),
    });
    s.addText(String(i + 1), {
      x:cx - circleR, y:lineY, w:circleR * 2, h:circleR * 2,
      fontSize:14, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
    });

    // Label above the line
    s.addText(label, {
      x:cx - stepW / 2 + 0.05, y:1.0, w:stepW - 0.1, h:1.4,
      fontSize:10.5, bold:true, color:textColor,
      align:"center", valign:"bottom", fontFace:C.fontHeader, margin:0,
    });

    // Description below the line
    if (desc) {
      s.addText(desc, {
        x:cx - stepW / 2 + 0.05, y:lineY + circleR * 2 + 0.15, w:stepW - 0.1, h:1.2,
        fontSize:9.5, color:C.slate,
        align:"center", valign:"top", fontFace:C.fontBody, margin:0,
      });
    }
  });

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// quote-highlight: first bullet as large centered italic quote, rest as attribution
function buildContentQuote(s, slide, C, isDark) {
  const content = slide.content || {};
  const bullets = content.bullets || [];
  const textColor = C.text;

  const quote = bullets.length > 0 ? bulletText(bullets[0]) : "";
  const attribs = bullets.slice(1);

  // Decorative quote mark
  s.addText("\u201C", {
    x:0.4, y:0.92, w:1.0, h:1.0,
    fontSize:72, color:C.teal, transparency:40,
    fontFace:C.fontHeader, valign:"top", margin:0,
  });

  // Large centered italic quote
  s.addText(quote, {
    x:1.0, y:1.4, w:W - 2.0, h:2.2,
    fontSize:24, italic:true, color:textColor,
    align:"center", valign:"middle", fontFace:C.fontBody, margin:0,
  });

  // Closing quote mark
  s.addText("\u201D", {
    x:W - 1.4, y:3.0, w:1.0, h:1.0,
    fontSize:72, color:C.teal, transparency:40,
    fontFace:C.fontHeader, valign:"top", align:"right", margin:0,
  });

  // Thin accent divider
  s.addShape("rect", {
    x:W / 2 - 1.0, y:3.8, w:2.0, h:0.04,
    fill:{color:C.teal}, line:{color:C.teal},
  });

  // Attribution text
  attribs.slice(0, 2).forEach((attr, i) => {
    s.addText(bulletText(attr), {
      x:1.0, y:3.95 + i * 0.4, w:W - 2.0, h:0.35,
      fontSize:11, color:C.slate,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:0,
    });
  });

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── CONTENT SLIDE ────────────────────────────────────────────────────────────
async function buildContent(s, slide, C, isDark) {
  const variant = slide.content?.layout_variant || slide.layout_variant || 'numbered-cards';
  const content   = slide.content || {};
  const bullets   = content.bullets || [];
  const iconName  = content.icon_name || null;
  const highlight = content.highlight_text || null;
  const textColor = C.text;

  // All variants share the section header + title
  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  switch (variant) {
    case 'icon-grid':        return buildContentIconGrid(s, slide, C, isDark);
    case 'two-column-text':  return buildContentTwoColumn(s, slide, C, isDark);
    case 'stat-callouts':    return buildContentStatCallouts(s, slide, C, isDark);
    case 'timeline':         return buildContentTimeline(s, slide, C, isDark);
    case 'quote-highlight':  return buildContentQuote(s, slide, C, isDark);
    default: break; // fall through to existing numbered-cards code
  }

  // ── Default: numbered-cards (existing behavior) ──

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

    const cardBg = "FFFFFF";
    const cardBorder = "E2E8F0";

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
    // Handle bullet as string or object with text field
    const bText = typeof bullet === 'string' ? bullet : (bullet?.text || String(bullet));
    s.addText(bText, {
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

// ─── CHART SLIDE VARIANTS ─────────────────────────────────────────────────────

// Helper: render a chart given position/size (shared by chart variants)
function addChartToSlide(s, slide, C, pres, cx, cy, cw, ch) {
  const content   = slide.content || {};
  const chartType = (content.chart_type || "bar").toLowerCase();
  const chartData = content.chart_data || [];

  if (chartData.length === 0) return;

  const labels = chartData.map(d => String(d.label || d.name || ""));
  const values = chartData.map(d => Number(d.value || d.y || 0));

  let pptxType, chartOpts;

  if (chartType === "pie" || chartType === "donut") {
    pptxType = pres.charts.PIE;
    chartOpts = {
      x:cx, y:cy, w:cw, h:ch,
      chartColors: C.chartColors,
      chartArea: { fill:{color:C.bg}, roundedCorners:false },
      showLegend:true, legendPos:"b",
      showPercent:true,
      dataLabelColor:C.navy, dataLabelFontSize:10,
    };
  } else if (chartType === "line" || chartType === "line_smooth") {
    pptxType = pres.charts.LINE;
    chartOpts = {
      x:cx, y:cy, w:cw, h:ch,
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
      x:cx, y:cy, w:cw, h:ch,
      chartColors: C.chartColors,
      chartArea: { fill:{color:C.bg}, roundedCorners:false },
      catAxisLabelColor:C.slate, valAxisLabelColor:C.slate,
      valGridLine:{color:"E2E8F0", size:0.5}, catGridLine:{style:"none"},
      showValue:false, showLegend:false,
    };
  } else if (chartType === "stacked_bar") {
    pptxType = pres.charts.BAR;
    chartOpts = {
      x:cx, y:cy, w:cw, h:ch,
      barDir:"col", barGrouping:"stacked",
      chartColors: C.chartColors,
      chartArea: { fill:{color:C.bg}, roundedCorners:false },
      catAxisLabelColor:C.slate, valAxisLabelColor:C.slate,
      valGridLine:{color:"E2E8F0", size:0.5}, catGridLine:{style:"none"},
      showValue:false, showLegend:true, legendPos:"b",
    };
  } else {
    pptxType = pres.charts.BAR;
    chartOpts = {
      x:cx, y:cy, w:cw, h:ch,
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

// chart-full: full-width chart, title overlaid at top
function buildChartFull(s, slide, C, pres) {
  const content = slide.content || {};
  const highlight = content.highlight_text || null;

  // Full-width chart
  const chartY = 0.92;
  const chartH = H - chartY - (highlight ? 0.95 : 0.15);
  addChartToSlide(s, slide, C, pres, 0.3, chartY, W - 0.6, chartH);

  // Highlight callout
  if (highlight) {
    s.addShape("rect", {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadow(),
    });
    s.addText(highlight, {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fontSize:10, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:5,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// chart-top: chart on top 55%, insight bullets below in a row
function buildChartTop(s, slide, C, pres) {
  const content = slide.content || {};
  const bullets = content.bullets || [];
  const highlight = content.highlight_text || null;

  // Chart in top 55%
  const chartY = 0.92;
  const chartH = (H - chartY) * 0.55;
  addChartToSlide(s, slide, C, pres, 0.3, chartY, W - 0.6, chartH);

  // Insight bullets below chart in a horizontal row
  const bulletY = chartY + chartH + 0.15;
  const bulletItems = bullets.slice(0, 3);
  const count = bulletItems.length || 1;
  const bulletW = (W - 0.6 - (count - 1) * 0.15) / count;
  const bulletH = H - bulletY - (highlight ? 0.95 : 0.15);

  bulletItems.forEach((b, i) => {
    const bx = 0.3 + i * (bulletW + 0.15);
    s.addShape("rect", {
      x:bx, y:bulletY, w:bulletW, h:Math.max(bulletH, 0.5),
      fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:0.5},
      shadow:mkShadowSm(),
    });
    s.addShape("rect", { x:bx, y:bulletY, w:bulletW, h:0.06, fill:{color:C.teal}, line:{color:C.teal} });
    s.addText(bulletText(b), {
      x:bx + 0.08, y:bulletY + 0.12, w:bulletW - 0.16, h:Math.max(bulletH - 0.2, 0.3),
      fontSize:9.5, color:C.navy, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  if (highlight) {
    s.addShape("rect", {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadow(),
    });
    s.addText(highlight, {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fontSize:9.5, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:5,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// chart-with-kpi: large KPI number on left, chart on right
function buildChartWithKpi(s, slide, C, pres) {
  const content = slide.content || {};
  const bullets = content.bullets || [];
  const highlight = content.highlight_text || null;
  const chartData = content.chart_data || [];

  // KPI card on left (like metric slide)
  const kpiW = W * 0.3;
  const kpiY = 0.92;
  const kpiH = H - kpiY - (highlight ? 0.95 : 0.15);

  s.addShape("rect", {
    x:0.3, y:kpiY, w:kpiW, h:kpiH,
    fill:{color:C.navy}, line:{color:C.teal, width:1.5},
    shadow:mkShadow(),
  });

  // Extract KPI from first bullet or chart data
  let kpiVal = "—", kpiLabel = "";
  if (bullets.length > 0) {
    const text = bulletText(bullets[0]);
    const numMatch = text.match(/^([\$€£¥]?\s*[\d,.]+[%+\-×xKMBT]*)/);
    if (numMatch) {
      kpiVal = numMatch[1].trim();
      kpiLabel = text.substring(numMatch[0].length).replace(/^[\s:\-–—]+/, "").trim();
    } else {
      kpiVal = text.length <= 12 ? text : text.substring(0, 12);
      kpiLabel = text.length > 12 ? text : "";
    }
  } else if (chartData.length > 0) {
    kpiVal = String(chartData[0].value || chartData[0].y || "—");
    kpiLabel = String(chartData[0].label || chartData[0].name || "");
  }

  // Big number
  s.addText(kpiVal, {
    x:0.3, y:kpiY + 0.3, w:kpiW, h:kpiH * 0.5,
    fontSize:42, bold:true, color:"FFFFFF",
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  // KPI label
  if (kpiLabel) {
    s.addText(kpiLabel, {
      x:0.3 + 0.1, y:kpiY + kpiH * 0.55, w:kpiW - 0.2, h:kpiH * 0.35,
      fontSize:11, color:C.teal, align:"center", valign:"top",
      fontFace:C.fontBody, margin:0,
    });
  }

  // Chart on right
  const chartX = 0.3 + kpiW + 0.3;
  const chartW = W - chartX - 0.25;
  addChartToSlide(s, slide, C, pres, chartX, kpiY, chartW, kpiH);

  if (highlight) {
    s.addShape("rect", {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadow(),
    });
    s.addText(highlight, {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fontSize:9.5, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:5,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── CHART SLIDE ──────────────────────────────────────────────────────────────
async function buildChart(s, slide, C, pres) {
  const variant = slide.content?.layout_variant || slide.layout_variant || 'chart-right';
  const content   = slide.content || {};
  const chartType = (content.chart_type || "bar").toLowerCase();
  const chartData = content.chart_data || [];
  const highlight = content.highlight_text || null;
  const bullets   = content.bullets || [];

  // All variants share the section header + title
  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  switch (variant) {
    case 'chart-full':     return buildChartFull(s, slide, C, pres);
    case 'chart-top':      return buildChartTop(s, slide, C, pres);
    case 'chart-with-kpi': return buildChartWithKpi(s, slide, C, pres);
    default: break; // fall through to existing chart-right code
  }

  // ── Default: chart-right (existing behavior) ──

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

// ─── TABLE SLIDE VARIANTS ─────────────────────────────────────────────────────

// table-highlight: full-width table with one row highlighted in accent color + callout
function buildTableHighlight(s, slide, C) {
  const content   = slide.content || {};
  const tableData = content.table_data || {};
  const headers   = tableData.headers || [];
  const rows      = tableData.rows    || [];
  const highlight = content.highlight_text || null;
  const highlightRow = content.highlight_row != null ? content.highlight_row : 0;

  if (headers.length === 0 || rows.length === 0) {
    if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
    return;
  }

  const tableW = W - 0.8;
  const tableY = 0.92;
  const tableH = H - tableY - (highlight ? 1.8 : 0.3);
  const colW   = tableW / headers.length;
  const maxRows = highlight ? 6 : 8;
  const limitedRows = rows.slice(0, maxRows);

  const headerRow = headers.map(h => ({
    text: String(h),
    options: {
      fill:{color:C.navy}, color:"FFFFFF", bold:true,
      fontSize:11, fontFace:C.fontBody,
      align:"center", valign:"middle",
      border:{pt:0},
    },
  }));

  const dataRows = limitedRows.map((row, ri) =>
    (Array.isArray(row) ? row : [row]).map(cell => {
      const isHighlighted = ri === highlightRow;
      return {
        text: String(cell ?? ""),
        options: {
          fill:{color: isHighlighted ? C.teal : (ri % 2 === 0 ? "F8F9FA" : "FFFFFF")},
          color: isHighlighted ? C.dark : C.navy,
          bold: isHighlighted,
          fontSize:10, fontFace:C.fontBody,
          align:"center", valign:"middle",
          border:{pt:0.5, color: isHighlighted ? C.teal : "E2E8F0"},
        },
      };
    })
  );

  s.addTable([headerRow, ...dataRows], {
    x:0.4, y:tableY, w:tableW, h:tableH,
    colW: Array(headers.length).fill(colW),
  });

  // Callout shape pointing to highlighted row
  const calloutY = tableY + (highlightRow + 1) * (tableH / (limitedRows.length + 1));
  const calloutX = 0.4 + tableW + 0.1;
  if (calloutX + 1.5 <= W) {
    // Small accent callout to the right of the table
    s.addShape("rect", {
      x:0.4 + tableW - 2.5, y:Math.min(calloutY, H - 1.5), w:2.5, h:0.45,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadowSm(),
    });
    s.addText("▶ Key Row", {
      x:0.4 + tableW - 2.5, y:Math.min(calloutY, H - 1.5), w:2.5, h:0.45,
      fontSize:9, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:0,
    });
  }

  if (highlight) {
    s.addShape("rect", {
      x:0.4, y:H - 0.82, w:W - 0.8, h:0.68,
      fill:{color:C.teal}, line:{color:C.teal},
      shadow:mkShadow(),
    });
    s.addText("▶  " + highlight, {
      x:0.4, y:H - 0.82, w:W - 0.8, h:0.68,
      fontSize:11, bold:true, color:C.dark,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:6,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── TABLE SLIDE ──────────────────────────────────────────────────────────────
async function buildTable(s, slide, C) {
  const variant = slide.content?.layout_variant || slide.layout_variant || 'table-full';
  const content   = slide.content || {};
  const tableData = content.table_data || {};
  const headers   = tableData.headers || [];
  const rows      = tableData.rows    || [];
  const highlight = content.highlight_text || null;
  const bullets   = content.bullets || [];

  // All variants share the section header + title
  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  switch (variant) {
    case 'table-with-insights':
      // table-with-insights is the existing behavior when bullets are present
      // Force the bullets path by falling through with hasBullets = true
      break;
    case 'table-highlight':
      return buildTableHighlight(s, slide, C);
    default: break; // fall through to existing table-full code
  }

  // ── Default: table-full / table-with-insights (existing behavior) ──

  if (headers.length > 0 && rows.length > 0) {
    // table-with-insights forces the bullets panel even if bullets are present
    const hasBullets = variant === 'table-with-insights' ? bullets.length > 0 : bullets.length > 0;
    const tableW = hasBullets ? W * 0.62 : W - 0.8;
    const tableY = 0.92;
    // Reserve more space at bottom for highlight text: 0.82 (position) + 0.68 (height) + 0.3 (margin) = 1.8
    const tableH = H - tableY - (highlight ? 1.8 : 0.3);
    const colW   = tableW / headers.length;
    
    // Limit rows to prevent overflow - max 6 rows when highlight exists, 8 otherwise
    const maxRows = highlight ? 6 : 8;
    const limitedRows = rows.slice(0, maxRows);

    const headerRow = headers.map(h => ({
      text: String(h),
      options: {
        fill:{color:C.navy}, color:"FFFFFF", bold:true,
        fontSize:11, fontFace:C.fontBody,
        align:"center", valign:"middle",
        border:{pt:0},
      },
    }));

    const dataRows = limitedRows.map((row, ri) =>
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
        // Stop rendering bullets if they would overlap with highlight text
        if (by + 0.72 > H - (highlight ? 1.8 : 0.25)) return;
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

// ─── COMPARISON SLIDE VARIANTS ────────────────────────────────────────────────

// Helper: extract comparison data from slide
function extractComparisonData(slide) {
  const content = slide.content || {};
  const comp    = content.comparison_data || {};

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

  return { leftH, rightH, leftItems, rightItems };
}

// pros-cons: two-column with green checkmarks (left) and red X marks (right)
function buildComparisonProsCons(s, slide, C) {
  const { leftH, rightH, leftItems, rightItems } = extractComparisonData(slide);
  const highlight = (slide.content || {}).highlight_text || null;

  const colW = (W - 1.0) / 2;
  const colY = 0.92;
  const colH = H - colY - (highlight ? 0.95 : 0.3);

  // ── Left column (Pros — green) ──
  const proColor = "22C55E";
  s.addShape("rect", {
    x:0.3, y:colY, w:colW, h:colH,
    fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:1},
    shadow:mkShadow(),
  });
  s.addShape("rect", { x:0.3, y:colY, w:colW, h:0.55, fill:{color:C.navy}, line:{color:C.navy} });
  s.addText(leftH || "Pros", {
    x:0.3, y:colY, w:colW, h:0.55,
    fontSize:14, bold:true, color:"FFFFFF",
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  leftItems.slice(0, 6).forEach((item, i) => {
    const iy = colY + 0.62 + i * 0.68;
    if (iy + 0.6 > H - (highlight ? 1.0 : 0.25)) return;
    s.addShape("rect", {
      x:0.35, y:iy, w:colW - 0.1, h:0.6,
      fill:{color:"F0FDF4"}, line:{color:"DCFCE7", width:0.5},
    });
    const itemText = typeof item === 'string' ? item : (item?.text || JSON.stringify(item));
    s.addText([
      { text:"✓  ", options:{color:proColor, bold:true, fontSize:12} },
      { text:itemText, options:{color:C.navy} },
    ], {
      x:0.42, y:iy + 0.05, w:colW - 0.24, h:0.5,
      fontSize:10.5, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // ── Right column (Cons — red) ──
  const conColor = "EF4444";
  const rx = 0.3 + colW + 0.4;
  s.addShape("rect", {
    x:rx, y:colY, w:colW, h:colH,
    fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:1},
    shadow:mkShadow(),
  });
  s.addShape("rect", { x:rx, y:colY, w:colW, h:0.55, fill:{color:C.teal}, line:{color:C.teal} });
  s.addText(rightH || "Cons", {
    x:rx, y:colY, w:colW, h:0.55,
    fontSize:14, bold:true, color:C.dark,
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  rightItems.slice(0, 6).forEach((item, i) => {
    const iy = colY + 0.62 + i * 0.68;
    if (iy + 0.6 > H - (highlight ? 1.0 : 0.25)) return;
    s.addShape("rect", {
      x:rx + 0.05, y:iy, w:colW - 0.1, h:0.6,
      fill:{color:"FEF2F2"}, line:{color:"FECACA", width:0.5},
    });
    const itemText = typeof item === 'string' ? item : (item?.text || JSON.stringify(item));
    s.addText([
      { text:"✗  ", options:{color:conColor, bold:true, fontSize:12} },
      { text:itemText, options:{color:C.navy} },
    ], {
      x:rx + 0.12, y:iy + 0.05, w:colW - 0.24, h:0.5,
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
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadow(),
    });
    s.addText(highlight, {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fontSize:10, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:5,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// before-after: left column muted/grayed, right column accent-emphasized
function buildComparisonBeforeAfter(s, slide, C) {
  const { leftH, rightH, leftItems, rightItems } = extractComparisonData(slide);
  const highlight = (slide.content || {}).highlight_text || null;

  const colW = (W - 1.0) / 2;
  const colY = 0.92;
  const colH = H - colY - (highlight ? 0.95 : 0.3);

  // ── Left column (Before — muted/grayed) ──
  s.addShape("rect", {
    x:0.3, y:colY, w:colW, h:colH,
    fill:{color:"F1F5F9"}, line:{color:"CBD5E1", width:1},
    shadow:mkShadowSm(),
  });
  s.addShape("rect", { x:0.3, y:colY, w:colW, h:0.55, fill:{color:C.slate}, line:{color:C.slate} });
  s.addText(leftH || "Before", {
    x:0.3, y:colY, w:colW, h:0.55,
    fontSize:14, bold:true, color:"FFFFFF",
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  leftItems.slice(0, 6).forEach((item, i) => {
    const iy = colY + 0.62 + i * 0.68;
    if (iy + 0.6 > H - (highlight ? 1.0 : 0.25)) return;
    s.addShape("rect", {
      x:0.35, y:iy, w:colW - 0.1, h:0.6,
      fill:{color:"F8FAFC"}, line:{color:"E2E8F0", width:0.5},
    });
    const itemText = typeof item === 'string' ? item : (item?.text || JSON.stringify(item));
    // Muted gray text for "before" state
    s.addText([
      { text:"›  ", options:{color:C.slateL, bold:true} },
      { text:itemText, options:{color:C.slate} },
    ], {
      x:0.42, y:iy + 0.05, w:colW - 0.24, h:0.5,
      fontSize:10.5, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // ── Right column (After — accent emphasized) ──
  const rx = 0.3 + colW + 0.4;
  s.addShape("rect", {
    x:rx, y:colY, w:colW, h:colH,
    fill:{color:"FFFFFF"}, line:{color:C.teal, width:1.5},
    shadow:mkShadow(),
  });
  s.addShape("rect", { x:rx, y:colY, w:colW, h:0.55, fill:{color:C.teal}, line:{color:C.teal} });
  s.addText(rightH || "After", {
    x:rx, y:colY, w:colW, h:0.55,
    fontSize:14, bold:true, color:C.dark,
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  rightItems.slice(0, 6).forEach((item, i) => {
    const iy = colY + 0.62 + i * 0.68;
    if (iy + 0.6 > H - (highlight ? 1.0 : 0.25)) return;
    s.addShape("rect", {
      x:rx + 0.05, y:iy, w:colW - 0.1, h:0.6,
      fill:{color:"FFFFFF"}, line:{color:C.teal, width:0.5},
      shadow:mkShadowSm(),
    });
    const itemText = typeof item === 'string' ? item : (item?.text || JSON.stringify(item));
    // Accent-colored text for "after" state
    s.addText([
      { text:"▶  ", options:{color:C.teal, bold:true} },
      { text:itemText, options:{color:C.navy, bold:true} },
    ], {
      x:rx + 0.12, y:iy + 0.05, w:colW - 0.24, h:0.5,
      fontSize:10.5, fontFace:C.fontBody, valign:"middle", margin:0,
    });
  });

  // Arrow divider (before → after)
  s.addShape("rect", {
    x:0.3 + colW + 0.14, y:colY, w:0.12, h:colH,
    fill:{color:C.teal, transparency:20}, line:{color:C.teal, transparency:20},
  });
  s.addText("→", {
    x:0.3 + colW + 0.05, y:colY + colH / 2 - 0.25, w:0.3, h:0.5,
    fontSize:20, bold:true, color:C.teal,
    align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
  });

  if (highlight) {
    s.addShape("rect", {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadow(),
    });
    s.addText(highlight, {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fontSize:10, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:5,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// icon-rows: two columns with icon + title + description rows and thin dividers
async function buildComparisonIconRows(s, slide, C) {
  const content = slide.content || {};
  const comp = content.comparison_data || {};
  const highlight = content.highlight_text || null;

  // Extract columns — support both "items" (rich) and "bullets" (plain) formats
  function getColumnData(col) {
    if (!col || typeof col !== 'object') return { heading: "", items: [] };
    const heading = col.heading || col.title || "";
    if (col.items && Array.isArray(col.items)) {
      return { heading, items: col.items };
    }
    // Convert plain bullets to items format
    const bullets = col.bullets || [];
    const items = bullets.map(b => {
      if (typeof b === 'object' && b.title) return b;
      return { title: typeof b === 'string' ? b : String(b) };
    });
    return { heading, items };
  }

  const left = getColumnData(comp.left_column || { heading: comp.left_title, bullets: comp.left });
  const right = getColumnData(comp.right_column || { heading: comp.right_title, bullets: comp.right });

  const colW = (W - 1.0) / 2;
  const colY = 0.92;
  const colH = H - colY - (highlight ? 0.95 : 0.3);

  // Render one column
  async function renderColumn(cx, col, headerColor) {
    // Colored header bar
    s.addShape("rect", {
      x:cx, y:colY, w:colW, h:0.55,
      fill:{color:headerColor}, line:{color:headerColor},
    });
    s.addText(col.heading, {
      x:cx, y:colY, w:colW, h:0.55,
      fontSize:13, bold:true, color:"FFFFFF",
      align:"center", valign:"middle", fontFace:C.fontHeader, margin:0,
    });

    // White card body
    s.addShape("rect", {
      x:cx, y:colY + 0.55, w:colW, h:colH - 0.55,
      fill:{color:"FFFFFF"}, line:{color:"E2E8F0", width:0.5},
    });

    const maxItems = Math.min(col.items.length, 5);
    const itemH = Math.min(0.85, (colH - 0.65) / maxItems);

    for (let i = 0; i < maxItems; i++) {
      const item = col.items[i];
      const iy = colY + 0.62 + i * itemH;
      if (iy + itemH > H - (highlight ? 1.0 : 0.2)) break;

      const iconName = item.icon || null;
      const title = item.title || (typeof item === 'string' ? item : String(item));
      const desc = item.description || "";

      // Icon circle
      if (iconName) {
        const ic = await iconToBase64(iconName, "#" + C.teal, 256);
        if (ic) {
          s.addShape("ellipse", {
            x:cx + 0.15, y:iy + 0.05, w:0.5, h:0.5,
            fill:{color:C.navy, transparency:90}, line:{color:"E2E8F0", width:0.5},
          });
          s.addImage({ data:ic, x:cx + 0.22, y:iy + 0.12, w:0.36, h:0.36 });
        }
      }

      // Title + description
      const textX = iconName ? cx + 0.75 : cx + 0.2;
      const textW = colW - (iconName ? 0.95 : 0.4);

      s.addText(title, {
        x:textX, y:iy + 0.05, w:textW, h:desc ? 0.3 : itemH - 0.1,
        fontSize:11, bold:true, color:C.text,
        fontFace:C.fontHeader, valign:"middle", margin:0,
      });

      if (desc) {
        s.addText(desc, {
          x:textX, y:iy + 0.35, w:textW, h:itemH - 0.45,
          fontSize:9, color:C.slate,
          fontFace:C.fontBody, valign:"top", margin:0,
        });
      }

      // Thin divider (except after last item)
      if (i < maxItems - 1) {
        s.addShape("rect", {
          x:cx + 0.15, y:iy + itemH - 0.02, w:colW - 0.3, h:0.01,
          fill:{color:"E2E8F0"}, line:{color:"E2E8F0"},
        });
      }
    }
  }

  await renderColumn(0.3, left, C.navy);
  await renderColumn(0.3 + colW + 0.4, right, C.teal);

  if (highlight) {
    s.addShape("rect", {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fill:{color:C.navy}, line:{color:C.teal, width:1},
      shadow:mkShadow(),
    });
    s.addText(highlight, {
      x:0.3, y:H - 0.82, w:W - 0.6, h:0.68,
      fontSize:10, bold:true, color:C.teal,
      align:"center", valign:"middle", fontFace:C.fontBody, margin:5,
    });
  }

  if (slide.speaker_notes) s.addNotes(slide.speaker_notes);
}

// ─── COMPARISON SLIDE ─────────────────────────────────────────────────────────
async function buildComparison(s, slide, C) {
  const variant = slide.content?.layout_variant || slide.layout_variant || 'two-column';
  const content = slide.content || {};
  const comp    = content.comparison_data || {};
  const highlight = content.highlight_text || null;

  console.log(`[DEBUG] Comparison slide data:`, JSON.stringify(comp, null, 2));

  const { leftH, rightH, leftItems, rightItems } = extractComparisonData(slide);

  console.log(`[DEBUG] Extracted leftItems:`, JSON.stringify(leftItems));
  console.log(`[DEBUG] Extracted rightItems:`, JSON.stringify(rightItems));

  // All variants share the section header + title
  addSectionHeader(s, null, C);
  s.addText(slide.title || "", {
    x:0.45, y:0.1, w:W-0.9, h:0.62,
    fontSize:18, bold:true, color:"FFFFFF",
    fontFace:C.fontHeader, charSpacing:1, valign:"middle", margin:0,
  });

  switch (variant) {
    case 'pros-cons':    return buildComparisonProsCons(s, slide, C);
    case 'before-after': return buildComparisonBeforeAfter(s, slide, C);
    case 'icon-rows':    return buildComparisonIconRows(s, slide, C);
    default: break; // fall through to existing two-column code
  }

  // ── Default: two-column (existing behavior) ──

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
    const itemText = typeof item === 'string' ? item : (item?.text || JSON.stringify(item));
    console.log(`[DEBUG] Left item ${i}: type=${typeof item}, value=${JSON.stringify(item)}, extracted=${itemText}`);
    s.addText([
      { text:"›  ", options:{color:C.navy, bold:true} },
      { text:itemText, options:{color:C.navy} },
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
    const itemText = typeof item === 'string' ? item : (item?.text || JSON.stringify(item));
    console.log(`[DEBUG] Right item ${i}: type=${typeof item}, value=${JSON.stringify(item)}, extracted=${itemText}`);
    s.addText([
      { text:"›  ", options:{color:C.teal, bold:true} },
      { text:itemText, options:{color:C.navy} },
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

module.exports = { buildPptx, resolveDesign, THEMES };
