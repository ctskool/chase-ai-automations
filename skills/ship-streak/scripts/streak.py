"""
streak.py - daily posting-streak tracker.

You pick the daily "tracks" in config.json (for example 1 long-form video,
2 shorts, 1 carousel). YouTube tracks fill in on their own from the YouTube
Data API. Every other track is a manual check-in.

Files (all in config.json's output_folder):
  ledger.json   the single source of truth
  streak.html   static dashboard, re-rendered on every change
  pending.json  written by `nudge` when today isn't done yet, removed when it is
  streak.log    one line per action

Commands:
  python streak.py check [--nudge]          pull YouTube, update, render (optional reminder)
  python streak.py mark <track>|freeze [--date YYYY-MM-DD] [--undo]
  python streak.py status                   one-line summary for today
  python streak.py nudge                    desktop reminder listing what's still missing
  python streak.py serve [--port N]         live dashboard with check-in buttons

Standard library only. Works on Windows, Mac and Linux.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"
ENV_FILES = [SKILL_DIR / ".env", Path.home() / ".claude" / ".env"]
YT_BASE = "https://www.googleapis.com/youtube/v3"
AUTO_SOURCES = ("youtube_longform", "youtube_shorts")
REFRESH_MINUTES = 30


# ---------------------------------------------------------------- config

def die(msg: str) -> None:
    sys.stderr.write(f"ship-streak: {msg}\n")
    raise SystemExit(2)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        die(f"no config.json at {CONFIG_PATH}. Copy config.example.json to config.json and fill it in.")
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"config.json is not valid JSON ({exc})")
    try:
        start = date.fromisoformat(cfg["start_date"])
        end = date.fromisoformat(cfg["end_date"])
    except (KeyError, ValueError):
        die("config.json needs start_date and end_date as YYYY-MM-DD")
    if end < start:
        die("end_date is before start_date")
    tracks = cfg.get("tracks") or []
    if not tracks:
        die("config.json needs at least one entry in tracks")
    seen = set()
    for t in tracks:
        tid = str(t.get("id", "")).strip()
        if not re.fullmatch(r"[a-z0-9_-]+", tid) or tid == "freeze" or tid in seen:
            die(f"track id {tid!r} must be unique, lowercase letters/digits/_/-, and not 'freeze'")
        seen.add(tid)
        t["id"] = tid
        t.setdefault("label", tid)
        t["source"] = t.get("source") or "manual"
        if t["source"] not in AUTO_SOURCES + ("manual",):
            die(f"track {tid}: source must be manual, youtube_longform or youtube_shorts")
        t["per_day"] = max(1, int(t.get("per_day") or 1))
    out = Path(os.path.expanduser(str(cfg.get("output_folder") or "output")))
    if not out.is_absolute():
        out = SKILL_DIR / out
    yt = cfg.get("youtube") or {}
    return {
        "start": start,
        "end": end,
        "tracks": tracks,
        "out": out,
        "freezes_per_month": int(cfg.get("freezes_per_month", 2)),
        "port": int(cfg.get("port") or 4630),
        "title": cfg.get("title") or "Ship streak",
        "yt_channel_id": (yt.get("channel_id") or "").strip(),
        "yt_handle": (yt.get("handle") or "").strip(),
        "shorts_max_seconds": int(yt.get("shorts_max_seconds") or 180),
    }


CFG: dict = {}


def paths() -> dict[str, Path]:
    out = CFG["out"]
    return {"ledger": out / "ledger.json", "dash": out / "streak.html",
            "marker": out / "pending.json", "log": out / "streak.log"}


def env(name: str) -> str | None:
    if val := os.environ.get(name):
        return val
    for path in ENV_FILES:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


# ---------------------------------------------------------------- helpers

def log(msg: str) -> None:
    p = paths()["log"]
    p.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)


def today() -> date:
    return datetime.now().date()


def iso(d: date) -> str:
    return d.isoformat()


def parse_duration(s: str) -> int:
    """PT1H2M3S -> seconds."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def utc_to_local_date(ts: str) -> date:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.astimezone().date()


