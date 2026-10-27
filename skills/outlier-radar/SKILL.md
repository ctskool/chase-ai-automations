---
name: outlier-radar
description: Scan YouTube for recent outlier videos from small channels in a niche, for example Claude Code, AI agents or vibe coding. Searches the configured seed queries plus a self-building watchlist of small channels, scores each video against that channel's own recent uploads, and appends new outliers to a dated Markdown report. Script only, no AI in the loop, usually scheduled every 6 hours. Use when the user says '/outlier-radar', 'run the radar', 'scan for outlier videos', 'any new outliers', 'what's popping off in my niche', or asks which small channels are getting unusual views.
---

# Outlier Radar

Finds videos from small channels (200 to 100k subscribers by default),
posted in the last 7 days, that are doing much better than that channel
usually does. Two ways to qualify:

- views are at least 1.5x the median lifetime views of the channel's recent
  long-form uploads, or
- the video is under 48 hours old and getting at least 10x the channel's
  usual views per hour (early detection).

Shorts and live streams are ignored.

## Settings

Read `config.json` in this skill's folder. If it's missing, tell the user to
copy `config.example.json` to `config.json`, and offer to fill it in with them.
The most important fields:

- `output_folder`: where reports and `state.json` go.
- `seed_queries`: search terms for the niche. Each costs 100 quota units per
  run.
- `subs_min`, `subs_max`: what counts as a small channel.
- `ratio_threshold`, `fresh_velocity_threshold`: how strong an outlier must
  be.
- `relevance_language`, `region_code`: optional search filters.

Secret: `YOUTUBE_API_KEY` from the environment or `~/.claude/.env`. Never
write it into `config.json` or print it.

## Run it

From this skill's folder:

```bash
python scripts/fetch.py
```

On Windows, `scripts/run.ps1` does the same and saves a log to `logs/`.

After a manual run, read today's report (`<output_folder>/YYYY-MM-DD-outliers.md`)
and give the user the top few outliers: title, multiplier, views, channel.

## How it works

1. `search.list` for each seed query, published within the window, sorted
   by views.
2. `videos.list` and `channels.list` for stats. Keep long-form, non-live
   videos with at least `min_views` from channels inside the subscriber
   range.
3. Channel baseline = its newest 50 uploads, cached 24h. Score = views /
   median lifetime views of up to 10 recent long-form uploads that are at
   least 3 days old. Needs at least 3 such uploads.
4. Channels that produce an outlier join a watchlist (capped by
   `watchlist_max`). Their uploads are checked cheaply every run, without a
   search call.
5. New outliers (not reported in the last 30 days) are appended as a
   `## Run HH:MM` section to the day's report.

## Quota

About 600 units per run for 6 seed queries, plus 50 to 150 for stats and
baselines. Four runs a day use roughly 2,600 to 3,000 of the free 10,000
daily units. If quota runs out mid-run, the report says so and the run ends
cleanly.
