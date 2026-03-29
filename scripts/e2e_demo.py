from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import hmac
from httpx import ASGITransport, AsyncClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.jobs.anchor_worker import run_anchor_worker_once
from app.main import app


@dataclass(frozen=True)
class DemoCheck:
    name: str
    passed: bool
    detail: str


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite:///{db_path.resolve().as_posix()}"


def _clean_database_files(db_path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()


def _configure_runtime(mode: str, db_path: Path) -> dict[str, str]:
    anchor_mode = "success" if mode == "happy" else "failure"
    max_retries = "3" if mode == "happy" else "2"
    values = {
        "TRACEABILITY_DATABASE_URL": _sqlite_url(db_path),
        "INGEST_SIGNING_KEYS": json.dumps({"factory-key-1": "super-secret"}),
        "ANCHOR_ADAPTER": "active_mock",
        "ANCHOR_MOCK_MODE": anchor_mode,
        "ANCHOR_MAX_RETRIES": max_retries,
        "ANCHOR_ALERT_SUPPRESSION_SECONDS": "3600",
    }
    for key, value in values.items():
        os.environ[key] = value
    return values


def _sign_payload(payload: dict[str, Any], secret: str) -> str:
    signing_payload = {
        "version": payload["version"],
        "device_id": payload["device_id"],
        "batch_id": payload["batch_id"],
        "timestamp": payload["timestamp"],
        "sensor_payload": payload["sensor_payload"],
        "signature_envelope": {
            "algorithm": payload["signature_envelope"]["algorithm"],
            "key_id": payload["signature_envelope"]["key_id"],
        },
    }
    canonical = canonicalize_payload(signing_payload)
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), sha256).hexdigest()


def _build_event_payload(mode: str, batch_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": "1.0.0",
        "device_id": "device-demo-001",
        "batch_id": batch_id,
        "timestamp": "2026-02-10T12:00:00Z" if mode == "happy" else "2026-02-10T12:30:00Z",
        "sensor_payload": {
            "temperature_c": 4.2 if mode == "happy" else 7.8,
            "humidity_pct": 69.5,
            "status": "stable" if mode == "happy" else "warning",
        },
        "signature_envelope": {
            "algorithm": "HMAC_SHA256",
            "signature": "",
            "key_id": "factory-key-1",
        },
    }
    payload["signature_envelope"]["signature"] = _sign_payload(payload, "super-secret")
    return payload


def _db_ingest_status(db_path: Path, idempotency_key: str) -> str:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT ingest_status FROM ingest_requests WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
    if row is None:
        raise RuntimeError("ingest row not found for demo idempotency key")
    return str(row[0])


