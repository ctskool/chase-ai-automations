---
name: content-cascade
description: "Turn a YouTube video into three drafts in the user's own voice: a blog post, an X post, and a LinkedIn post, saved as Markdown files. Gets the transcript with yt-dlp (Apify optional fallback) and reads the user's voice guide. Drafts only, nothing gets posted. Use when the user says things like 'turn this video into posts', 'repurpose this video', 'write a blog post from my video', 'make an X post and LinkedIn post from this YouTube link', 'content cascade for this video', 'run content cascade on my latest video', or '/content-cascade'."
---

# Content Cascade

Turn one YouTube video into three drafts: a blog post, an X post, and a LinkedIn post.
Everything is written in the user's voice, from their voice guide.
Drafts are saved as Markdown files. **Nothing is ever posted or published.**

The scripts live in this skill's folder, usually `~/.claude/skills/content-cascade/`.
Below, `SKILL_DIR` means that folder. If the skill is installed somewhere else, use that path.

## Modes

- **Full (default):** blog + X post + LinkedIn post.
- **Pick and choose:** if the user asks for only some pieces ("just the blog", "only LinkedIn", "skip the blog"), make only those. Still fetch the transcript.

## Step 0: Load settings

```bash
node "SKILL_DIR/scripts/config.js"
```

This prints the resolved settings as JSON:
- `output_folder`: where drafts go.
- `voice_guide` and `voice_guide_exists`: the user's voice guide.
- `watch_channel`: optional channel used for "my latest video".
- `apify_token_set`: whether the optional Apify fallback can run.

If `config_file` is null, tell the user once: "No config.json yet, so I'm using defaults. Copy config.example.json to config.json to change them."

**Read the voice guide file now.** If it doesn't exist, say so and continue with the default writing rules below. Suggest they copy `voice-guide.example.md` to `voice-guide.md` and fill it in.

## Step 1: Find the video

- **The user gave a YouTube URL or ID:** use it.
- **The user said "my latest video" (or gave nothing):** run

  ```bash
  node "SKILL_DIR/scripts/latest-video.js"
  ```

  It lists the newest long-form videos on `watch_channel` and marks which ones already have drafts. Use `next` (the newest video with no drafts). If `next` is null, say everything recent is already done and stop. If `watch_channel` is empty, ask the user for a URL.

  In an interactive session, confirm: "Found your latest video: TITLE. Drafting from this one."

Get the title (and upload date, for the file name) if you don't have it:

```bash
yt-dlp --skip-download --print "%(title)s" --print "%(upload_date)s" "<url>"
```

## Step 2: Get the transcript

Try these in order. Move on if one fails.

1. **yt-dlp (free, default):**
   ```bash
   node "SKILL_DIR/scripts/fetch-transcript-ytdlp.js" "<url>"
   ```
   Add `--lang xx` for a non-English video (for example `--lang es`).

2. **Apify (optional fallback):** only if `apify_token_set` is true.
   ```bash
   node "SKILL_DIR/scripts/fetch-transcript-apify.js" "<url>"
   ```
   It can take 30 to 60 seconds. It costs a small amount per run on the user's Apify account.

**Check the transcript matches the video.** Compare the first few sentences with the title.
If they clearly don't match, the captions are wrong. Throw them out and try the next method.

**If every method fails,** captions probably aren't ready yet. Tell the user:
> "Captions aren't available for this video yet. YouTube can take 30 to 60 minutes after upload. Try again in a bit."

Do not write anything without a transcript. Stop here.

## Step 3: Write the blog post

Follow the voice guide first. Then follow these rules where the voice guide doesn't say otherwise.

**Structure**
- `# Title` on the first line. Include the main keyword. Aim for under 60 characters. No clickbait.
- A bold one-line hook right after the title.
- The first 40 to 60 words answer the core question directly. No throat-clearing.
- `##` headings written as questions people search for ("How Do You Set Up X?").
- Each `##` section makes sense on its own. Search engines and AI tools quote sections in isolation.
- Paragraphs of 2 to 4 sentences. Mix short and long sentences.
- Bold the key definitions and quotable lines.
- Numbered steps for processes. Bullets for options. Don't over-format.
- At least one concrete example from the video, framed as problem, what was done, result.
- End with `## Frequently Asked Questions`: 3 to 5 `###` questions, each with a 2 to 4 sentence answer.
- Then a `---` rule and the blog CTA from the voice guide. If there isn't one, end with a short line pointing to the video.
- Length: 1,500 to 2,500 words unless the topic needs less. Don't pad.

**Frontmatter fields:** `title`, `slug` (lowercase-hyphenated, under 60 chars), `meta_description` (150 to 160 chars), `primary_keyword`, `secondary_keywords` (3 to 5), `excerpt` (1 to 2 sentences), `tags` (3 to 7), `cover_image` (`https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg`).

**Review notes:** list what you cut from the transcript and any `[STAT NEEDED: topic]` flags. These go at the bottom of the file, after a `<!-- review notes -->` line, so they're easy to delete.

## Step 4: Write the X post