def yt_get(endpoint: str, params: dict, key: str) -> dict:
    qs = urllib.parse.urlencode({**params, "key": key})
    req = urllib.request.Request(f"{YT_BASE}/{endpoint}?{qs}", headers={"User-Agent": "ship-streak/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def in_window(d: date) -> bool:
    return CFG["start"] <= d <= CFG["end"]


def track_ids() -> list[str]:
    return [t["id"] for t in CFG["tracks"]]


def track(tid: str) -> dict | None:
    return next((t for t in CFG["tracks"] if t["id"] == tid), None)


# ---------------------------------------------------------------- ledger

def empty_day() -> dict:
    return {"counts": {tid: 0 for tid in track_ids()}, "freeze": False, "videos": []}


def load_ledger() -> dict:
    p = paths()["ledger"]
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            p.replace(p.with_suffix(".json.bak"))
            log("ledger.json was corrupt; saved it as ledger.json.bak and started fresh")
    return {"schema_version": 2, "yt": {"status": "never", "checked": None, "error": ""}, "days": {}}


def save_ledger(ledger: dict) -> None:
    p = paths()["ledger"]
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)
    render_dashboard(ledger, static=True)


def day_of(ledger: dict, d: date) -> dict:
    day = ledger["days"].setdefault(iso(d), empty_day())
    for k, v in empty_day().items():
        day.setdefault(k, v)
    for tid in track_ids():
        day["counts"].setdefault(tid, 0)
    return day


# ---------------------------------------------------------------- scoring

def hits(day: dict) -> dict[str, bool]:
    counts = day.get("counts", {})
    return {t["id"]: counts.get(t["id"], 0) >= t["per_day"] for t in CFG["tracks"]}


def grade(day: dict) -> str:
    """green (all hit) | freeze | yellow (missed one) | red (missed more)."""
    n_hit = sum(hits(day).values())
    n = len(CFG["tracks"])
    if n_hit == n:
        return "green"
    if day.get("freeze"):
        return "freeze"
    if n >= 2 and n_hit == n - 1:
        return "yellow"
    return "red"


def freezes_used(ledger: dict, d: date) -> int:
    return sum(
        1 for k, v in ledger["days"].items()
        if v.get("freeze") and date.fromisoformat(k).replace(day=1) == d.replace(day=1) and grade(v) != "green"
    )


def freezes_left(ledger: dict, d: date) -> int:
    return max(0, CFG["freezes_per_month"] - freezes_used(ledger, d))


def streaks(ledger: dict, upto: date) -> tuple[int, int]:
    """(current, best) run of green-or-frozen days. Today doesn't break the run until it's over."""
    start = CFG["start"]
    upto = min(upto, CFG["end"])
    ok = {date.fromisoformat(k) for k, v in ledger["days"].items() if grade(v) in ("green", "freeze")}
    best = cur = 0
    d = start
    while d <= upto:
        cur = cur + 1 if d in ok else 0
        best = max(best, cur)
        d += timedelta(days=1)
    current = 0
    d = upto
    if d not in ok and d == today():
        d -= timedelta(days=1)
    while d >= start and d in ok:
        current += 1
        d -= timedelta(days=1)
    return current, best


def months() -> list[tuple[date, date]]:
    out, d = [], CFG["start"]
    while d <= CFG["end"]:
        nxt = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
        out.append((d, min(nxt - timedelta(days=1), CFG["end"])))
        d = nxt
    return out


def month_stats(ledger: dict) -> list[dict]:
    t = today()
    out = []
    for s, e in months():
        n_days = (e - s).days + 1
        counts = {tid: 0 for tid in track_ids()}
        greens = 0
        d = s
        while d <= e:
            day = ledger["days"].get(iso(d))
            if day:
                for tid in counts:
                    counts[tid] += day.get("counts", {}).get(tid, 0)
                greens += grade(day) == "green"
            d += timedelta(days=1)
        out.append({
            "name": s.strftime("%b %Y"), "start": iso(s), "end": iso(e), "days": n_days,
            "counts": counts, "goals": {t_["id"]: t_["per_day"] * n_days for t_ in CFG["tracks"]},
            "greens": greens, "active": s <= t <= e,
        })
    return out


def summary(ledger: dict) -> dict:
    t = today()
    tday = day_of(ledger, t) if in_window(t) else empty_day()
    cur, best = streaks(ledger, t)
    totals = {tid: 0 for tid in track_ids()}
    for k, v in ledger["days"].items():
        if in_window(date.fromisoformat(k)):
            for tid in totals:
                totals[tid] += v.get("counts", {}).get(tid, 0)
    total_days = (CFG["end"] - CFG["start"]).days + 1
    goal = sum(tr["per_day"] for tr in CFG["tracks"]) * total_days
    h = hits(tday)
    return {
        "today": iso(t),
        "in_window": in_window(t),
        "today_counts": tday["counts"],
        "today_hits": h,
        "today_grade": grade(tday),
        "today_videos": tday["videos"],
        "missing": [tid for tid, ok in h.items() if not ok],
        "streak": cur,
        "best": best,
        "freezes_left": freezes_left(ledger, t),
        "totals": totals,
        "total_pieces": sum(totals.values()),
        "goal_pieces": goal,
        "total_days": total_days,
        "days_elapsed": max(0, min(total_days, (t - CFG["start"]).days + 1)),
        "days_remaining": max(0, min(total_days, (CFG["end"] - t).days + 1)),
        "months": month_stats(ledger),
        "yt": ledger.get("yt", {}),
    }


# ---------------------------------------------------------------- youtube

def uses_youtube() -> bool:
    return any(t["source"] in AUTO_SOURCES for t in CFG["tracks"])


def uploads_playlist(key: str) -> str:
    params = {"part": "contentDetails"}
    if CFG["yt_channel_id"]:
        params["id"] = CFG["yt_channel_id"]
    else:
        h = CFG["yt_handle"]
        params["forHandle"] = h if h.startswith("@") else f"@{h}"
    items = yt_get("channels", params, key).get("items") or []
    if not items:
        raise LookupError("channel not found")
    pid = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not pid:
        raise LookupError("no uploads playlist")
    return pid


def pull_youtube(ledger: dict) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not uses_youtube():
        ledger["yt"] = {"status": "not_used", "checked": now, "error": ""}
        return
    key = env("YOUTUBE_API_KEY")
    if not key or not (CFG["yt_channel_id"] or CFG["yt_handle"]):
        why = "YOUTUBE_API_KEY not set" if not key else "youtube.channel_id or youtube.handle missing in config.json"
        ledger["yt"] = {"status": "error", "checked": now, "error": why}
        log(f"youtube: {why}")
        return
    start, end, t = CFG["start"], CFG["end"], today()
    try:
        pid = uploads_playlist(key)
        ids: list[str] = []
        page_token = ""
        for _ in range(40):  # up to 2,000 uploads back
            params = {"part": "contentDetails", "maxResults": 50, "playlistId": pid}
            if page_token:
                params["pageToken"] = page_token
            body = yt_get("playlistItems", params, key)
            stop = False
            for it in body.get("items") or []:
                cd = it.get("contentDetails", {})
                vid, pub = cd.get("videoId"), cd.get("videoPublishedAt")
                if not vid or not pub:
                    continue
                if utc_to_local_date(pub) < start:
                    stop = True
                    break
                ids.append(vid)
            page_token = body.get("nextPageToken") or ""
            if stop or not page_token:
                break

        found: list[dict] = []
        for i in range(0, len(ids), 50):
            body = yt_get("videos", {"part": "contentDetails,snippet", "id": ",".join(ids[i:i + 50])}, key)
            for v in body.get("items") or []:
                sn, cd = v.get("snippet", {}), v.get("contentDetails", {})
                pub = sn.get("publishedAt")
                if not pub or sn.get("liveBroadcastContent") not in (None, "none"):
                    continue  # skip live streams and upcoming premieres
                secs = parse_duration(cd.get("duration", ""))
                found.append({
                    "id": v["id"], "title": sn.get("title", ""), "seconds": secs,
                    "kind": "short" if secs <= CFG["shorts_max_seconds"] else "longform",
                    "published_local": iso(utc_to_local_date(pub)), "url": f"https://youtu.be/{v['id']}",
                })

        by_day: dict[str, list[dict]] = {}
        for v in found:
            by_day.setdefault(v["published_local"], []).append(v)
        d = start
        while d <= min(t, end):
            day = day_of(ledger, d)
            vids = sorted(by_day.get(iso(d), []), key=lambda x: x["title"])
            day["videos"] = vids
            for tr in CFG["tracks"]:
                if tr["source"] == "youtube_longform":
                    day["counts"][tr["id"]] = sum(1 for x in vids if x["kind"] == "longform")
                elif tr["source"] == "youtube_shorts":
                    day["counts"][tr["id"]] = sum(1 for x in vids if x["kind"] == "short")
            d += timedelta(days=1)
        ledger["yt"] = {"status": "ok", "checked": now, "error": ""}
        log(f"youtube: ok, {len(found)} uploads since {iso(start)}")
    except urllib.error.HTTPError as exc:
        ledger["yt"] = {"status": "error", "checked": now, "error": f"http {exc.code}"}
        log(f"youtube: http {exc.code}")
    except LookupError as exc:
        ledger["yt"] = {"status": "error", "checked": now, "error": str(exc)}
        log(f"youtube: {exc}")
    except Exception as exc:  # noqa: BLE001 - network etc.; keep the old auto values
        ledger["yt"] = {"status": "stale", "checked": now, "error": type(exc).__name__}
        log(f"youtube: stale ({type(exc).__name__})")


# ---------------------------------------------------------------- marks

def apply_mark(ledger: dict, field: str, value: bool, d: date) -> str | None:
    """Returns an error message, or None on success."""
    if not in_window(d):
        return f"{iso(d)} is outside {iso(CFG['start'])} to {iso(CFG['end'])}"
    day = day_of(ledger, d)
    if field == "freeze":
        if value and not day["freeze"] and freezes_left(ledger, d) <= 0:
            return "no freezes left this month"
        day["freeze"] = value
        return None
    tr = track(field)
    if not tr:
        return f"unknown track {field!r}. Tracks: {', '.join(track_ids())}"
    if tr["source"] != "manual":
        return f"{field} is filled in from YouTube automatically"
    day["counts"][field] = max(0, day["counts"].get(field, 0) + (1 if value else -1))
    return None


# ---------------------------------------------------------------- reminder

def missing_text(s: dict) -> list[str]:
    out = []
    for tr in CFG["tracks"]:
        have = s["today_counts"].get(tr["id"], 0)
        if have < tr["per_day"]:
            left = tr["per_day"] - have
            out.append(f"{left} {tr['label']}" if tr["per_day"] > 1 else tr["label"])
    return out


def nudge(ledger: dict) -> None:
    s = summary(ledger)
    marker = paths()["marker"]
    if not s["in_window"]:
        print("today is outside the streak window; no reminder")
        return
    missing = missing_text(s)
    if not missing:
        marker.unlink(missing_ok=True)
        notify("Ship streak: green day", f"Everything shipped. Streak {s['streak']} becomes {s['streak'] + 1} at midnight.")
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"date": s["today"], "missing": missing, "streak": s["streak"]}), encoding="utf-8")
    body = "Still missing: " + ", ".join(missing) + f". Streak on the line: {s['streak']}."
    if s["yt"].get("status") not in ("ok", "not_used"):
        body += f" (YouTube check: {s['yt'].get('status')})"
    notify("Ship streak: today's tally", body)


