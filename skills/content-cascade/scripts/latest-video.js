#!/usr/bin/env node
// Lists the newest long-form videos on the channel in config.json ("watch_channel"),
// and marks which ones already have drafts in your output folder.
// Usage: node latest-video.js [--count 5]
// Prints JSON: { channel, videos: [{ id, title, url, upload_date, duration, has_drafts }], next }
// "next" is the newest video with no drafts yet, or null.

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const { loadConfig } = require("./config");

const args = process.argv.slice(2);
const countIdx = args.indexOf("--count");
const count = countIdx >= 0 ? parseInt(args[countIdx + 1], 10) || 5 : 5;

const cfg = loadConfig();
if (!cfg.watch_channel) {
  console.error('No "watch_channel" in config.json. Add your channel (like "@yourhandle") or pass a video URL instead.');
  process.exit(1);
}

// Accepts "@handle", a channel ID ("UC..."), or a full channel URL.
function channelVideosUrl(ch) {
  if (/^https?:\/\//.test(ch)) return ch.replace(/\/+$/, "").replace(/\/(videos|shorts|streams|featured)$/, "") + "/videos";
  if (ch.startsWith("@")) return `https://www.youtube.com/${ch}/videos`;
  if (/^UC[a-zA-Z0-9_-]{22}$/.test(ch)) return `https://www.youtube.com/channel/${ch}/videos`;
  return `https://www.youtube.com/@${ch}/videos`;
}

// Find video IDs that already have drafts (any .md with "video_id: <id>" in it).
function draftedIds(dir) {
  const ids = new Set();
  if (!fs.existsSync(dir)) return ids;
  const walk = (d) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, entry.name);
      if (entry.isDirectory()) walk(p);
      else if (entry.name.endsWith(".md")) {
        const m = fs.readFileSync(p, "utf8").match(/^video_id:\s*["']?([a-zA-Z0-9_-]{11})/m);
        if (m) ids.add(m[1]);
      }
    }
  };
  walk(dir);
  return ids;
}

let out;
try {
  out = execFileSync(
    "yt-dlp",
    ["--flat-playlist", "--playlist-end", String(count), "--print", "%(id)s\t%(title)s\t%(duration)s\t%(upload_date)s", channelVideosUrl(cfg.watch_channel)],
    { encoding: "utf8", timeout: 90000, stdio: ["ignore", "pipe", "pipe"] }
  );
} catch (e) {
  console.error(e.code === "ENOENT" ? "yt-dlp is not installed or not on your PATH." : `yt-dlp failed: ${e.message}`);
  process.exit(1);
}

const done = draftedIds(cfg.output_folder);
const videos = out
  .trim()
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => {
    const [id, title, dur, date] = line.split("\t");
    return {
      id,
      title,
      url: `https://youtu.be/${id}`,
      upload_date: /^\d{8}$/.test(date) ? `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6)}` : null,
      duration: parseFloat(dur) || null,
      has_drafts: done.has(id),
    };
  })
  // Skip Shorts. The /videos tab mostly excludes them already; this catches stragglers.
  .filter((v) => v.duration === null || v.duration > 90);

console.log(JSON.stringify({ channel: cfg.watch_channel, videos, next: videos.find((v) => !v.has_drafts) || null }, null, 2));
