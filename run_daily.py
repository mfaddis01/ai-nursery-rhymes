#!/usr/bin/env python3
"""Entrypoint for the AI nursery rhyme pipeline.

Run from the repository root so the relative paths in config.env (./data,
./output, ./logs, ./upload_queue.json) resolve against the repo rather than
src/.

    python run_daily.py test      # 1 long + 2 shorts from a popular rhyme
    python run_daily.py test-ai   # same, but the rhyme comes from Claude
    python run_daily.py run       # the full daily batch, then exit
    python run_daily.py schedule  # stay resident and fire at DAILY_JOB_TIME
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent

# config.env holds the API keys and the ./-relative output paths. Nothing in
# src/ loads it, so it has to happen here before any module reads os.getenv.
load_dotenv(REPO_ROOT / "config.env")

# src/ uses flat imports between its own modules (`from rhyme_manager import
# ...`), so it has to be on the path directly rather than imported as a package.
sys.path.insert(0, str(REPO_ROOT / "src"))

for directory in ("logs", "output", "output/staging", "notifications"):
    (REPO_ROOT / directory).mkdir(parents=True, exist_ok=True)

from daily_scheduler import DailyScheduler  # noqa: E402  (needs the path setup above)

USAGE = "usage: run_daily.py {test|test-ai|run|schedule}"


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    os.chdir(REPO_ROOT)

    if mode not in {"test", "test-ai", "run", "schedule"}:
        print(USAGE, file=sys.stderr)
        return 2

    scheduler = DailyScheduler()

    if mode in {"test", "test-ai", "run"}:
        if mode == "test":
            produced = scheduler.generate_daily_videos(count=1, force_source="popular")
        elif mode == "test-ai":
            produced = scheduler.generate_daily_videos(count=1, force_source="generated")
        else:
            produced = scheduler.generate_daily_videos()

        if not produced:
            print("FAILED: no videos were generated", file=sys.stderr)
            return 1
        return 0

    if mode == "schedule":
        scheduler.start()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            scheduler.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
