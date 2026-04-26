"use strict";

/**
 * Logo loader — reads the Hexaware logo and returns a base64 PNG for embedding in slides.
 */

const path = require("path");
const fs = require("fs");

let sharp;
try {
  sharp = require("sharp");
} catch (e) {
  // sharp unavailable — logo will be skipped
}

let _cachedLogoBase64 = null;

/**
 * Load the Hexaware logo as a base64 PNG data URI.
 * Result is cached after first load.
 * @param {number} width  - Output width in pixels (default 240 - larger size)
 * @param {number} height - Output height in pixels (default 60 - larger size)
 * @returns {Promise<string|null>} base64 PNG data URI or null
 */
async function getHexawareLogoBase64(width = 240, height = 60) {
  if (_cachedLogoBase64) return _cachedLogoBase64;

  try {
    // Use the new Icon.jpeg file from assets folder
    const logoPath = path.join(__dirname, "assets", "Icon.jpeg");
    const logoBuffer = fs.readFileSync(logoPath);

    if (sharp) {
      // Convert JPEG → PNG with sharp, preserving aspect ratio
      const pngBuffer = await sharp(logoBuffer)
        .resize(width, height, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
        .png()
        .toBuffer();
      _cachedLogoBase64 = "image/png;base64," + pngBuffer.toString("base64");
    } else {
      // Fallback: embed the JPEG directly as base64
      _cachedLogoBase64 = "image/jpeg;base64," + logoBuffer.toString("base64");
    }

    return _cachedLogoBase64;
  } catch (e) {
    console.warn("Hexaware logo load failed:", e.message);
    return null;
  }
}

module.exports = { getHexawareLogoBase64 };