- **One line, sometimes two. Aim for under 140 characters.** The text just has to earn the click.
- One bold claim or outcome: the video's main payoff. Same energy as the title, different words.
- Add a second line only for a concrete detail (a number, a tool name) the first line can't hold.
- It reads like a take, not an announcement. Never "new video!", "I just dropped", or "in this video".
- **No link in the post.** X shows posts with links to fewer people. The link goes in a reply.
- No hashtags. No "thread". No emoji unless the voice guide says otherwise.

Also write the reply: the X reply line from the voice guide (default: "Full video here:") and then `https://youtu.be/VIDEO_ID`.

## Step 5: Write the LinkedIn post

- **Cover the video's whole premise.** If the video has 5 steps, cover all 5. Don't pick one side point.
- **Opening line (first ~150 characters):** it shows before "see more", so it must work for a stranger. Lead with a pain point, a bold claim from experience, or a surprise. No jargon yet.
- **Adapt the video's own hook.** The first 30 to 60 seconds of the transcript is usually the best hook. Rework it for LinkedIn rather than inventing a weaker one.
- **Substance (10 to 20 short lines):** each point gets at least one sentence of real insight, not just a label. One idea per line, blank lines between thoughts.
- **Point to the video:** one line saying the full video goes deeper.
- **CTA:** the LinkedIn CTA from the voice guide, if there is one.
- No link in the post body. LinkedIn shows posts with links to fewer people. The link goes in the first comment: `Full video here: https://youtu.be/VIDEO_ID`.
- Plain text only. LinkedIn doesn't render Markdown. No hashtags. No emoji unless the voice guide says otherwise.
- 1,200 to 2,000 characters. Shorter is fine if it's done.
- Don't open with "I just...", "Excited to share...", "Hot take:", or "Unpopular opinion:". No engagement bait at the end ("Agree? Let me know!").

## Rules for every piece

- **Never invent claims, stats, or stories** that aren't in the transcript. Flag gaps with `[STAT NEEDED: topic]` (blog) or leave them out.
- **Keep names exactly as spoken.** Product names, model names, versions, and tools come from the transcript, not your memory. If you're not sure a name is right, search the web to check. Never swap in a name you know better.
- **Use the creator's real examples and stories.** Don't make them generic.
- **Reorder for readers.** Spoken videos jump around. Cut filler, sponsor reads, and "like and subscribe".
- **Describe what was shown on screen** when the reader needs it to follow along.
- **Default banned words** (plus any in the voice guide): game-changer, revolutionize, unlock, supercharge, leverage, utilize, synergy, cutting-edge, elevate, empower, seamless, robust, deep dive, delve, unpack, landscape, ecosystem, paradigm, realm, harness, spearhead, streamline, "in today's...", "let's dive in", "it's important to note", "without further ado", "in conclusion", "at the end of the day". No rhetorical questions as transitions.
- If a draft could have been written by anyone, rewrite it.

## Step 6: Save the drafts

Make a folder: `<output_folder>/YYYY-MM-DD-SLUG/`. Use the video's upload date (today if unknown) and the blog slug.
Use the Write tool so special characters are safe. Write these files:

**`blog.md`**
```markdown
---
title: "TITLE"
slug: SLUG
video_id: VIDEO_ID
video_url: https://youtu.be/VIDEO_ID
date: YYYY-MM-DD
status: draft
meta_description: "..."
primary_keyword: "..."
secondary_keywords: ["...", "..."]
excerpt: "..."
tags: ["...", "..."]
cover_image: https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg
---

BLOG CONTENT

<!-- review notes -->
- Cut: ...
- [STAT NEEDED: ...]
```

**`x-post.md`**
```markdown
---
title: "TITLE"
video_id: VIDEO_ID
platform: x
status: draft
characters: 123
---

POST TEXT

=== REPLY ===
Full video here:
https://youtu.be/VIDEO_ID
```

**`linkedin.md`**
```markdown
---
title: "TITLE"
video_id: VIDEO_ID
platform: linkedin
status: draft
characters: 1450
---

POST BODY

=== FIRST COMMENT ===
Full video here: https://youtu.be/VIDEO_ID
```

**`transcript.txt`**: the raw transcript, for reference.

If the folder already has drafts for this video, ask before overwriting. In an unattended run, write new files with a `-2` suffix instead.

## Step 7: Summary

Tell the user:
- The video title and the folder path.
- The blog title and word count.
- The X post and its character count.
- The first two lines of the LinkedIn post and its character count.
- Any `[STAT NEEDED]` flags or other review notes.

Remind them these are drafts. They review, edit, and post them by hand.

## Interactive vs unattended runs

- **Interactive:** show each piece before saving. If the user says "just do it all", skip the pauses.
- **Unattended (scheduled task, `claude -p`):** don't ask questions. Use `latest-video.js`, write all drafts, then print the summary. If there's no new video or no captions yet, say so and stop. That's a normal result, not an error.

## Never

- Never post, schedule, or publish anything. Never log in to any site. This skill only writes files.
- Never print or save the Apify token.
