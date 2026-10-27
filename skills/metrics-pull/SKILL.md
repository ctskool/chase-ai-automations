---
name: metrics-pull
description: Pull current audience and usage numbers (YouTube subscribers, total views and latest-video views; optional Instagram followers through the official Instagram API; Claude Code token usage over the last 5 hours) and append them as rows to a metrics CSV. Each source records its own status (ok/error/mock), so one broken source never stops the others. Use when the user says '/metrics-pull', 'pull metrics', 'refresh my numbers', 'update the dashboard data', 'how many subscribers do I have now', or asks for a metric refresh. Also runs on a schedule (every 6 hours is typical).
---

# metrics-pull

Append fresh numbers to a CSV that a dashboard, spreadsheet or another skill
can read.

## Settings

Read `config.json` in this skill's folder. If it's missing, tell the user to
copy `config.example.json` to `config.json`, and offer to fill it in with them.

- `output_folder`: where `metrics.csv`, `last-pull.json` and
  `latest-video.json` go. `~` is allowed.
- `youtube.channel_id` (starts with `UC`) or `youtube.handle` (like `@name`).
- `instagram.enabled`: optional, off by default.
- `claude_usage.enabled`, `claude_usage.window_hours`: on by default.

Secrets come only from environment variables (or `~/.claude/.env`):
`YOUTUBE_API_KEY` (required), `INSTAGRAM_ACCESS_TOKEN` (optional). Never
write keys into `config.json`, and never print them.

## Run

From this skill's folder:

```bash
python scripts/run_all.py
```

This runs every source in parallel with a 90 second limit each. One source
at a time also works, e.g. `python scripts/pull_youtube.py`. Add
`--force-mock` to any command to write fake numbers and test the setup.

After the run, show the user a short table: source, metric, value, status.
If a row has status `error`, say why using its `error` field.

## Output contract

`metrics.csv` is append-only. Never rewrite or reorder it.

```
timestamp,source,metric,value,status,error
2026-10-27T18:00:02Z,youtube,subscribers,5120,ok,
2026-10-27T18:00:02Z,youtube,total_views,251880,ok,
2026-10-27T18:00:03Z,youtube,latest_video_views,1834,ok,
2026-10-27T18:00:04Z,instagram,followers,0,error,ig_api_http_401
2026-10-27T18:00:01Z,claude_code,tokens_5h,184220,ok,
```

- `timestamp`: ISO 8601 UTC with `Z`.
- `source`: `youtube`, `instagram`, `claude_code`.
- `metric`: `subscribers`, `total_views`, `latest_video_views`,
  `followers`, `tokens_5h`, `billable_5h`, `cache_read_5h`.
- `status`: `ok` (fresh) | `error` (could not pull, last known value or 0) | `mock` (fake, from
  `--force-mock`).
- `error`: a short code with no commas when status isn't `ok`.

`last-pull.json` holds `{ ts, status, error }` per source and is rewritten
every run.

Sources that aren't configured print `skipped` and write no rows.

## Sources

| Source | Needs | Notes |
|---|---|---|
| YouTube | `YOUTUBE_API_KEY` + channel ID or handle | Official Data API v3. About 3 quota units per run. |
| Instagram | `instagram.enabled: true` + `INSTAGRAM_ACCESS_TOKEN` | Official Instagram API, exact count. Professional accounts only. |
| Claude usage | nothing | Reads Claude Code's local transcripts in `~/.claude/projects`. Only works on the computer where you use Claude Code. |
