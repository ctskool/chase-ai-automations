"""
run_all.py - run every metrics-pull source in parallel. Works on Windows, Mac and Linux.

    python scripts/run_all.py              # real pull
    python scripts/run_all.py --force-mock # fake numbers, to test the setup

Each source runs as its own process with a 90 second limit, so one slow or
broken source never blocks the others. Sources that aren't configured print
"skipped" and write nothing. Always exits 0, so schedulers never see a failure.
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ["pull_youtube.py", "pull_instagram.py", "pull_claude_usage.py"]
TIMEOUT_S = 90


def run(script: str, extra: list[str]) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / script), *extra],
            cwd=str(HERE), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=TIMEOUT_S,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return f"--- {script} (exit {proc.returncode}) ---\n{out.strip()}"
    except subprocess.TimeoutExpired:
        return f"--- {script} --- stopped after {TIMEOUT_S}s"
    except Exception as exc:  # noqa: BLE001
        return f"--- {script} --- could not start: {type(exc).__name__}"


def main(argv: list[str]) -> int:
    print(f"=== metrics-pull started {datetime.now().isoformat(timespec='seconds')} ===")
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        for result in pool.map(lambda s: run(s, argv), SOURCES):
            print(result)
    print(f"=== metrics-pull finished {datetime.now().isoformat(timespec='seconds')} ===")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
