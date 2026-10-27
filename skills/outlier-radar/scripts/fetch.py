"""Outlier Radar - find recent outlier videos from small YouTube channels in a niche.

Script only, no AI in the loop. Each run:
  1. search.list per seed query (published in the last N days)       [100 units each]
  2. videos.list + channels.list for stats                           [1 unit each]
  3. Per-channel baseline from its uploads playlist (cached 24h)     [2 units each]
  4. Score: headline ratio = views / median LIFETIME views of the
     channel's recent long-form uploads. A secondary "velocity" score
     (views per hour vs the channel's usual views per hour, inflated for
     young videos) catches videos under 48h old before views pile up.
  5. Also scan a watchlist of small channels that produced an outlier
     before (their baseline fetch doubles as new-upload detection).
  6. Append NEW outliers to <output_folder>/YYYY-MM-DD-outliers.md

State (seen videos, watchlist, baseline cache): <output_folder>/state.json

Settings: config.json next to SKILL.md (see config.example.json).
Secret:   YOUTUBE_API_KEY (process env first, then the skill's .env, then ~/.claude/.env).

Run:      python scripts/fetch.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"
ENV_FILES = [SKILL_DIR / ".env", Path.home() / ".claude" / ".env"]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"ERROR: no config.json at {CONFIG_PATH}. "
              "Copy config.example.json to config.json and fill it in.")
        sys.exit(2)
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: config.json is not valid JSON ({exc})")
        sys.exit(2)


CFG = load_config()

# ---------------- Tuning (from config.json) ----------------
SEED_QUERIES = [q for q in (CFG.get("seed_queries") or []) if str(q).strip()]
RELEVANCE_LANGUAGE = CFG.get("relevance_language", "en")  # "" = any language
REGION_CODE = CFG.get("region_code", "")                  # e.g. "US"; "" = anywhere
PUBLISHED_WITHIN_DAYS = int(CFG.get("published_within_days", 7))
SEARCH_RESULTS_PER_QUERY = min(50, int(CFG.get("results_per_query", 25)))
SUBS_MAX = int(CFG.get("subs_max", 100_000))       # "smaller channel" ceiling
SUBS_MIN = int(CFG.get("subs_min", 200))           # ignore brand-new/spam channels
MIN_VIEWS = int(CFG.get("min_views", 500))         # floor before we bother scoring
RATIO_THRESHOLD = float(CFG.get("ratio_threshold", 1.5))
FRESH_VEL_HOURS = 48                               # videos younger than this can also qualify on velocity
FRESH_VEL_THRESHOLD = float(CFG.get("fresh_velocity_threshold", 10.0))
WATCHLIST_MAX = int(CFG.get("watchlist_max", 75))
REPORT_TOP_N = int(CFG.get("report_top_n", 15))    # max new outliers reported per run

# Scoring pool rules.
SHORT_FORMAT_MAX_S = 181       # <= this is treated as a Short and ignored
MIN_AGE_HOURS = 2
POOL_MIN_AGE_HOURS = 72
POOL_MAX = 10
POOL_MIN = 3
POOL_MEDIAN_MIN_VIEWS = 100

BASELINE_TTL_S = 24 * 3600     # re-fetch a channel's baseline at most daily
SEEN_RETENTION_DAYS = 30

BASE = "https://www.googleapis.com/youtube/v3"

# ---------------- Env / paths ----------------

def dotenv_get(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    for env_file in ENV_FILES:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    return None


def _output_dir() -> Path:
    path = Path(os.path.expanduser(str(CFG.get("output_folder") or "output")))
    return path if path.is_absolute() else SKILL_DIR / path


REPORT_DIR = _output_dir()
STATE_DIR = REPORT_DIR
STATE_FILE = STATE_DIR / "state.json"

units_spent = 0

# ---------------- API ----------------

class QuotaExceeded(Exception):
    pass


def api(endpoint: str, params: dict, units: int) -> dict:
    global units_spent
    key = dotenv_get("YOUTUBE_API_KEY")
    if not key:
        print("ERROR: YOUTUBE_API_KEY not set. Set it as an environment variable or in ~/.claude/.env.")
        sys.exit(1)
    qs = urllib.parse.urlencode({**params, "key": key})
    url = f"{BASE}/{endpoint}?{qs}"
    last_err: Exception = RuntimeError("unreachable")
    for attempt in range(3):
        units_spent += units
        try:
            with urllib.request.urlopen(url, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = {}
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                pass
            reason = ""
            try:
                reason = body["error"]["errors"][0]["reason"]
            except Exception:
                pass
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                raise QuotaExceeded(reason)
            if e.code == 429 or e.code >= 500:
                last_err = e
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    raise last_err


def chunks(xs: list, n: int):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]

# ---------------- Stat helpers ----------------

DUR_RE = re.compile(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def parse_duration(iso: str | None) -> int:
    m = DUR_RE.match(iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def parse_ts(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def hours_since(iso: str, now_s: float) -> float:
    return (now_s - parse_ts(iso)) / 3600.0


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def pool_record_vph(rec: dict) -> float:
    age_h = (rec["fetchedAt"] - parse_ts(rec["publishedAt"])) / 3600.0
    return (rec["viewCount"] or 0) / max(age_h, MIN_AGE_HOURS)


def compute_scores(scored: dict, pool: list[dict], now_s: float) -> dict | None:
    """Score a video against its channel's recent uploads. None = not enough history.

    Returns {"ratio", "velocity"}:
      ratio    — views / median LIFETIME views of the pool (headline metric;
                 conservative for young videos, means what it sounds like)
      velocity — current VPH / median pool lifetime-avg VPH (inflated by view
                 front-loading; used to catch < 48h videos early, and shown as
                 a secondary column). None if pool VPH is degenerate.
    """
    if scored["durationS"] <= SHORT_FORMAT_MAX_S or scored["viewCount"] is None:
        return None
    eligible = [
        r for r in pool
        if r["id"] != scored["id"]
        and hours_since(r["publishedAt"], now_s) >= POOL_MIN_AGE_HOURS
        and r["durationS"] > SHORT_FORMAT_MAX_S
        and r["viewCount"] is not None
        and not r["isLive"]
    ]
    eligible.sort(key=lambda r: parse_ts(r["publishedAt"]), reverse=True)
    eligible = eligible[:POOL_MAX]
    if len(eligible) < POOL_MIN:
        return None
    median_views = median([float(r["viewCount"]) for r in eligible])
    if median_views < POOL_MEDIAN_MIN_VIEWS:
        return None
    ratio = scored["viewCount"] / max(median_views, 1)
    age_h = hours_since(scored["publishedAt"], now_s)
    vph = scored["viewCount"] / max(age_h, MIN_AGE_HOURS)
    median_pool_vph = median([pool_record_vph(r) for r in eligible])
    velocity = vph / median_pool_vph if median_pool_vph > 0 else None
    return {"ratio": ratio, "velocity": velocity}

# ---------------- Parsers ----------------

def parse_video_item(item: dict) -> dict:
    sn = item.get("snippet", {})
    st = item.get("statistics", {})
    return {
        "id": item.get("id", ""),
        "title": sn.get("title", "?"),
        "channelId": sn.get("channelId", ""),
        "channelTitle": sn.get("channelTitle", "?"),
        "publishedAt": sn.get("publishedAt", ""),
        "durationS": parse_duration(item.get("contentDetails", {}).get("duration")),
        "viewCount": int(st["viewCount"]) if "viewCount" in st else None,
        "isLive": item.get("liveStreamingDetails") is not None
        or sn.get("liveBroadcastContent") in ("live", "upcoming"),
    }


def fetch_videos(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for batch in chunks(ids, 50):
        body = api("videos", {
            "part": "snippet,statistics,contentDetails,liveStreamingDetails",
            "id": ",".join(batch), "maxResults": "50",
        }, 1)
        for item in body.get("items", []):
            v = parse_video_item(item)
            out[v["id"]] = v
    return out


def fetch_channels(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for batch in chunks(ids, 50):
        body = api("channels", {
            "part": "statistics,contentDetails", "id": ",".join(batch),
        }, 1)
        for item in body.get("items", []):
            st = item.get("statistics", {})
            subs = None
            if not st.get("hiddenSubscriberCount") and "subscriberCount" in st:
                subs = int(st["subscriberCount"])
            out[item["id"]] = {
                "subs": subs,
                "uploads": item.get("contentDetails", {})
                .get("relatedPlaylists", {}).get("uploads"),
            }
    return out


def fetch_baseline(uploads_playlist: str, now_s: float) -> list[dict]:
    """Newest <=50 uploads with stats. Doubles as pool AND new-upload feed."""
    body = api("playlistItems", {
        "part": "contentDetails", "playlistId": uploads_playlist, "maxResults": "50",
    }, 1)
    ids = [i["contentDetails"]["videoId"] for i in body.get("items", [])
           if i.get("contentDetails", {}).get("videoId")]
    if not ids:
        return []
    vids = fetch_videos(ids[:50])
    recs = []
    for vid in ids[:50]:
        v = vids.get(vid)
        if v:
            recs.append({**v, "fetchedAt": now_s})
    return recs

# ---------------- State ----------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"seen": {}, "watchlist": {}, "baselines": {}}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")

# ---------------- Report ----------------

def fmt_count(n: int | None) -> str:
    if n is None:
        return "?"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_age(hours: float) -> str:
    return f"{hours:.0f}h" if hours < 48 else f"{hours / 24:.1f}d"


def write_report(outliers: list[dict], now: datetime, note: str | None) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{now:%Y-%m-%d}-outliers.md"
    lines = []
    if not path.exists():
        lines += [
            "---",
            f"date: {now:%Y-%m-%d}",
            "type: outlier-radar",
            "tags: [research, youtube, outliers]",
            "---",
            "",
            f"# Outlier Radar — {now:%Y-%m-%d}",
            "",
            "Recent videos from small channels (< "
            + fmt_count(SUBS_MAX)
            + f" subs) at >= {RATIO_THRESHOLD:g}x the median LIFETIME views of "
            "the channel's recent uploads (or < 48h old with >= "
            + f"{FRESH_VEL_THRESHOLD:g}x velocity). 'vel' is the VPH-ratio "
            "metric — inflated for young videos, use for early detection only.",
        ]
    lines += ["", f"## Run {now:%H:%M}", ""]
    if note:
        lines.append(f"> {note}")
        lines.append("")
    if not outliers:
        lines.append("_No new outliers this run._")
    for o in outliers:
        ratio = ">100x" if o["ratio"] > 100 else f"{o['ratio']:.1f}x"
        vel = (
            "vel ?"
            if o["velocity"] is None
            else "vel >100x" if o["velocity"] > 100 else f"vel {o['velocity']:.1f}x"
        )
        lines.append(
            f"- **[{o['title']}](https://youtu.be/{o['id']})** — **{ratio}** ({vel}) | "
            f"{fmt_count(o['viewCount'])} views in {fmt_age(o['ageH'])} | "
            f"[{o['channelTitle']}](https://www.youtube.com/channel/{o['channelId']}) "
            f"({fmt_count(o['subs'])} subs) | via {o['source']}"
        )
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path

# ---------------- Main ----------------

def main() -> None:
    if not dotenv_get("YOUTUBE_API_KEY"):
        print("ERROR: YOUTUBE_API_KEY not set. Set it as an environment variable or in ~/.claude/.env.")
        sys.exit(1)
    if not SEED_QUERIES:
        print("ERROR: seed_queries is empty in config.json. Add a few search terms for your niche.")
        sys.exit(2)
    now = datetime.now()
    now_s = time.time()
    state = load_state()
    note = None

    # Prune old seen entries / stale baseline cache.
    cutoff = now_s - SEEN_RETENTION_DAYS * 86400
    state["seen"] = {k: v for k, v in state["seen"].items() if v > cutoff}
    state["baselines"] = {
        k: v for k, v in state["baselines"].items()
        if now_s - v["fetchedAt"] < 7 * 86400
    }

    candidates: dict[str, dict] = {}  # videoId -> {video, source}

    # --- Discovery: seed-query searches ---
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=PUBLISHED_WITHIN_DAYS)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    search_ids: dict[str, str] = {}  # videoId -> seed query
    try:
        for q in SEED_QUERIES:
            body = api("search", {
                "part": "snippet", "q": q, "type": "video",
                "publishedAfter": published_after, "order": "viewCount",
                "maxResults": str(SEARCH_RESULTS_PER_QUERY),
                **({"relevanceLanguage": RELEVANCE_LANGUAGE} if RELEVANCE_LANGUAGE else {}),
                **({"regionCode": REGION_CODE} if REGION_CODE else {}),
            }, 100)
            for item in body.get("items", []):
                vid = item.get("id", {}).get("videoId")
                if vid and vid not in search_ids:
                    search_ids[vid] = q
            print(f"search '{q}': {len(body.get('items', []))} results")
    except QuotaExceeded:
        note = "Quota exhausted during search phase; partial run."
        print("WARN: quota exceeded during search")

    try:
        if search_ids:
            videos = fetch_videos(list(search_ids.keys()))
            # Pre-filter before paying for channel lookups.
            keep = [
                v for v in videos.values()
                if v["durationS"] > SHORT_FORMAT_MAX_S
                and not v["isLive"]
                and (v["viewCount"] or 0) >= MIN_VIEWS
                and hours_since(v["publishedAt"], now_s) >= MIN_AGE_HOURS
            ]
            chans = fetch_channels(list({v["channelId"] for v in keep}))
            for v in keep:
                ch = chans.get(v["channelId"])
                if ch and ch["subs"] is not None and SUBS_MIN <= ch["subs"] <= SUBS_MAX:
                    candidates[v["id"]] = {
                        "video": v, "subs": ch["subs"], "uploads": ch["uploads"],
                        "source": f'search "{search_ids[v["id"]]}"',
                    }
            print(f"candidates after filters: {len(candidates)} "
                  f"(from {len(videos)} searched)")

        # --- Watchlist scan: baseline fetch doubles as new-upload detection ---
        for ch_id, w in list(state["watchlist"].items()):
            cached = state["baselines"].get(ch_id)
            if cached and now_s - cached["fetchedAt"] < BASELINE_TTL_S:
                recs = cached["records"]
            else:
                if not w.get("uploads"):
                    continue
                recs = fetch_baseline(w["uploads"], now_s)
                state["baselines"][ch_id] = {"fetchedAt": now_s, "records": recs}
            for r in recs:
                if (
                    r["id"] not in candidates
                    and hours_since(r["publishedAt"], now_s)
                    < PUBLISHED_WITHIN_DAYS * 24
                    and r["durationS"] > SHORT_FORMAT_MAX_S
                    and not r["isLive"]
                    and (r["viewCount"] or 0) >= MIN_VIEWS
                    and hours_since(r["publishedAt"], now_s) >= MIN_AGE_HOURS
                ):
                    candidates[r["id"]] = {
                        "video": r, "subs": w.get("subs"), "uploads": w["uploads"],
                        "source": f"watchlist ({w.get('title', ch_id)})",
                    }

        # --- Score ---
        outliers: list[dict] = []
        for vid, c in candidates.items():
            v = c["video"]
            ch_id = v["channelId"]
            cached = state["baselines"].get(ch_id)
            if cached and now_s - cached["fetchedAt"] < BASELINE_TTL_S:
                pool = cached["records"]
            else:
                if not c.get("uploads"):
                    continue
                pool = fetch_baseline(c["uploads"], now_s)
                state["baselines"][ch_id] = {"fetchedAt": now_s, "records": pool}
            scores = compute_scores(v, pool, now_s)
            if scores is None:
                continue
            age_h = hours_since(v["publishedAt"], now_s)
            qualifies = scores["ratio"] >= RATIO_THRESHOLD or (
                age_h < FRESH_VEL_HOURS
                and scores["velocity"] is not None
                and scores["velocity"] >= FRESH_VEL_THRESHOLD
            )
            if qualifies:
                outliers.append({
                    **v, "ratio": scores["ratio"], "velocity": scores["velocity"],
                    "subs": c["subs"], "ageH": age_h,
                    "source": c["source"], "uploads": c.get("uploads"),
                })
    except QuotaExceeded:
        note = (note or "") + " Quota exhausted mid-scoring; partial run."
        print("WARN: quota exceeded during scoring")
        outliers = []

    # --- New vs already-reported ---
    outliers.sort(key=lambda o: o["ratio"], reverse=True)
    fresh = [o for o in outliers if o["id"] not in state["seen"]][:REPORT_TOP_N]
    for o in fresh:
        state["seen"][o["id"]] = now_s
        # Confirmed outlier -> watch that channel cheaply from now on.
        if o["channelId"] not in state["watchlist"] and o.get("uploads"):
            state["watchlist"][o["channelId"]] = {
                "title": o["channelTitle"], "subs": o["subs"],
                "uploads": o["uploads"], "addedAt": now_s,
            }
    # Evict oldest watchlist entries past the cap.
    if len(state["watchlist"]) > WATCHLIST_MAX:
        for ch_id in sorted(state["watchlist"], key=lambda k: state["watchlist"][k]["addedAt"])[
            : len(state["watchlist"]) - WATCHLIST_MAX
        ]:
            del state["watchlist"][ch_id]

    path = write_report(fresh, now, note)
    save_state(state)
    print(f"done: {len(fresh)} new outliers ({len(outliers)} total qualifying), "
          f"{units_spent} quota units, "
          f"watchlist {len(state['watchlist'])} channels")
    print(f"report: {path}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
