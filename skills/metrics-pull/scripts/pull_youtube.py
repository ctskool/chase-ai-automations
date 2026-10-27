"""
pull_youtube.py - YouTube channel stats via the official YouTube Data API v3.

Needs:
  YOUTUBE_API_KEY             environment variable
  youtube.channel_id          in config.json (starts with UC...), or
  youtube.handle              in config.json (e.g. @yourchannel)

Writes three rows per run:
  youtube / subscribers
  youtube / total_views          (lifetime channel views)
  youtube / latest_video_views   (views on your newest upload)

Also writes latest-video.json (title, url, views, likes, comments) to the
output folder.

Flags: --force-mock (fake numbers, for testing), --ts <ISO timestamp>.
"""

from __future__ import annotations

import json
import random
import sys
import urllib.error
import urllib.parse
import urllib.request

from _common import emit, env, last_known_value, now_iso, output_dir, parse_common_args, section

SOURCE = "youtube"
BASE = "https://www.googleapis.com/youtube/v3"
UA = {"User-Agent": "metrics-pull/1.0"}


def _get(endpoint: str, params: dict, api_key: str) -> dict:
    qs = urllib.parse.urlencode({**params, "key": api_key})
    req = urllib.request.Request(f"{BASE}/{endpoint}?{qs}", headers=UA)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _err(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"yt_http_{exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "yt_network"
    return f"yt_{type(exc).__name__}"


def fetch_channel(api_key: str, channel_id: str, handle: str) -> dict:
    params = {"part": "statistics,contentDetails"}
    if channel_id:
        params["id"] = channel_id
    else:
        params["forHandle"] = handle if handle.startswith("@") else f"@{handle}"
    items = _get("channels", params, api_key).get("items") or []
    if not items:
        raise LookupError("channel_not_found")
    item = items[0]
    stats = item.get("statistics", {})
    return {
        "subscribers": int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "uploads": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
    }


def fetch_latest_video(api_key: str, uploads: str) -> dict:
    items = _get("playlistItems", {"part": "snippet,contentDetails", "maxResults": 1,
                                   "playlistId": uploads}, api_key).get("items") or []
    if not items:
        raise LookupError("no_uploads")
    details, snippet = items[0].get("contentDetails", {}), items[0].get("snippet", {})
    video_id = details.get("videoId")
    if not video_id:
        raise LookupError("no_video_id")
    vitems = _get("videos", {"part": "statistics", "id": video_id}, api_key).get("items") or []
    if not vitems:
        raise LookupError("video_not_found")
    stats = vitems[0].get("statistics", {})
    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "url": f"https://youtu.be/{video_id}",
        "published_at": details.get("videoPublishedAt") or snippet.get("publishedAt", ""),
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
    }


def write_latest_video(data: dict, status: str, error: str, ts: str) -> None:
    out = output_dir()
    out.mkdir(parents=True, exist_ok=True)
    payload = {**data, "ts": ts, "status": status, "error": error}
    (out / "latest-video.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str]) -> int:
    ts_override, force_mock = parse_common_args(argv)
    ts = ts_override or now_iso()
    cfg = section("youtube")
    channel_id = (cfg.get("channel_id") or "").strip()
    handle = (cfg.get("handle") or "").strip()
    api_key = env("YOUTUBE_API_KEY")

    if force_mock:
        values = {"subscribers": 5000 + random.randint(0, 50), "total_views": 250_000 + random.randint(0, 5000)}
        latest = {"video_id": "mock", "title": "Mock video", "url": "", "published_at": ts,
                  "views": 1200 + random.randint(0, 200), "likes": 80, "comments": 12}
        status = lv_status = "mock"
        error = lv_error = ""
    elif not api_key or not (channel_id or handle):
        reason = "missing_youtube_api_key" if not api_key else "missing_channel_in_config"
        values, latest, status, error, lv_status, lv_error = {}, {}, "error", reason, "error", reason
    else:
        try:
            channel = fetch_channel(api_key, channel_id, handle)
            values, status, error = channel, "ok", ""
        except Exception as exc:  # noqa: BLE001 - one bad source must not crash the run
            channel, values, status = {}, {}, "error"
            error = str(exc) if isinstance(exc, LookupError) else _err(exc)
        latest, lv_status, lv_error = {}, status, error
        if channel.get("uploads"):
            try:
                latest, lv_status, lv_error = fetch_latest_video(api_key, channel["uploads"]), "ok", ""
            except Exception as exc:  # noqa: BLE001
                lv_status = "error"
                lv_error = str(exc) if isinstance(exc, LookupError) else _err(exc)

    rows = []
    for metric in ("subscribers", "total_views"):
        value = values.get(metric, last_known_value(SOURCE, metric))
        rows.append(emit(SOURCE, metric, value, status, error, ts=ts))
    write_latest_video(latest, lv_status, lv_error, ts)
    lv_value = latest.get("views", last_known_value(SOURCE, "latest_video_views"))
    rows.append(emit(SOURCE, "latest_video_views", lv_value, lv_status, lv_error, ts=ts))

    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
