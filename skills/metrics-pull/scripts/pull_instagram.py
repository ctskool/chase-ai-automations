"""
pull_instagram.py - Instagram follower count via the official Instagram API. Optional source.

Skipped (nothing written) unless instagram.enabled is true in config.json
and INSTAGRAM_ACCESS_TOKEN is set (an Instagram API token for a professional
account). One GET to graph.instagram.com/me per run.

Status: ok | error (API call failed; writes the last known value) | mock (--force-mock).
"""

from __future__ import annotations

import json
import random
import sys
import urllib.error
import urllib.parse
import urllib.request

from _common import emit, env, last_known_value, parse_common_args, section, skipped

SOURCE = "instagram"
METRIC = "followers"
API_URL = "https://graph.instagram.com/me"


def from_api(token: str) -> tuple[int | None, str]:
    qs = urllib.parse.urlencode({"fields": "followers_count", "access_token": token})
    try:
        req = urllib.request.Request(f"{API_URL}?{qs}", headers={"User-Agent": "metrics-pull/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return None, f"ig_api_http_{exc.code}"
    except Exception as exc:  # noqa: BLE001 - type name only, never a message that could echo the URL
        return None, f"ig_api_{type(exc).__name__}"
    value = body.get("followers_count") if isinstance(body, dict) else None
    if not isinstance(value, int):
        return None, "ig_api_no_followers_count"
    return value, ""


def main(argv: list[str]) -> int:
    ts_override, force_mock = parse_common_args(argv)
    if not section("instagram").get("enabled"):
        return skipped(SOURCE, "instagram.enabled is false in config.json")

    if force_mock:
        value, status, error = 1500 + random.randint(-5, 12), "mock", ""
    else:
        token = env("INSTAGRAM_ACCESS_TOKEN")
        if not token:
            return skipped(SOURCE, "INSTAGRAM_ACCESS_TOKEN is not set")
        value, error = from_api(token)
        status = "ok"
        if value is None:
            value, status = int(last_known_value(SOURCE, METRIC)), "error"

    print(json.dumps(emit(SOURCE, METRIC, value, status, error, ts=ts_override), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
