# metrics-pull

Saves your current numbers to a CSV file, one row per number, every time it
runs. Run it every few hours and you get a history you can chart.

It pulls:

- **YouTube:** subscribers, total channel views, views on your newest video
- **Instagram followers** (optional, through the official Instagram API)
- **Claude Code tokens** used in the last 5 hours, read from your own
  computer

If one source fails, the others still run. Each row says whether its number
is fresh (`ok`) or couldn't be pulled (`error`, with the last known number).

## What it needs

- Python 3.10 or newer
- A free YouTube Data API key
- Optional, for Instagram: an Instagram API access token for a business or
  creator account

## Setup

1. Copy this folder to `~/.claude/skills/metrics-pull`.
2. Copy `config.example.json` to `config.json` and fill it in:
   - `output_folder`: where the CSV goes, e.g. `~/metrics`
   - `youtube.handle` (like `@yourchannel`) or `youtube.channel_id`
     (starts with `UC`). One is enough.
   - Instagram is off. To turn it on, set `instagram.enabled` to `true` and
     set `INSTAGRAM_ACCESS_TOKEN` (next step).
   - Set `claude_usage.enabled` to `false` if you don't want token numbers.
3. Set your keys as environment variables, or put them in `~/.claude/.env`.
   See `.env.example` for the names. Never put keys in `config.json`.
   - `YOUTUBE_API_KEY`: in console.cloud.google.com, make a project,
     enable "YouTube Data API v3", then create an API key under Credentials.
   - `INSTAGRAM_ACCESS_TOKEN`: optional.

## Run it

In Claude Code:

```
/metrics-pull
```

Or straight from a terminal, in the skill folder (any OS):

```
python scripts/run_all.py
```

Test your setup without calling any API:

```
python scripts/run_all.py --force-mock
```

Delete the mock rows from `metrics.csv` afterwards (they have status
`mock`).

## Schedule it

This one is script-only. It doesn't need Claude to run, so a plain
scheduler is the cheapest choice.

- **Windows Task Scheduler:** make a task that runs every 6 hours with
  program `powershell.exe` and arguments
  `-NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.claude\skills\metrics-pull\scripts\run_all.ps1"`.
  Logs go to the skill's `logs` folder.
- **Mac or Linux cron:** run `crontab -e` and add
  `0 */6 * * * cd ~/.claude/skills/metrics-pull && python3 scripts/run_all.py >> cron.log 2>&1`
- **Claude desktop scheduled task:** works too. Set the prompt to
  `/metrics-pull`. It only runs while the app is open.
- **Cloud scheduled task:** not a good fit. The CSV would be written on a
  cloud machine, not yours, and Claude usage needs your local files.

## Sample output

`metrics.csv`:

```
timestamp,source,metric,value,status,error
2026-10-27T18:00:01Z,claude_code,tokens_5h,184220,ok,
2026-10-27T18:00:01Z,claude_code,billable_5h,3912004,ok,
2026-10-27T18:00:01Z,claude_code,cache_read_5h,51230881,ok,
2026-10-27T18:00:02Z,youtube,subscribers,5120,ok,
2026-10-27T18:00:02Z,youtube,total_views,251880,ok,
2026-10-27T18:00:03Z,youtube,latest_video_views,1834,ok,
2026-10-27T18:00:04Z,instagram,followers,23410,ok,
```

## Good to know

- YouTube uses about 3 of your 10,000 free daily quota units per run.
- The Claude usage numbers come from Claude Code's local session files.
  That format isn't a public API, so a Claude Code update can break it.
  The number is a rough guide, not your official plan limit.
