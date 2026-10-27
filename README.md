# Chase AI automations

The Claude Code skills I actually run every day, cleaned up so you can run
them too. They come from the automations lesson in the Chase AI+ AI
Masterclass (6.3).

Each one is a normal Claude Code skill: a folder with a `SKILL.md` and a few
scripts. Your own settings go in a `config.json` you create, and your keys go
in environment variables. Nothing personal ships in this repo.

## The skills

| Skill | What it does | Needs | Good schedule |
| --- | --- | --- | --- |
| [morning-intel](skills/morning-intel) | A morning brief: AI news, X, Hacker News, YouTube and GitHub trends, your inbox, and what to do about it | Python; YouTube API key (free); Gmail connector (optional) | Every morning, desktop task |
| [lead-research](skills/lead-research) | Researches each new lead and writes a briefing before your call | Your leads in a CSV or Supabase | Every morning, desktop or cloud task |
| [content-cascade](skills/content-cascade) | Turns one YouTube video into blog, X and LinkedIn drafts in your voice | Node, yt-dlp | After each upload, desktop task |
| [outlier-radar](skills/outlier-radar) | Finds small channels in your niche whose videos are taking off | Python; YouTube API key (free) | Every 6 hours, Task Scheduler or cron |
| [metrics-pull](skills/metrics-pull) | Adds your YouTube, Instagram and Claude usage numbers to a CSV | Python; YouTube API key (free) | Every 6 hours, Task Scheduler or cron |
| [ship-streak](skills/ship-streak) | Tracks a daily posting streak with a heatmap and an evening reminder | Python; YouTube API key (optional) | Every evening, desktop task |

`github-trending` and `yt-search` are helpers that morning-intel uses. You can
also run them on their own.

## Install

The easy way: clone this repo, open it in Claude Code, and say:

> set me up

Claude follows `CLAUDE.md`: it asks which skills you want, checks what they
need, copies them, fills in the settings with you, runs each one once, and
helps you schedule it.

The manual way:

1. Copy the skill's folder from `skills/` to `~/.claude/skills/`.
2. Read that skill's README. Copy `config.example.json` to `config.json` and
   fill it in.
3. Set the keys listed in its `.env.example` as environment variables or in
   `~/.claude/.env`. (morning-intel's keys are in `morning-intel.env.example`
   at the top of this repo.)
4. Run it once in Claude Code, for example `/lead-research`.

## Scheduling

- **Desktop scheduled task** (Claude desktop app → Scheduled → New task):
  for skills that read files on your computer. Runs while the app is open
  and your computer is awake.
- **Cloud scheduled task** (`/schedule` in Claude Code): for skills that
  only need the internet and connectors. Runs with your laptop closed.
- **Task Scheduler (Windows) or cron (Mac, Linux)**: for script-only skills
  like outlier-radar and metrics-pull, which don't need Claude on every run.
  Their READMEs have the exact commands.

## Safety

- Nothing here sends, posts or deletes on its own. Drafts and reports land
  in folders for you to read.
- Keep `config.json`, `.env` and anything the skills write out of public
  repos. This repo's `.gitignore` already does that.
- Lead briefings contain personal data about real people. Keep them private.

## License

MIT