async def _run_api_flow(*, mode: str, batch_id: str, idempotency_key: str) -> dict[str, Any]:
    payload = _build_event_payload(mode, batch_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://demo") as client:
        ingest_response = await client.post(
            "/v1/events",
            headers={"Idempotency-Key": idempotency_key},
            json=payload,
        )
        ingest_body = ingest_response.json()
        if ingest_response.status_code != 202:
            raise RuntimeError(
                f"ingest failed status={ingest_response.status_code} body={ingest_body}"
            )

        worker_runs = 1 if mode == "happy" else 2
        total_processed = 0
        for _ in range(worker_runs):
            total_processed += run_anchor_worker_once()

        trace_response = await client.get(f"/v1/trace/{batch_id}")
        trace_body = trace_response.json()
        if trace_response.status_code != 200:
            raise RuntimeError(
                f"trace query failed status={trace_response.status_code} body={trace_body}"
            )

    return {
        "ingest": ingest_body,
        "trace": trace_body,
        "worker_processed_total": total_processed,
    }


def _evaluate(
    *,
    mode: str,
    flow_result: dict[str, Any],
    db_path: Path,
    idempotency_key: str,
) -> tuple[list[DemoCheck], dict[str, Any]]:
    trace_timeline = flow_result["trace"]["timeline"]
    if not trace_timeline:
        raise RuntimeError("trace timeline is empty")

    entry = trace_timeline[0]
    expected_status = "ANCHORED" if mode == "happy" else "DEAD_LETTER"
    min_alert_total = 0 if mode == "happy" else 1
    status_from_db = _db_ingest_status(db_path, idempotency_key)

    checks = [
        DemoCheck(
            name="ingest_status_matches_mode",
            passed=entry["ingest_status"] == expected_status,
            detail=f"expected={expected_status} actual={entry['ingest_status']}",
        ),
        DemoCheck(
            name="db_status_matches_trace",
            passed=status_from_db == entry["ingest_status"],
            detail=f"db={status_from_db} trace={entry['ingest_status']}",
        ),
        DemoCheck(
            name="degraded_alert_visibility",
            passed=int(entry["alert_snapshot"]["total"]) >= min_alert_total,
            detail=(
                f"minimum={min_alert_total} actual={entry['alert_snapshot']['total']}"
            ),
        ),
        DemoCheck(
            name="worker_processed_requests",
            passed=int(flow_result["worker_processed_total"]) >= 1,
            detail=f"processed_total={flow_result['worker_processed_total']}",
        ),
    ]

    summary = {
        "mode": mode,
        "trace_ingest_status": entry["ingest_status"],
        "alert_total": entry["alert_snapshot"]["total"],
        "event_id": entry["event_id"],
        "worker_processed_total": flow_result["worker_processed_total"],
    }
    return checks, summary


def _write_evidence(
    *,
    evidence_dir: Path,
    mode: str,
    status: str,
    checks: list[DemoCheck],
    runtime: dict[str, str],
    flow_result: dict[str, Any],
    summary: dict[str, Any],
) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    evidence_path = evidence_dir / f"e2e_demo_{mode}_{timestamp}.json"
    evidence_payload = {
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "mode": mode,
        "status": status,
        "checks": [asdict(check) for check in checks],
        "runtime": runtime,
        "flow": flow_result,
        "summary": summary,
    }
    evidence_path.write_text(
        json.dumps(evidence_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return evidence_path


def _print_summary(payload: dict[str, Any]) -> None:
    print(f"E2E_DEMO_RESULT {json.dumps(payload, sort_keys=True)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic E2E MVP demo flow")
    parser.add_argument("--mode", choices=["happy", "degraded"], required=True)
    parser.add_argument("--db-path", default=None, help="SQLite database file path")
    parser.add_argument(
        "--evidence-dir",
        default=str(PROJECT_ROOT / ".sisyphus" / "evidence"),
        help="Directory where demo evidence json is written",
    )
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir)
    db_path = (
        Path(args.db_path)
        if args.db_path is not None
        else evidence_dir / f"e2e_demo_{args.mode}.db"
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _clean_database_files(db_path)

    batch_id = f"batch-demo-{args.mode}-001"
    idempotency_key = f"idem-demo-{args.mode}-001"
    runtime = _configure_runtime(args.mode, db_path)

    evidence_path: Path | None = None
    try:
        flow_result = asyncio.run(
            _run_api_flow(mode=args.mode, batch_id=batch_id, idempotency_key=idempotency_key)
        )
        checks, summary = _evaluate(
            mode=args.mode,
            flow_result=flow_result,
            db_path=db_path,
            idempotency_key=idempotency_key,
        )
        overall_pass = all(check.passed for check in checks)
        status = "PASS" if overall_pass else "FAIL"
        evidence_path = _write_evidence(
            evidence_dir=evidence_dir,
            mode=args.mode,
            status=status,
            checks=checks,
            runtime=runtime,
            flow_result=flow_result,
            summary=summary,
        )
        summary_payload = {
            "mode": args.mode,
            "status": status,
            "trace_ingest_status": summary["trace_ingest_status"],
            "alert_total": summary["alert_total"],
            "worker_processed_total": summary["worker_processed_total"],
            "evidence_path": str(evidence_path),
        }
        _print_summary(summary_payload)
        return 0 if overall_pass else 1
    except Exception as exc:  # noqa: BLE001 - CLI must always return parseable failure output.
        summary_payload = {
            "mode": args.mode,
            "status": "FAIL",
            "error": str(exc),
            "evidence_path": str(evidence_path) if evidence_path is not None else "",
        }
        _print_summary(summary_payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
