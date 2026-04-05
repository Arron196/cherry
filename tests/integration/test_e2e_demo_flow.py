from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_demo(mode: str, tmp_path: Path) -> tuple[int, str, str, dict[str, object]]:
    db_path = tmp_path / f"e2e-{mode}.db"
    evidence_dir = tmp_path / "evidence"
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/e2e_demo.py"),
        "--mode",
        mode,
        "--db-path",
        str(db_path),
        "--evidence-dir",
        str(evidence_dir),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=PROJECT_ROOT,
    )

    summary_line = ""
    for line in completed.stdout.splitlines():
        if line.startswith("E2E_DEMO_RESULT "):
            summary_line = line
            break

    assert summary_line, f"missing machine-readable summary in output:\n{completed.stdout}"
    summary = json.loads(summary_line.partition(" ")[2])
    return completed.returncode, completed.stdout, completed.stderr, summary


def test_integration_assembly_files_exist() -> None:
    required_files = [
        PROJECT_ROOT / "Dockerfile",
        PROJECT_ROOT / "docker-compose.yml",
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / "scripts/e2e_demo.py",
        PROJECT_ROOT / "tests/integration/test_e2e_demo_flow.py",
    ]
    for path in required_files:
        assert path.exists(), f"missing required integration artifact: {path}"


@pytest.mark.parametrize(
    ("mode", "expected_status", "min_alert_total"),
    [
        ("happy", "ANCHORED", 0),
        ("degraded", "DEAD_LETTER", 1),
    ],
)
def test_e2e_demo_script_reports_machine_parseable_pass(
    mode: str,
    expected_status: str,
    min_alert_total: int,
    tmp_path: Path,
) -> None:
    returncode, stdout, stderr, summary = _run_demo(mode, tmp_path)
    assert returncode == 0, f"script failed:\nstdout:\n{stdout}\n\nstderr:\n{stderr}"

    assert summary["mode"] == mode
    assert summary["status"] == "PASS"
    assert summary["trace_ingest_status"] == expected_status
    assert int(cast(int | str, summary["alert_total"])) >= min_alert_total

    evidence_path = Path(str(summary["evidence_path"]))
    assert evidence_path.exists(), f"missing evidence artifact: {evidence_path}"
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence_payload["mode"] == mode
    assert evidence_payload["status"] == "PASS"
