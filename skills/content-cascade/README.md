# content-cascade

A Claude Code skill that turns one YouTube video into three drafts:

- a blog post
- an X post (plus a reply with the video link)
- a LinkedIn post (plus a first comment with the video link)

It writes in your voice, from a voice guide you write once.
The drafts are saved as Markdown files in a folder you choose.

**It does not post anything.** That's on purpose. You read the drafts, fix them, and post them yourself.
If you want posting later, add your own step (for example, a script that sends `x-post.md` to a scheduler you use).

## What you need

- [Claude Code](https://docs.claude.com/en/docs/claude-code)
- [Node.js](https://nodejs.org) 18 or newer
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) on your PATH. Check with `yt-dlp --version`.
- Optional: an [Apify](https://apify.com) token. It's a backup for when yt-dlp can't get captions. It costs a little per run.

No npm install. The scripts use only what ships with Node.

## Setup

1. Copy this folder to `~/.claude/skills/content-cascade`.
   On Windows that's `C:\Users\<you>\.claude\skills\content-cascade`.
2. In that folder, copy `config.example.json` to `config.json`. Edit it:
   - `output_folder`: where drafts go. `~` means your home folder.
   - `voice_guide`: path to your voice guide. Relative paths start from the skill folder.
   - `watch_channel`: optional. Your channel, like `"@yourhandle"`. Used for "my latest video".
3. Copy `voice-guide.example.md` to `voice-guide.md`. Fill it in with how you write.
   A few real samples of your writing help the most.
4. Optional: copy `.env.example` to `.env` and add your `APIFY_API_TOKEN`.
   Or set it as a normal environment variable. Never commit `.env`.
5. Check your setup:
   ```bash
   node ~/.claude/skills/content-cascade/scripts/config.js
   ```
   It prints your settings. `voice_guide_exists` should be `true`.

## How to run it

Open Claude Code and say one of these:

- `turn this video into posts: https://youtu.be/VIDEO_ID`
- `run content cascade on my latest video` (needs `watch_channel`)
- `just the LinkedIn post for https://youtu.be/VIDEO_ID`
- `/content-cascade https://youtu.be/VIDEO_ID`

Claude gets the transcript, shows you each draft, and saves them to:

```
<output_folder>/2026-10-20-your-video-slug/
  blog.md
  x-post.md
  linkedin.md
  transcript.txt
```

If captions aren't ready yet (new uploads can take 30 to 60 minutes), it tells you and stops.

## How to schedule it

Want drafts waiting for you after every upload? Set `watch_channel`, then run it on a schedule.
Each run checks your channel and drafts the newest video that has no drafts yet.
If nothing is new, it does nothing.

Use this prompt for the scheduled task:

```
Run content-cascade on my latest video. This is an unattended run: don't ask questions, save all three drafts, then summarize.
```

**Option 1: desktop scheduled task (runs on your computer).**
In the Claude desktop app, create a scheduled task with the prompt above. Pick a time, like daily at noon.
Your computer needs to be on and the app open when it runs. This is the easiest option, since it uses your local yt-dlp and folders.

**Option 2: cloud scheduled task (runs without your computer).**
In Claude Code, run `/schedule` and create a routine with the prompt above.
Cloud runs only see files in a repo, so put this skill and your voice guide in a repo the routine uses, and set `output_folder` to a folder inside that repo.
YouTube often blocks cloud machines, so set `APIFY_API_TOKEN` in the routine's environment as a backup.

## Sample output

`x-post.md`

```markdown
---
title: "I Replaced My Morning Routine With 3 Automations"
video_id: abc123XYZ_0
platform: x
status: draft
characters: 86
---

Three small automations now do the first hour of my workday before I open my laptop.

=== REPLY ===
Full video here:
https://youtu.be/abc123XYZ_0
```

`linkedin.md` (first lines)

```
Most people automate the wrong part of their day.

They go after the big, fun projects. The real time sink is the first hour: inbox, calendar, notes.

I moved all three to automations last month. Here's what each one does...
```

## What's in the folder

| File | What it does |
| --- | --- |
| `SKILL.md` | The instructions Claude follows. |
| `config.example.json` | Settings template. Copy to `config.json`. |
| `voice-guide.example.md` | Voice guide template. Copy to `voice-guide.md`. |
| `.env.example` | Names of optional secrets. Copy to `.env`. |
| `scripts/config.js` | Loads and prints your settings. |
| `scripts/latest-video.js` | Finds your newest video without drafts. |
| `scripts/fetch-transcript-ytdlp.js` | Gets the transcript with yt-dlp. |
| `scripts/fetch-transcript-apify.js` | Optional backup transcript fetch through Apify. |
| `scripts/video-id.js` | Pulls the video ID out of a URL. |

## Troubleshooting

- **"yt-dlp is not installed"**: install it and make sure `yt-dlp --version` works in a new terminal.
- **"No captions found"**: wait for YouTube to finish captions, or set up the Apify backup. Update yt-dlp too (`yt-dlp -U`). Old versions break often.
- **Drafts don't sound like you**: add more real writing samples to your voice guide. Add the words you hate to "Words I never use".
