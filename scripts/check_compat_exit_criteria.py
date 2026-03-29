from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.compat_exit import (  # noqa: E402
    COMPAT_EXIT_HISTORY_DEFAULT_PATH,
    compat_closure_requested,
    evaluate_compat_closure_decision,
)


def main() -> int:
    closure_requested = compat_closure_requested()
    history_path = os.getenv(
        "COMPAT_EXIT_HISTORY_PATH", str(COMPAT_EXIT_HISTORY_DEFAULT_PATH)
    )
    decision = evaluate_compat_closure_decision()
    evaluation = decision.evaluation

    if evaluation is None:
        result = {
            "status": "SKIP",
            "closure_requested": False,
            "history_path": history_path,
            "include_compat_router": True,
            "reason": "compatibility closure not requested",
        }
        print("COMPAT_EXIT_CRITERIA_RESULT", json.dumps(result))
        return 0

    criteria_passed = evaluation.criteria_passed
    status = "PASS" if criteria_passed else "FAIL"
    result = {
        "status": status,
        "closure_requested": closure_requested,
        "history_path": history_path,
        "include_compat_router": decision.include_compat_router,
        "criteria_passed": criteria_passed,
        "releases_observed": evaluation.releases_observed,
        "required_releases": evaluation.required_releases,
        "trailing_streak_days": evaluation.trailing_streak_days,
        "required_consecutive_days": evaluation.required_consecutive_days,
        "max_compat_ratio": evaluation.max_compat_ratio,
        "trailing_streak_dates": list(evaluation.trailing_streak_dates),
        "reasons": list(evaluation.reasons),
    }
    print("COMPAT_EXIT_CRITERIA_RESULT", json.dumps(result))
    if evaluation.reasons:
        for reason in evaluation.reasons:
            print(f"- {reason}")

    if closure_requested and not criteria_passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
