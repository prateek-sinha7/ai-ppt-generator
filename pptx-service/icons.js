"use strict";

/**
 * Icon renderer — converts react-icons SVGs to base64 PNG via sharp.
 * Falls back gracefully if sharp or react-icons are unavailable.
 */

let React, ReactDOMServer, sharp, fa, md, hi, bi;

try {
  React = require("react");
  ReactDOMServer = require("react-dom/server");
  sharp = require("sharp");
  fa = require("react-icons/fa");
  md = require("react-icons/md");
  hi = require("react-icons/hi");
  bi = require("react-icons/bi");
} catch (e) {
  // Icons unavailable — will return null and callers skip icon rendering
}

// Map icon names to react-icons components
const ICON_MAP = {
  // Trending / Analytics
  TrendingUp:       () => fa && fa.FaChartLine,
  TrendingDown:     () => fa && fa.FaChartBar,
  BarChart2:        () => fa && fa.FaChartBar,
  Activity:         () => fa && fa.FaHeartbeat,
  Analytics:        () => md && md.MdAnalytics,
  // People / Org
  Users:            () => fa && fa.FaUsers,
  Briefcase:        () => fa && fa.FaBriefcase,
  Handshake:        () => fa && fa.FaHandshake,
  // Security / Trust
  Shield:           () => fa && fa.FaShieldAlt,
  Lock:             () => fa && fa.FaLock,
  Unlock:           () => fa && fa.FaUnlock,
  Security:         () => md && md.MdSecurity,
  // Tech / Data
  Database:         () => fa && fa.FaDatabase,
  Cpu:              () => fa && fa.FaMicrochip,
  Network:          () => fa && fa.FaNetworkWired,
  Cogs:             () => fa && fa.FaCogs,
  Settings:         () => fa && fa.FaCog,
  Tool:             () => fa && fa.FaTools,
  Layers:           () => fa && fa.FaLayerGroup,
  Cubes:            () => fa && fa.FaCubes,
  // Finance / Business
  DollarSign:       () => fa && fa.FaDollarSign,
  Target:           () => fa && fa.FaBullseye,
  Award:            () => fa && fa.FaAward,
  Star:             () => fa && fa.FaStar,
  Crown:            () => fa && fa.FaCrown,
  Diamond:          () => fa && fa.FaGem,
  // Status / Alerts
  CheckCircle:      () => fa && fa.FaCheckCircle,
  AlertTriangle:    () => fa && fa.FaExclamationTriangle,
  Flag:             () => fa && fa.FaFlag,
  // World / Location
  Globe:            () => fa && fa.FaGlobe,
  Map:              () => fa && fa.FaMap,
  Building:         () => bi && bi.BiBuilding,
  // Ideas / Innovation
  Lightbulb:        () => fa && fa.FaLightbulb,
  Rocket:           () => fa && fa.FaRocket,
  Zap:              () => fa && fa.FaBolt,
  Fire:             () => fa && fa.FaFire,
  Brain:            () => fa && fa.FaBrain,
  // Time / Process
  Clock:            () => fa && fa.FaClock,
  Calendar:         () => fa && fa.FaCalendar,
  // Logistics
  Package:          () => fa && fa.FaBox,
  Truck:            () => fa && fa.FaTruck,
  // Health
  Heart:            () => fa && fa.FaHeart,
  // Search / Misc
  Search:           () => fa && fa.FaSearch,
  // Industry icons
  Industry:         () => fa && fa.FaIndustry,
  Hospital:         () => fa && fa.FaHospital,
  University:       () => fa && fa.FaUniversity,
  Leaf:             () => fa && fa.FaLeaf,
  // Material Design extras
  Speed:            () => md && md.MdSpeed,
  AccountBalance:   () => md && md.MdAccountBalance,
  // Bootstrap extras
  Graph:            () => bi && bi.BiLineChart,
};

/**
 * Render an icon to a base64 PNG string.
 * @param {string} iconName - Icon name from ICON_MAP
 * @param {string} color - Hex color with # prefix
 * @param {number} size - Rasterization size in pixels (default 256)
 * @returns {Promise<string|null>} base64 PNG data URI or null
 */
async function iconToBase64(iconName, color = "#FFFFFF", size = 256) {
  if (!React || !ReactDOMServer || !sharp) return null;

  const getComponent = ICON_MAP[iconName];
  if (!getComponent) return null;

  const IconComponent = getComponent();
  if (!IconComponent) return null;

  try {
    const svg = ReactDOMServer.renderToStaticMarkup(
      React.createElement(IconComponent, { color, size: String(size) })
    );
    const pngBuffer = await sharp(Buffer.from(svg)).png().toBuffer();
    return "image/png;base64," + pngBuffer.toString("base64");
  } catch (e) {
    console.warn(`Icon render failed for ${iconName}:`, e.message);
    return null;
  }
}

module.exports = { iconToBase64 };
