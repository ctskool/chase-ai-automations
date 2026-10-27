# Chase AI automations: installer instructions for Claude Code

This repo is a pack of Claude Code skills, not an app. When someone opens it
in Claude Code and says "set me up", "install", or similar, walk them through
the steps below. One step at a time, and ask before writing any file.

## 1. Pick the skills

Show the table from README.md and ask which ones they want. Most people start
with one. Each skill lives in `skills/<name>/` with its own README.md; read
that README before installing it.

`morning-intel` also needs `github-trending`, and can use `yt-search` as a
fallback. Install those with it.

## 2. Check what each one needs

Read the skill's README and check the prerequisites (Python, Node, yt-dlp).
If something is missing, say what to install and stop until it's there.

## 3. Copy the skill

Copy `skills/<name>/` to `~/.claude/skills/<name>/`. If that folder already
exists, ask before overwriting it: they may have customized it.

## 4. Fill in its settings

- If the skill has `config.example.json`, copy it to `config.json` inside the
  installed folder and fill it in with the user, one value at a time.
- If it has `.env.example`, explain each key and how to get it. Write keys to
  `~/.claude/.env` yourself when the user pastes them. Never put keys in
  `config.json`, in this repo, or in chat summaries.
- morning-intel uses `~/.claude/.env` (see `morning-intel.env.example` at the
  repo root).

## 5. Test it once

Run the skill once with the user watching. Fix anything that fails before
moving on. Anything that would send, post, or delete should be a draft.

## 6. Schedule it (optional)

Ask if they want it to run on its own, then pick with them:

- **Desktop scheduled task** (Claude desktop app, Scheduled page): for skills
  that read files on their computer. Runs while the app is open and the
  computer is awake.
- **Cloud scheduled task** (`/schedule`): for skills that only need the
  internet and connectors. Runs with the laptop closed.
- **Task Scheduler or cron**: for script-only skills that don't need Claude
  for every run (the skill's README says when that applies).

After the first scheduled run, help them read its output and run history.