def notify(title: str, body: str) -> None:
    """Desktop notification on Windows, Mac or Linux. Always prints too."""
    print(f"{title}\n{body}")
    try:
        if sys.platform == "win32":
            esc = lambda x: x.replace("'", "''")  # noqa: E731
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                f"$n.BalloonTipTitle='{esc(title)}';$n.BalloonTipText='{esc(body)}';"
                "$n.Visible=$true;$n.ShowBalloonTip(20000);Start-Sleep -Seconds 21;$n.Dispose()"
            )
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        elif sys.platform == "darwin":
            q = lambda x: x.replace("\\", "\\\\").replace('"', '\\"')  # noqa: E731
            subprocess.run(["osascript", "-e", f'display notification "{q(body)}" with title "{q(title)}"'],
                           check=False, capture_output=True, timeout=10)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", title, body], check=False, capture_output=True, timeout=10)
    except Exception as exc:  # noqa: BLE001
        log(f"notification failed: {type(exc).__name__}")


# ---------------------------------------------------------------- dashboard

def dashboard_data(ledger: dict, static: bool) -> dict:
    return {
        "summary": summary(ledger),
        "days": ledger["days"],
        "grades": {k: grade(v) for k, v in ledger["days"].items()},
        "tracks": CFG["tracks"],
        "static": static,
        "start": iso(CFG["start"]),
        "end": iso(CFG["end"]),
        "title": CFG["title"],
        "port": CFG["port"],
    }


