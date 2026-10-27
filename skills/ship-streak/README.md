# ship-streak

A streak tracker for posting every day. You set daily goals, like one
long-form video, two shorts and one carousel. Each day turns green, yellow or
red on a heatmap. An evening reminder tells you what's still missing.

- **YouTube** counts itself. It reads your uploads through the YouTube API
  and splits them into long-form and shorts by length.
- **Everything else** (Instagram, TikTok, LinkedIn, a newsletter...) is a
  manual check-in: one click on the dashboard, or tell Claude "I posted the
  carousel".
- **Freezes** let you excuse a couple of days a month without losing the
  streak.

## What it needs

- Python 3.10 or newer. No extra packages.
- A free YouTube Data API key, only if you track YouTube.

## Setup

1. Copy this folder to `~/.claude/skills/ship-streak`.
2. Copy `config.example.json` to `config.json` and fill it in:
   - `start_date` and `end_date`: the stretch you're committing to.
   - `output_folder`: where the ledger and dashboard go, e.g.
     `~/ship-streak`.
   - `tracks`: your daily goals. Each one has an `id`, a `label`, a
     `source` (`youtube_longform`, `youtube_shorts` or `manual`) and
     `per_day`. Delete the ones you don't want.
   - `youtube.handle` (like `@yourchannel`) or `youtube.channel_id`.
3. If you track YouTube, set `YOUTUBE_API_KEY` as an environment variable or
   put it in `~/.claude/.env`. See `.env.example`. In
   console.cloud.google.com, make a project, enable "YouTube Data API v3",
   then create an API key under Credentials.

## Run it

In Claude Code:

```
/ship-streak
```

Then say things like "did I ship today?", "mark the carousel" or "use a
freeze for Tuesday".

Or from a terminal, in the skill folder (any OS):

```
python scripts/streak.py check
python scripts/streak.py mark carousel
python scripts/streak.py serve
```

`serve` opens a live dashboard at http://localhost:4630 with check-in
buttons. A read-only copy is saved as `streak.html` in your output folder
after every change.

## Schedule it

Two jobs are worth scheduling:

1. **Evening reminder (around 6pm):** `check --nudge`.
   - **Claude desktop scheduled task:** set the prompt to
     `/ship-streak check and remind me what's missing today`. You can then
     reply "mark carousel" in that chat. It runs while the app is open.
   - **Or script-only:** Task Scheduler on Windows, cron on Mac/Linux (below).
2. **Final tally (around 11:50pm):** `check`, so the day closes with the
   right YouTube counts even if you never opened the dashboard.

Script-only examples:

- **Windows Task Scheduler:** program `pythonw.exe` (no console window),
  arguments `"%USERPROFILE%\.claude\skills\ship-streak\scripts\streak.py" check --nudge`.
- **Mac or Linux cron** (`crontab -e`):

  ```
  0 18 * * *  cd ~/.claude/skills/ship-streak && python3 scripts/streak.py check --nudge
  50 23 * * * cd ~/.claude/skills/ship-streak && python3 scripts/streak.py check
  ```

  On Linux, desktop pop-ups need `notify-send`. Without it the reminder is
  only printed. Cron jobs often can't show pop-ups at all; the desktop
  scheduled task is the easier route there.

To keep the live dashboard running, start `serve` when you log in (a
Startup-folder shortcut on Windows, a Login Item on Mac). It re-checks
YouTube every 30 minutes.

A **cloud scheduled task** isn't a good fit. The ledger, the dashboard and
the reminder all live on your computer.

## Sample output

```
$ python scripts/streak.py status
2027-01-14  longform 1/1✓  shorts 1/2–  carousel 1/1✓  story 0/1–  grade=red streak=6 best=9 pieces=58/450 yt=ok

$ python scripts/streak.py check --nudge
Ship streak: today's tally
Still missing: 1 Shorts, Story. Streak on the line: 6.
```

## Good to know

- Days split at midnight on your computer's clock.
- Videos of 180 seconds or less count as shorts. Change
  `youtube.shorts_max_seconds` if you want another cutoff.
- Live streams and upcoming premieres don't count.
- Each YouTube check uses a few of your 10,000 free daily quota units.
