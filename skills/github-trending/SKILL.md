---
name: github-trending
description: Pull last-7-days + last-30-days top GitHub repos by stars PLUS fastest-growing (star velocity, 24h and 30d windows) metrics, classify AI/dev relevance, write to inbox/research/github-trending/YYYY-MM-DD-trending.md in your vault. Direct-exec (no AI in loop). Use when invoked via /github-trending, or as the GitHub source for the morning-intel brief.
---

# GitHub Trending

Mechanical fetch — no AI judgment needed. Four metrics, ranks by stars /
star-growth, flags AI/dev relevance from topics + description, writes markdown.

## The four metrics

1. **This Week** — repos `created:>7d`, sorted by stars (REST search API).
2. **This Month** — repos `created:>30d`, sorted by stars (REST search API).
3. **Fastest Growing (24h)** — top AI/dev repos by **stars gained today**, scraped from `github.com/trending?since=daily`. Catches same-day spikes.
4. **Fastest Growing (30d)** — top AI/dev repos by **stars gained this month**, scraped from `github.com/trending?since=monthly`. The durable breakouts.

Metrics 3 & 4 are the velocity pair. Unlike 1 & 2 (which filter on
`created:<date>` and so only ever see brand-new repos), they surface a repo of
**any age** that is suddenly ripping. A pure stars-sorted API query cannot do
velocity — the top of that list is all mega-repos, so a single-digit-k sleeper
never appears. The trending page is GitHub's own growth ranking.

## Output

`<VAULT>/inbox/research/github-trending/YYYY-MM-DD-trending.md` — VAULT from
`AGENTIC_OS_VAULT` in `~/.claude/.env`, default `~/the-vault`.

Sections: Top 10 This Week, Top 5 This Month, Top 10 Fastest Growing (24h),
Top 10 Fastest Growing (30d), Content Radar (AI-pick summary). Each repo block:
stars, language, created date, topics, description, `[AI/DEV]` flag. If a
scrape fails, that section degrades gracefully and the others still render.

## Manual invocation

```bash
python ~/.claude/skills/github-trending/scripts/fetch.py
```

## AI/Dev classifier

Substring match (case-insensitive) on topics OR description against:
`ai, llm, gpt, claude, anthropic, agent, mcp, prompt, embedding, rag, deepseek, kimi, gemini, openai, copilot, codex, fine-tun, transformer, ollama, langchain, chatgpt`

Not perfect — false positives on "DarkGPT"-style spam, false negatives on AI
projects with vague descriptions. Good enough for a glance.

## Rate limit

Per run: 2 Search API calls + 2 trending-page GETs + up to ~1 enrich call per
trending repo scanned (`GET /repos/{full}`). Unauthenticated Search = 10
req/min; core REST = 60/hr per IP — fine for a few runs/day, but bursty manual
re-runs can exhaust it. Set `GITHUB_TOKEN` in `~/.claude/.env` to lift both to
5000/hr.
