#!/usr/bin/env node
// OPTIONAL fallback: fetch a YouTube transcript through Apify.
// Use it when yt-dlp can't get captions (for example, from a cloud machine YouTube blocks).
// Needs an Apify account. Put your token in the APIFY_API_TOKEN env var (or in .env next to SKILL.md).
// Apify bills per run, so this costs a little each time.
// Usage: node fetch-transcript-apify.js <youtube-url-or-id>

const { loadDotEnv } = require("./config");
const { extractVideoId } = require("./video-id");

loadDotEnv();

const input = process.argv[2];
if (!input) {
  console.error("Usage: node fetch-transcript-apify.js <youtube-url-or-id>");
  process.exit(1);
}

const videoId = extractVideoId(input);
if (!videoId) {
  console.error("Could not find a video ID in:", input);
  process.exit(1);
}

const token = process.env.APIFY_API_TOKEN;
if (!token) {
  console.error("APIFY_API_TOKEN is not set. Apify is optional; skip this step or add the token to your env.");
  process.exit(4);
}

// Community actor that renders the YouTube page and returns captions.
const ACTOR = process.env.APIFY_TRANSCRIPT_ACTOR || "karamelo~youtube-transcripts";
const endpoint = `https://api.apify.com/v2/acts/${ACTOR}/run-sync-get-dataset-items`;

const body = JSON.stringify({
  urls: [`https://www.youtube.com/watch?v=${videoId}`],
  maxRetries: 8,
  proxyOptions: { useApifyProxy: true },
});

fetch(endpoint, {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  body,
})
  .then((res) => {
    if (!res.ok) throw new Error(`Apify returned ${res.status} ${res.statusText}`);
    return res.json();
  })
  .then((data) => {
    if (!Array.isArray(data) || data.length === 0) {
      console.error("Apify returned no results");
      process.exit(2);
    }
    const captions = data[0].captions;
    if (!captions || (Array.isArray(captions) && captions.length === 0)) {
      console.error("Apify found no captions for", videoId);
      process.exit(2);
    }
    let text = Array.isArray(captions) ? captions.join(" ") : String(captions);
    text = text
      .replace(/&#39;/g, "'")
      .replace(/&quot;/g, '"')
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&")
      .replace(/\s+/g, " ")
      .trim();
    console.log(text);
  })
  .catch((err) => {
    console.error("Apify transcript fetch failed:", err.message);
    process.exit(1);
  });
