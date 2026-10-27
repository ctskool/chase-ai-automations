"""
pull_claude_usage.py - Claude Code token usage over a rolling window (default 5h).

Reads the session transcripts Claude Code keeps on every machine:
  ~/.claude/projects/**/*.jsonl   (or $CLAUDE_CONFIG_DIR/projects if you set it)

No API key needed and nothing leaves your computer. The transcript format is
not a public API, so if Claude Code changes it these numbers may drop to 0.

Rows written:
  claude_code / tokens_5h       output tokens in the window
  claude_code / billable_5h     input + output + cache-creation tokens
  claude_code / cache_read_5h   cache-read tokens

The metric names keep the "_5h" suffix even if you change
claude_usage.window_hours, so charts don't break.

Skipped when claude_usage.enabled is false in config.json.
"""

from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _common import emit, parse_common_args, section, skipped

SOURCE = "claude_code"


def projects_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(os.path.expanduser(base)) if base else Path.home() / ".claude") / "projects"


def parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def scan(window_hours: float) -> tuple[int, int, int, str, str]:
    """Returns (output, billable, cache_read, status, error)."""
    root = projects_dir()
    if not root.exists():
        return 0, 0, 0, "error", "projects_dir_missing"

    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    cutoff_epoch = cutoff.timestamp()
    output = billable = cache_read = 0
    seen: set[str] = set()

    try:
        for jsonl in root.rglob("*.jsonl"):
            try:
                if jsonl.stat().st_mtime < cutoff_epoch:
                    continue  # file not touched inside the window
                with jsonl.open("r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(rec, dict):
                            continue
                        ts = parse_ts(rec.get("timestamp", ""))
                        if not ts or ts < cutoff:
                            continue
                        msg = rec.get("message") or {}
                        usage = msg.get("usage") if isinstance(msg, dict) else None
                        if not usage:
                            continue
                        # The same API response can be logged more than once; count it once.
                        key = f"{msg.get('id')}:{rec.get('requestId')}"
                        if msg.get("id") and rec.get("requestId"):
                            if key in seen:
                                continue
                            seen.add(key)
                        out = int(usage.get("output_tokens", 0) or 0)
                        inp = int(usage.get("input_tokens", 0) or 0)
                        create = int(usage.get("cache_creation_input_tokens", 0) or 0)
                        output += out
                        billable += inp + out + create
                        cache_read += int(usage.get("cache_read_input_tokens", 0) or 0)
            except OSError:
                continue
    except Exception as exc:  # noqa: BLE001
        return 0, 0, 0, "error", f"scan_{type(exc).__name__}"
    return output, billable, cache_read, "ok", ""


def main(argv: list[str]) -> int:
    ts_override, force_mock = parse_common_args(argv)
    cfg = section("claude_usage")
    if cfg.get("enabled") is False:
        return skipped(SOURCE, "claude_usage.enabled is false in config.json")
    window = float(cfg.get("window_hours") or 5)

    if force_mock:
        output = random.randint(80_000, 380_000)
        billable = output * random.randint(15, 30)
        cache_read = billable * random.randint(8, 20)
        status, error = "mock", ""
    else:
        output, billable, cache_read, status, error = scan(window)

    rows = [
        emit(SOURCE, "tokens_5h", output, status, error, ts=ts_override),
        emit(SOURCE, "billable_5h", billable, status, error, ts=ts_override),
        emit(SOURCE, "cache_read_5h", cache_read, status, error, ts=ts_override),
    ]
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
