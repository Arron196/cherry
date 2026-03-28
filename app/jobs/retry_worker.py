from __future__ import annotations

import argparse
import os

from app.services.anchoring import run_anchor_state_machine


def _batch_size() -> int:
    raw_value = os.getenv("RETRY_WORKER_BATCH_SIZE", os.getenv("ANCHOR_WORKER_BATCH_SIZE", "100"))
    try:
        parsed = int(raw_value)
    except ValueError:
        return 100
    return parsed if parsed > 0 else 1


def run_retry_worker_once() -> int:
    return run_anchor_state_machine(limit=_batch_size())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retry/dead-letter state processing")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one retry/dead-letter processing pass and exit (MVP mode).",
    )
    args = parser.parse_args()

    if not args.once:
        raise SystemExit("Only --once mode is supported in MVP")

    processed = run_retry_worker_once()
    print(f"processed={processed}")


if __name__ == "__main__":
    main()
