#!/usr/bin/env node
// Fetch a YouTube transcript with yt-dlp captions. Free, no account needed.
// Order: captions the creator uploaded, then YouTube's original-language auto captions (en-orig),
// then plain auto captions (en). Plain auto captions are sometimes wrong on fresh uploads.
// Usage: node fetch-transcript-ytdlp.js <youtube-url-or-id> [--lang xx]
// Prints the transcript as plain text. Exit codes: 1 bad input, 2 no captions, 3 parse error.

const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { extractVideoId } = require("./video-id");

const args = process.argv.slice(2);
const langIdx = args.indexOf("--lang");
const lang = langIdx >= 0 ? args[langIdx + 1] : "en";
const input = args.find((a, i) => !a.startsWith("--") && i !== langIdx + 1);

if (!input) {
  console.error("Usage: node fetch-transcript-ytdlp.js <url|id> [--lang xx]");
  process.exit(1);
}

const id = extractVideoId(input);
if (!id) {
  console.error("Could not find a video ID in:", input);
  process.exit(1);
}

const workDir = fs.mkdtempSync(path.join(os.tmpdir(), `yt-tr-${id}-`));
const url = `https://youtu.be/${id}`;

function tryLang(subLang, auto) {
  const flag = auto ? "--write-auto-subs" : "--write-subs";
  try {
    execFileSync(
      "yt-dlp",
      [flag, "--sub-langs", subLang, "--skip-download", "--sub-format", "json3", "-o", path.join(workDir, "sub"), url],
      { stdio: "pipe" }
    );
  } catch (e) {
    if (e.code === "ENOENT") {
      console.error("yt-dlp is not installed or not on your PATH.");
      process.exit(1);
    }
    return null;
  }
  const files = fs.readdirSync(workDir).filter((f) => f.endsWith(".json3"));
  return files.length ? path.join(workDir, files[0]) : null;
}

function cleanup() {
  try { fs.rmSync(workDir, { recursive: true, force: true }); } catch {}
}

let file = tryLang(lang, false) || tryLang(`${lang}-orig`, true) || tryLang(lang, true);

if (!file) {
  cleanup();
  console.error("No captions found for", id);
  process.exit(2);
}

try {
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  const text = (data.events || [])
    .filter((e) => e.segs)
    .map((e) => e.segs.map((s) => s.utf8 || "").join(""))
    .join(" ")
    .replace(/\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  cleanup();
  if (!text) {
    console.error("Captions file was empty for", id);
    process.exit(2);
  }
  console.log(text);
} catch (e) {
  cleanup();
  console.error("Could not read captions:", e.message);
  process.exit(3);
}
