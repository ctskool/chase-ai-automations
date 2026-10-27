---
name: morning-intel
description: The morning brief on steroids — full AI-sphere intelligence sweep (last-24h AI news via smol.ai + Hacker News, X/Twitter announcements from Anthropic/OpenAI devs, trending YouTube in the Claude Code/Codex sphere, GitHub trending 7d/30d/velocity, optional Gmail last-24h triage) synthesized into one brief ending in a "So What" section tailored to your goals. Use when the user says '/morning-intel', 'intel brief', 'AI intel sweep', 'what happened in AI in the last 24 hours', 'morning brief on steroids', or wants a combined news + inbox + action-angle briefing.
---

# morning-intel

Many thin deterministic fetchers, one synthesis pass. The fetchers are plain
Python (no AI in the loop; every failure degrades to a status flag instead of
crashing the brief); Claude does Gmail triage, X gap-fill, and the editorial
synthesis.

**First run?** If `~/.claude/skills/morning-intel/profile.md` does not exist,
the skill pack's installer hasn't run — see the repo README / CLAUDE.md.

## Step 1 — Run the fetch layer (parallel)

Run all five in parallel (independent; failures don't block each other):

```bash
python ~/.claude/skills/morning-intel/scripts/fetch_smol.py
python ~/.claude/skills/morning-intel/scripts/fetch_hn.py
python ~/.claude/skills/morning-intel/scripts/fetch_youtube.py
python ~/.claude/skills/morning-intel/scripts/fetch_github.py
python ~/.claude/skills/morning-intel/scripts/fetch_changelogs.py
```

(Windows headless/cron wrapper: `scripts/run_all.ps1` — same scripts via
Start-Job, 6min timeout, never throws. On macOS/Linux just background the five
commands with `&` + `wait`.)

Each writes `<VAULT>/inbox/research/morning-intel/cache/YYYY-MM-DD/<source>.json`
with `{status: ok|stale|error|mock, error, items}`. Always exit 0. VAULT is the
`AGENTIC_OS_VAULT` entry in `~/.claude/.env` (defaults to `~/the-vault`).
github's "items" embeds the full github-trending report (it delegates to that
skill's fetch.py, installed alongside this one).

| Source | What it covers | Fallback when status != ok |
|---|---|---|
| smol | X (544 accts) + Reddit + Discords, pre-aggregated daily | lean harder on Step 3 X searches |
| hn | front page + last-24h AI stories by points | skip section, note in status table |
| youtube | last-7d videos for 4 queries, views + views/subs outlier ratio | fall back to yt-search skill (slow) or skip |
| github | 7d/30d new repos + 24h/30d star velocity | read yesterday's github-trending file |
| changelogs | Codex changelog + Claude Code releases (raw text) | skip, note it |

## Step 2 — Gmail triage (optional, read-only, ~5 tool calls)

Requires the Gmail connector (claude.ai connectors). If unavailable, skip and
mark `gmail: unavailable` in the status table — the rest of the brief stands.

1. `search_threads` with query `newer_than:1d in:inbox`, pageSize 50.
2. Dedupe by THREAD; use the latest message date per thread (old threads with
   fresh replies match `newer_than:1d`, so classify off the newest message).
3. Snippets classify ~80% of mail. Call `get_thread` ONLY for: transactional/
   operational senders (billing, quotas, site notifications), and personalized
   inbound (a human who clearly knows the user's work).
4. Categories: **needs-reply** / **opportunity** / **newsletter-worth-reading** /
   **FYI** / **ignore**. One why-care sentence each.
5. Standing rule: quota/billing/site-breakage emails surface at the TOP of the
   brief as 🚨 operational items, above everything else.
6. Read-only. Never label, draft, archive, or click tracking links.

## Step 3 — X/Twitter gap-fill (WebSearch battery)

smol.ai covers most X discourse but lags ~1-2 days. Fill the gap with a fixed
WebSearch battery (direct x.com fetches fail with HTTP 402; Nitter is dead —
do not try them):

- `site:x.com AnthropicAI OR claudeai OR ClaudeDevs <topic keywords>`
- `site:x.com bcherny OR _catwu OR alexalbert__ claude code`
- `site:x.com sama OR gdb OR OpenAIDevs OR Codex_Changelog`
- `Anthropic OR "Claude Code" announcement news <today's date>`
- `OpenAI OR Codex announcement news <today's date>`

Snippets return tweet text but NOT engagement counts — don't invent numbers.
Date-check results: site:x.com recency ranking is unreliable, so verify a tweet
is actually fresh (snowflake-ID magnitude or corroborating dated coverage)
before presenting it as last-24h. Skip this step entirely if WebSearch is
unavailable; smol + hn still carry the news sections.

## Step 4 — Synthesize the brief

Read all cache JSONs + Gmail triage + X results + the user's
`~/.claude/skills/morning-intel/profile.md` (who they are, what formats/goals
the So What section should target), then write:

`<VAULT>/inbox/research/morning-intel/YYYY-MM-DD-intel.md`

Idempotent: re-running the same day regenerates (overwrites) the file.

Section schema (keep headings stable):

```
# Morning Intel - YYYY-MM-DD (Weekday)

## TL;DR
3-6 bullets. The single most important story first. Any 🚨 operational email
items belong here too.

## Top Story
The one dominant narrative, 1-2 paragraphs, with links + the quotable stat.

## AI News (last 24h)
Grouped: Anthropic/Claude · OpenAI/Codex · Everyone else. Source links on
every claim. Changelog deltas fold in here.

## Hacker News Pulse
Front-page reads + last-24h AI stories worth knowing (points/comments).

## YouTube Radar
Table: title, channel (subs), views, ratio. Flag outliers (ratio >= 0.3) —
those are the angles resonating. Note formula convergence (multiple channels,
same hook). Non-English videos appear despite the US region hint — lead with
English results but call out international outliers as a lane signal.

## GitHub Radar
Top new repos (7d/30d) + fastest-growing, AI-relevant picks only — pull from
the embedded github-trending report. One line each on why it matters to the
user (per profile.md).

## Inbox (last 24h)          <- only if Gmail connected
🚨 Operational first, then 💰 opportunities/needs-reply, then FYI. Ignore-tier
gets one collapsed line with count, not a listing.

## So What - Action Plan
The payoff section, driven by profile.md. For content creators: 3-5 ranked
video/post ideas with working title, hook, which findings each rides, and
timing urgency (ride-now with expiry date vs evergreen). For builders: what to
try, adopt, or watch. Angles that extend something the user already does beat
cold ones.

## Source Status
| source | status | note |
One row per source incl. gmail + x-search. Honest about failures.

_Generated at HH:MM local_
```

## Step 5 — Deliver

Chat summary: TL;DR + top story + the #1 action angle + any 🚨 inbox items.
Link the vault file. Don't paste the whole brief into chat.

## Cost + cadence notes

- YouTube: ~410 quota units/run of the 10k/day free Data API quota — fine daily, don't hammer manually.
- GitHub: unauthenticated works; set GITHUB_TOKEN in ~/.claude/.env for burst headroom.
- Reddit has NO direct free path (all routes 403) — smol.ai is the Reddit proxy. Direct Reddit would need a free Reddit script-app OAuth token (future work).
- Optional upgrade: SOCIALDATA_API_KEY (socialdata.tools, ~$0.20/1k tweets) would add real X engagement numbers for a watchlist; not wired yet.
- Keep this on a LOCAL scheduler (Task Scheduler / cron / launchd) if the Gmail step is enabled — personal inbox data shouldn't route through cloud-scheduled agents.
