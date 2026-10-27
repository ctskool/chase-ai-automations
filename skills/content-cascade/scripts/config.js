#!/usr/bin/env node
// Loads config.json (next to SKILL.md) and an optional .env file, and resolves paths.
// Run it directly to print the resolved settings:
//   node scripts/config.js

const fs = require("fs");
const os = require("os");
const path = require("path");

const SKILL_DIR = path.resolve(__dirname, "..");

const DEFAULTS = {
  output_folder: "~/content-cascade",
  voice_guide: "./voice-guide.md",
  watch_channel: "",
};

// Load KEY=value lines from .env next to SKILL.md. Real env vars win.
function loadDotEnv() {
  const envPath = path.join(SKILL_DIR, ".env");
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!m || m[1] in process.env) continue;
    const value = m[2].replace(/^["']|["']$/g, "");
    if (value) process.env[m[1]] = value;
  }
}

// "~" means your home folder. Relative paths are relative to the skill folder.
function resolvePath(p) {
  if (!p) return p;
  if (p === "~" || p.startsWith("~/") || p.startsWith("~\\")) {
    p = path.join(os.homedir(), p.slice(1));
  }
  return path.isAbsolute(p) ? p : path.resolve(SKILL_DIR, p);
}

function loadConfig() {
  loadDotEnv();
  const configPath = path.join(SKILL_DIR, "config.json");
  let user = {};
  if (fs.existsSync(configPath)) {
    try {
      user = JSON.parse(fs.readFileSync(configPath, "utf8"));
    } catch (e) {
      throw new Error(`config.json is not valid JSON: ${e.message}`);
    }
  }
  const cfg = { ...DEFAULTS, ...user };
  return {
    config_file: fs.existsSync(configPath) ? configPath : null,
    output_folder: resolvePath(cfg.output_folder),
    voice_guide: resolvePath(cfg.voice_guide),
    voice_guide_exists: fs.existsSync(resolvePath(cfg.voice_guide)),
    watch_channel: (cfg.watch_channel || "").trim(),
    apify_token_set: !!process.env.APIFY_API_TOKEN,
  };
}

module.exports = { loadConfig, loadDotEnv, resolvePath, SKILL_DIR };

if (require.main === module) {
  try {
    console.log(JSON.stringify(loadConfig(), null, 2));
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }
}
