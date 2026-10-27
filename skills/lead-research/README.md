# lead-research

Researches each new lead before you get on a call with them. For every lead
without research yet, Claude visits their website, searches the web for the
person and the company, and writes a short briefing with an opening angle for
the call.

## What it needs

- Claude Code
- Your leads, in either:
  - a CSV file (see `leads.example.csv` for the columns), or
  - a Supabase table with the same columns

## Setup

1. Copy this folder to `~/.claude/skills/lead-research`.
2. Copy `config.example.json` to `config.json` and fill it in:
   - `source`: `csv` or `supabase`
   - `csv_path` or `supabase_table`
   - `briefings_dir`: where the daily briefing file goes
   - `my_emails`: your own addresses, so your test submissions get skipped
3. Supabase only: set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` as
   environment variables. Never put them in the config file.

## Run it

In Claude Code:

```
/lead-research
```

Or research one person again:

```
/lead-research Jordan
```

## Schedule it

- **Every morning:** in the Claude desktop app, open Scheduled, click
  New task, choose this computer, and set the prompt to `/lead-research`.
  Use a desktop task if your CSV lives on your computer.
- **In the cloud:** if your leads are in Supabase, a cloud scheduled task
  works too. Add the two Supabase values as secrets in the task's
  environment.

## Sample output

```
## Jordan Example · Automate online orders, $2k-5k
jordan@examplebakery.com · examplebakery.com · arrived Oct 20

Jordan runs Example Bakery, a two-location bakery that sells custom cakes
and wholesale bread to local cafes. Their site takes no online orders; the
order page is a phone number and an email form...

Angle: Open with their phone-order bottleneck: their own form answer says it
eats their mornings, and their site has no way to order online.
```

## Privacy

Briefings contain personal data about real people. Keep `briefings_dir` and
your leads file out of any public repo.
