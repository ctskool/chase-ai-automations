---
name: yt-search
description: Search YouTube and return structured video results with metadata. Use this skill whenever the user wants to search YouTube, find videos on a topic, research what's trending on YouTube, compare YouTube videos, or look up YouTube creators/channels. Triggers on phrases like "search YouTube for", "find videos about", "what videos are there on", "YouTube results for", or any request involving YouTube video discovery or research.
---

# YouTube Search

Search YouTube using yt-dlp and return structured, formatted results with engagement metrics.

## How to use

Run the search script:

```bash
python "~/.claude/skills/yt-search/scripts/search.py" <query> [--count N] [--months N] [--no-date-filter]
```

### Parameters
- `<query>` — search terms (required)
- `--count N` — number of results to return (default: 20)
- `--months N` — only show videos from the last N months (default: 6)
- `--no-date-filter` — include videos of any age

### Examples

```bash
# Basic search (top 20, last 6 months)
python "~/.claude/skills/yt-search/scripts/search.py" claude code tutorial

# Fewer results, shorter window
python "~/.claude/skills/yt-search/scripts/search.py" obsidian workflow --count 5 --months 3

# All time, no date filter
python "~/.claude/skills/yt-search/scripts/search.py" AI agents --count 10 --no-date-filter
```

## Output format

Each result includes:
- Title
- Channel name and subscriber count
- View count
- Duration
- Upload date
- Engagement ratio (views / subscribers) — higher means the video outperformed the channel's base
- Direct URL

Results are separated by dividers for easy scanning. Status messages (searching, filtering) go to stderr; the formatted results go to stdout.

## Notes

- yt-dlp must be installed (`pip install yt-dlp`)
- The script fetches 2x the requested count to compensate for date filtering
- Subscriber counts come from yt-dlp metadata and may occasionally be unavailable (shown as N/A)
