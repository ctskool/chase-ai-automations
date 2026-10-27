# outlier-radar

Finds YouTube videos from small channels in your niche that are taking off.
It checks every few hours and writes what it finds to a Markdown file, one
file per day.

An "outlier" is a video doing far better than that channel's usual videos.
A 5k-subscriber channel with a video at 4x its normal views is worth a look:
the topic or the packaging is working.

## What it needs

- Python 3.10 or newer. No extra packages.
- A free YouTube Data API key.

## Setup

1. Copy this folder to `~/.claude/skills/outlier-radar`.
2. Copy `config.example.json` to `config.json` and fill it in:
   - `output_folder`: where the reports go, e.g. `~/outlier-radar`. Point it
     at a notes folder (like an Obsidian vault) if you want them there.
   - `seed_queries`: 3 to 8 search terms for your niche. The examples are
     for AI and coding. Replace them with yours.
   - `subs_min` and `subs_max`: the channel sizes you care about.
   - The rest can stay as it is.
3. Set `YOUTUBE_API_KEY` as an environment variable or put it in
   `~/.claude/.env`. See `.env.example`. In console.cloud.google.com, make
   a project, enable "YouTube Data API v3", then create an API key under
   Credentials.

## Run it

In Claude Code:

```
/outlier-radar
```

Or from a terminal, in the skill folder (any OS):

```
python scripts/fetch.py
```

## Schedule it

This one is script-only, so a plain scheduler works best. Every 6 hours is
a good default.

- **Windows Task Scheduler:** make a task that repeats every 6 hours with
  program `powershell.exe` and arguments
  `-NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.claude\skills\outlier-radar\scripts\run.ps1"`.
  Logs go to the skill's `logs` folder.
- **Mac or Linux cron** (`crontab -e`):
  `0 */6 * * * cd ~/.claude/skills/outlier-radar && python3 scripts/fetch.py >> cron.log 2>&1`
- **Claude desktop scheduled task:** set the prompt to `/outlier-radar`
  and every 6 hours. Claude then also summarizes the top finds for you. It
  runs while the app is open.
- **Cloud scheduled task:** possible, if `output_folder` is inside a repo
  the task can commit to, and the API key is set as a secret in the task's
  environment. Otherwise the reports stay on the cloud machine.

## Sample output

`~/outlier-radar/2026-10-27-outliers.md`:

```
## Run 12:00

- **[I replaced my whole dev workflow with agents](https://youtu.be/xxxxxxxxxxx)** — **4.2x** (vel 18.7x) | 38.1k views in 3.1d | [Example Dev](https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx) (12.4k subs) | via search "ai agents"
- **[MCP servers explained in 10 minutes](https://youtu.be/yyyyyyyyyyy)** — **2.1x** (vel 31.0x) | 6.2k views in 20h | [Small Builder](https://www.youtube.com/channel/UCyyyyyyyyyyyyyyyyyyyyyy) (3.1k subs) | via watchlist (Small Builder)
```

The first number is views compared with the channel's usual video. `vel`
compares views per hour. It runs high on new videos, so use it as an early
signal only.

## Good to know

- Each seed query costs 100 of your 10,000 free daily quota units per run.
  Six queries, four times a day, uses about 3,000. Other tools on the same
  key share that budget.
- `state.json` in the output folder remembers what was already reported and
  which channels are on the watchlist. Delete it to start fresh.
- Shorts (181 seconds or less) and live streams are skipped.
