---
name: ship-streak
description: Daily posting-streak tracker for creators. You set daily goals per platform (for example 1 long-form video, 2 shorts, 1 carousel) between a start and end date. YouTube uploads are detected automatically through the YouTube Data API; other platforms are one-tap manual check-ins. Shows a green/yellow/red heatmap dashboard on localhost and sends an evening reminder listing what's still missing. Use when the user says '/ship-streak', 'streak status', 'did I ship today', 'what's left today', 'mark carousel shipped', 'I posted a story', 'use a freeze', 'open the streak dashboard', or asks how their daily posting goals are going.
---

# Ship Streak

Track daily output goals and keep a streak.

## Settings

Read `config.json` in this skill's folder. If it's missing, tell the user to
copy `config.example.json` to `config.json`, and offer to fill it in with them.

- `start_date`, `end_date`: the streak window, `YYYY-MM-DD`.
- `output_folder`: where `ledger.json`, `streak.html`, `pending.json` and
  `streak.log` go.
- `tracks`: one entry per daily goal.
  - `id`: short name used in commands (`carousel`, `story`, ...).
  - `label`: what the dashboard shows.
  - `source`: `youtube_longform`, `youtube_shorts` or `manual`.
  - `per_day`: how many count as done.
- `youtube.channel_id` or `youtube.handle`: needed for YouTube tracks.
  `shorts_max_seconds` (default 180) splits shorts from long-form.
- `freezes_per_month`: days per month the user can excuse.
- `port`: dashboard port (default 4630).

Secret: `YOUTUBE_API_KEY` from the environment or `~/.claude/.env`. Never
write it into `config.json` or print it.

## Commands

Run from this skill's folder:

```bash
python scripts/streak.py check            # pull YouTube, update, re-render
python scripts/streak.py check --nudge    # same, plus a desktop reminder of what's missing
python scripts/streak.py status           # one line for today
python scripts/streak.py mark carousel    # +1 on a manual track (--undo, --date YYYY-MM-DD)
python scripts/streak.py mark freeze --date 2027-01-14
python scripts/streak.py serve            # live dashboard at http://localhost:4630
python scripts/streak.py nudge            # reminder only, no YouTube pull
```

When the user says something like "I posted the carousel" or "mark the
story", run `mark <track id>`. Don't edit `ledger.json` by hand. YouTube
tracks can't be marked: they come from the API. If an upload is missing, run
`check` again.

## Scoring

- **green**: every track hit its `per_day` goal.
- **yellow**: missed exactly one track.
- **red**: missed more than one.
- **freeze**: a non-green day the user excused.
- The streak counts green and frozen days in a row. Today doesn't break the
  streak until it's over.

## Gotchas

- The day boundary is the computer's local time. A 12:30am upload counts for
  the new day.
- Live streams and upcoming premieres are skipped.
- If the YouTube call fails, the old YouTube counts stay, and the dashboard
  shows a warning instead of a false red.
- Marks outside `start_date` to `end_date` are refused.