def render_dashboard(ledger: dict, static: bool) -> str:
    html = HTML.replace("__DATA__", json.dumps(dashboard_data(ledger, static)).replace("</", "<\\/"))
    if static:
        p = paths()["dash"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
    return html


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ship Streak</title>
<style>
:root{--bg:#141210;--panel:#1d1a17;--panel2:#242019;--ink:#f1e9df;--muted:#9a8f82;--line:#2e2924;
--accent:#d97757;--accent2:#f0a284;--green:#4fa36a;--yellow:#d9a441;--red:#c4553f;--freeze:#5a86b8;--empty:#2a2621;--future:#1a1714}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:15px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 18px;font-weight:600}
.hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.big{font-size:52px;font-weight:700;line-height:1;color:var(--accent2);letter-spacing:-.02em}
.lab{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
.sub{color:var(--muted);font-size:13px;margin-top:8px}
.today{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:22px}
.item{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:8px}
.item .t{font-weight:600;display:flex;justify-content:space-between;align-items:center;gap:8px}
.item.hit{border-color:rgba(79,163,106,.55)}
.dot{width:10px;height:10px;border-radius:50%;background:var(--red);display:inline-block;margin-right:6px}
.hit .dot{background:var(--green)}
.item small{color:var(--muted);font-size:12px}
.item ul{margin:0;padding-left:16px;font-size:12px;color:var(--muted)}
.btns{display:flex;gap:8px}
button{background:var(--accent);color:#1a120e;border:0;border-radius:8px;padding:8px 12px;font-weight:700;cursor:pointer;font-size:13px}
button.ghost{background:transparent;color:var(--muted);border:1px solid var(--line)}
.tag{font-size:11px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.heat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:22px;overflow-x:auto}
.grid{display:grid;grid-auto-flow:column;grid-template-rows:repeat(7,16px);gap:4px;margin-top:10px;width:max-content}
.cell{width:16px;height:16px;border-radius:3px;background:var(--empty)}
.cell.green{background:var(--green)}.cell.yellow{background:var(--yellow)}.cell.red{background:var(--red)}.cell.freeze{background:var(--freeze)}
.cell.future{background:var(--future);border:1px solid var(--line)}.cell.today{outline:2px solid var(--accent2);outline-offset:1px}
.legend{display:flex;gap:16px;font-size:12px;color:var(--muted);margin-top:12px;flex-wrap:wrap}
.legend span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:middle;background:var(--empty)}
.legend .g::before{background:var(--green)}.legend .y::before{background:var(--yellow)}.legend .r::before{background:var(--red)}.legend .f::before{background:var(--freeze)}
.months{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:22px}
.month{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.month.active{border-color:rgba(217,119,87,.6)}
.month h3{margin:0 0 4px;font-size:14px}.month .r{font-size:12px;color:var(--muted);margin-bottom:10px}
.bar{height:8px;background:var(--empty);border-radius:4px;overflow:hidden;margin:6px 0 2px}
.bar i{display:block;height:100%;background:var(--accent);border-radius:4px}
.row{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);gap:8px}
.foot{color:var(--muted);font-size:12px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
.tip{position:fixed;pointer-events:none;background:#000;color:#eee;font-size:12px;padding:6px 8px;border-radius:6px;display:none;max-width:280px;z-index:9}
.warn{background:rgba(196,85,63,.15);border:1px solid rgba(196,85,63,.5);border-radius:10px;padding:10px 14px;font-size:13px;margin-bottom:18px}
</style></head><body><div class="wrap">
<h1 id="h1"></h1>
<div id="warn"></div>
<div class="hero" id="hero"></div>
<div class="today" id="today"></div>
<div class="heat"><div class="lab">Every day</div><div class="grid" id="grid"></div>
<div class="legend"><span class="g">green: everything</span><span class="y">yellow: missed one</span><span class="r">red: missed more</span><span class="f">frozen</span><span>not yet</span></div></div>
<div class="months" id="months"></div>
<div class="foot" id="foot"></div>
</div><div class="tip" id="tip"></div>
<script>
const DATA=__DATA__;
const STATIC=DATA.static;
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function el(h){const t=document.createElement('template');t.innerHTML=h.trim();return t.content.firstChild}
function fmt(d){const [y,m,dd]=d.split('-');return new Date(+y,+m-1,+dd).toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'})}
function key(d){return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
function render(D){
 const S=D.summary,days=D.days,T=S.today,TR=D.tracks;
 document.getElementById('h1').textContent=`${D.title} · ${fmt(D.start)} to ${fmt(D.end)}`;
 const yt=S.yt||{};
 document.getElementById('warn').innerHTML=(yt.status&&!['ok','not_used'].includes(yt.status))?`<div class="warn">YouTube check: ${esc(yt.status)}${yt.error?' ('+esc(yt.error)+')':''}. YouTube counts may be behind. ${STATIC?'':'<button class="ghost" onclick="recheck()">Check again</button>'}</div>`:'';
 const totals=TR.map(t=>`${esc(t.label)} ${S.totals[t.id]||0}`).join(' · ');
 document.getElementById('hero').innerHTML=`
  <div class="card"><div class="lab">Current streak</div><div class="big">${S.streak}</div><div class="sub">best ${S.best} · ${S.freezes_left} freeze${S.freezes_left===1?'':'s'} left this month</div></div>
  <div class="card"><div class="lab">Pieces shipped</div><div class="big">${S.total_pieces}</div><div class="sub">of ${S.goal_pieces} · ${Math.round(100*S.total_pieces/Math.max(1,S.goal_pieces))}%<br>${totals}</div></div>
  <div class="card"><div class="lab">Days left</div><div class="big">${S.days_remaining}</div><div class="sub">day ${S.days_elapsed} of ${S.total_days}</div></div>`;
 const td=days[T]||{counts:{},videos:[]};
 const vids=t=>(td.videos||[]).filter(v=>t.source==='youtube_longform'?v.kind==='longform':v.kind==='short').map(v=>`<li title="${esc(v.title)}">${esc(v.title.slice(0,46))}${v.title.length>46?'…':''}</li>`).join('');
 const card=t=>{const n=(td.counts||{})[t.id]||0,need=t.per_day,hit=n>=need;
   if(t.source!=='manual'){const v=vids(t);return `<div class="item ${hit?'hit':''}"><div class="t"><span><i class="dot"></i>${esc(t.label)}</span><span class="tag">auto · ${n}/${need}</span></div>${v?`<ul>${v}</ul>`:`<small>${Math.max(0,need-n)} to go · YouTube fills this in</small>`}</div>`}
   const ctl=STATIC?`<small>${hit?'shipped':'check in from the live dashboard'}</small>`:`<div class="btns"><button onclick="mark('${t.id}',true)">Shipped one</button>${n>0?`<button class="ghost" onclick="mark('${t.id}',false)">undo</button>`:''}</div>`;
   return `<div class="item ${hit?'hit':''}"><div class="t"><span><i class="dot"></i>${esc(t.label)}</span><span class="tag">${n}/${need}</span></div>${ctl}</div>`};
 document.getElementById('today').innerHTML=S.in_window?TR.map(card).join(''):`<div class="item"><small>Today is outside the streak window.</small></div>`;
 const g=document.getElementById('grid');g.innerHTML='';
 const start=new Date(D.start+'T00:00:00'),end=new Date(D.end+'T00:00:00');
 const dow=(start.getDay()+6)%7;for(let i=0;i<dow;i++)g.appendChild(el('<div class="cell" style="visibility:hidden"></div>'));
 for(let d=new Date(start);d<=end;d.setDate(d.getDate()+1)){
   const k=key(d),day=days[k],gr=D.grades[k];let cls='cell';
   if(k>T)cls+=' future';else cls+=' '+(gr||'red');
   if(k===T)cls+=' today';
   const c=el(`<div class="${cls}"></div>`);
   const info=day?`${fmt(k)} · `+TR.map(t=>`${t.label} ${(day.counts||{})[t.id]||0}/${t.per_day}`).join(', ')+(day.freeze?' · frozen':''):fmt(k)+(k>T?' · upcoming':' · nothing logged');
   c.addEventListener('mousemove',e=>{const t=document.getElementById('tip');t.style.display='block';t.textContent=info;t.style.left=(e.clientX+12)+'px';t.style.top=(e.clientY+12)+'px'});
   c.addEventListener('mouseleave',()=>document.getElementById('tip').style.display='none');
   if(!STATIC&&k<T&&gr!=='green'&&!(day&&day.freeze)){c.style.cursor='pointer';c.title='click to spend a freeze';c.addEventListener('click',()=>mark('freeze',true,k))}
   g.appendChild(c);
 }
 const pct=(a,b)=>Math.min(100,Math.round(100*a/Math.max(1,b)));
 document.getElementById('months').innerHTML=S.months.map(m=>`<div class="month ${m.active?'active':''}"><h3>${esc(m.name)}</h3><div class="r">${m.greens} green day${m.greens===1?'':'s'} of ${m.days}</div>`+
   TR.map(t=>`<div class="row"><span>${esc(t.label)}</span><span>${m.counts[t.id]} / ${m.goals[t.id]}</span></div><div class="bar"><i style="width:${pct(m.counts[t.id],m.goals[t.id])}%"></i></div>`).join('')+`</div>`).join('');
 document.getElementById('foot').innerHTML=`<span>YouTube last checked ${yt.checked?new Date(yt.checked).toLocaleString():'never'} · ${esc(yt.status||'')}</span><span>${STATIC?'static copy · check in at http://localhost:'+D.port:'live · '+location.host}</span>`;
}
async function mark(field,value,date){
 const r=await fetch('/api/mark',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({field,value,date})});
 const j=await r.json();if(j.error){alert(j.error);return}render(j);
}
async function recheck(){const r=await fetch('/api/check',{method:'POST'});render(await r.json())}
render(DATA);
if(!STATIC){setInterval(async()=>{try{const r=await fetch('/api/state');render(await r.json())}catch(e){}},60000)}
</script></body></html>
"""


# ---------------------------------------------------------------- server

class Handler(BaseHTTPRequestHandler):
    lock = threading.Lock()

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _state(self, ledger: dict) -> bytes:
        return json.dumps(dashboard_data(ledger, static=False)).encode("utf-8")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        with self.lock:
            ledger = load_ledger()
            if path == "/api/state":
                return self._send(200, self._state(ledger))
            if path in ("/", "/index.html"):
                return self._send(200, render_dashboard(ledger, static=False).encode("utf-8"), "text/html; charset=utf-8")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except json.JSONDecodeError:
            body = {}
        with self.lock:
            ledger = load_ledger()
            if path == "/api/mark":
                try:
                    d = date.fromisoformat(body["date"]) if body.get("date") else today()
                except ValueError:
                    return self._send(400, b'{"error":"bad date"}')
                field, value = str(body.get("field", "")), bool(body.get("value", True))
                err = apply_mark(ledger, field, value, d)
                if err:
                    return self._send(409, json.dumps({"error": err}).encode("utf-8"))
                save_ledger(ledger)
                log(f"mark {field} {'+' if value else '-'} {iso(d)}")
                return self._send(200, self._state(ledger))
            if path == "/api/check":
                pull_youtube(ledger)
                save_ledger(ledger)
                return self._send(200, self._state(ledger))
        self._send(404, b"not found", "text/plain")


def serve(port: int) -> None:
    with Handler.lock:
        ledger = load_ledger()
        pull_youtube(ledger)
        save_ledger(ledger)

    def refresher():
        while True:
            time.sleep(REFRESH_MINUTES * 60)
            with Handler.lock:
                lg = load_ledger()
                pull_youtube(lg)
                save_ledger(lg)

    threading.Thread(target=refresher, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log(f"serving http://localhost:{port}")
    srv.serve_forever()


# ---------------------------------------------------------------- cli

def status_line(s: dict) -> str:
    parts = []
    for tr in CFG["tracks"]:
        n = s["today_counts"].get(tr["id"], 0)
        parts.append(f"{tr['id']} {n}/{tr['per_day']}{'✓' if n >= tr['per_day'] else '–'}")
    return (f"{s['today']}  " + "  ".join(parts) +
            f"  grade={s['today_grade']} streak={s['streak']} best={s['best']} "
            f"pieces={s['total_pieces']}/{s['goal_pieces']} yt={s['yt'].get('status')}")


def main(argv: list[str]) -> int:
    global CFG
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 1
    CFG = load_config()
    cmd, rest = argv[0], argv[1:]
    if cmd == "check":
        ledger = load_ledger()
        pull_youtube(ledger)
        save_ledger(ledger)
        if "--nudge" in rest:
            nudge(ledger)
        print(status_line(summary(ledger)))
        return 0
    if cmd == "mark":
        if not rest or rest[0].startswith("--"):
            print(f"usage: mark {'|'.join(t['id'] for t in CFG['tracks'] if t['source'] == 'manual')}|freeze "
                  "[--date YYYY-MM-DD] [--undo]")
            return 2
        try:
            d = date.fromisoformat(rest[rest.index("--date") + 1]) if "--date" in rest else today()
        except (ValueError, IndexError):
            print("--date needs YYYY-MM-DD")
            return 2
        ledger = load_ledger()
        err = apply_mark(ledger, rest[0], "--undo" not in rest, d)
        if err:
            print(err)
            return 3
        save_ledger(ledger)
        log(f"mark {rest[0]} {'-' if '--undo' in rest else '+'} {iso(d)}")
        print(status_line(summary(ledger)))
        return 0
    if cmd == "nudge":
        nudge(load_ledger())
        return 0
    if cmd == "status":
        print(status_line(summary(load_ledger())))
        return 0
    if cmd == "serve":
        port = int(rest[rest.index("--port") + 1]) if "--port" in rest else CFG["port"]
        serve(port)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
