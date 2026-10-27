"""Shared helpers for the metrics-pull source scripts.

Settings come from config.json next to SKILL.md. Secrets come from
environment variables only (process env first, then the skill's own .env,
then ~/.claude/.env).
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"
ENV_FILES = [SKILL_DIR / ".env", Path.home() / ".claude" / ".env"]

CSV_HEADER = ["timestamp", "source", "metric", "value", "status", "error"]

_config: dict | None = None


# ---------------------------------------------------------------- config / env

def load_config() -> dict:
    global _config
    if _config is not None:
        return _config
    if not CONFIG_PATH.exists():
        sys.stderr.write(
            f"metrics-pull: no config.json found at {CONFIG_PATH}\n"
            "Copy config.example.json to config.json and fill it in.\n"
        )
        raise SystemExit(2)
    try:
        _config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"metrics-pull: config.json is not valid JSON ({exc})\n")
        raise SystemExit(2)
    return _config


def section(name: str) -> dict:
    value = load_config().get(name) or {}
    return value if isinstance(value, dict) else {}


def output_dir() -> Path:
    raw = load_config().get("output_folder") or "output"
    path = Path(os.path.expanduser(str(raw)))
    if not path.is_absolute():
        path = SKILL_DIR / path
    return path


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def env(name: str) -> str | None:
    if val := os.environ.get(name):
        return val
    for path in ENV_FILES:
        if val := _read_env_file(path).get(name):
            return val
    return None


# ---------------------------------------------------------------- output files

def csv_path() -> Path:
    return output_dir() / "metrics.csv"


def snapshot_path() -> Path:
    return output_dir() / "last-pull.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_csv() -> None:
    output_dir().mkdir(parents=True, exist_ok=True)
    if not csv_path().exists():
        with csv_path().open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(CSV_HEADER)


def append_row(ts: str, source: str, metric: str, value: float, status: str, error: str) -> None:
    ensure_csv()
    with csv_path().open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow([ts, source, metric, value, status, error])


def update_snapshot(source: str, ts: str, status: str, error: str) -> None:
    path = snapshot_path()
    snapshot: dict = {}
    if path.exists():
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            snapshot = {}
    snapshot[source] = {"ts": ts, "status": status, "error": error}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")


def emit(source: str, metric: str, value: float, status: str, error: str, ts: str | None = None) -> dict:
    """Write one CSV row and update the snapshot. Returns the row as a dict."""
    final_ts = ts or now_iso()
    append_row(final_ts, source, metric, value, status, error)
    update_snapshot(source, final_ts, status, error)
    return {"ts": final_ts, "source": source, "metric": metric, "value": value,
            "status": status, "error": error}


def skipped(source: str, reason: str) -> int:
    """Print a 'skipped' line and write nothing. Used when a source isn't configured."""
    print(json.dumps({"source": source, "status": "skipped", "reason": reason}))
    return 0


def parse_common_args(argv: list[str]) -> tuple[str | None, bool]:
    """Returns (ts_override, force_mock)."""
    ts_override = None
    if "--ts" in argv:
        idx = argv.index("--ts")
        if idx + 1 < len(argv):
            ts_override = argv[idx + 1]
    return ts_override, "--force-mock" in argv


def last_known_value(source: str, metric: str) -> float:
    """Most recent non-zero value for (source, metric), or 0 if none."""
    path = csv_path()
    if not path.exists():
        return 0.0
    last = 0.0
    with path.open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("source") == source and row.get("metric") == metric:
                try:
                    v = float(row.get("value", "0"))
                except ValueError:
                    continue
                if v > 0:
                    last = v
    return last

