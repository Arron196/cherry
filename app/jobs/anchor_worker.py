from __future__ import annotations

import argparse
import logging
import os
import time

from app.services.anchoring import run_anchor_state_machine

worker_logger = logging.getLogger("app.worker.anchor_loop")


def _batch_size() -> int:
    raw_value = os.getenv("ANCHOR_WORKER_BATCH_SIZE", "100")
    try:
        parsed = int(raw_value)
    except ValueError:
        return 100
    return parsed if parsed > 0 else 1


def _poll_seconds() -> float:
    raw_value = os.getenv("WORKER_POLL_SECONDS", "5")
    try:
        parsed = float(raw_value)
    except ValueError:
        return 5.0
    return parsed if parsed > 0 else 1.0


def run_anchor_worker_once() -> int:
    return run_anchor_state_machine(limit=_batch_size())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run anchor state machine worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one anchoring pass and exit (MVP mode).",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=None,
        help="Run continuously, sleeping this many seconds between passes.",
    )
    args = parser.parse_args()

    if args.once:
        processed = run_anchor_worker_once()
        print(f"processed={processed}")
        return

    poll_seconds = (
        args.poll_seconds if args.poll_seconds is not None else _poll_seconds()
    )
    if poll_seconds < 1:
        poll_seconds = 1.0

    while True:
        try:
            processed = run_anchor_worker_once()
            print(f"processed={processed}")
        except Exception:
            worker_logger.exception("anchor worker pass failed")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
