from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.contracts.trace_event import TraceEvent


def test_trace_event_contract_contains_required_fields() -> None:
    event = TraceEvent.model_validate(
        {
            "version": "1.0.0",
            "device_id": "device-001",
            "batch_id": "batch-2026-02-10",
            "timestamp": "2026-02-10T02:00:00Z",
            "sensor_payload": {
                "temperature_c": 4.2,
                "humidity_pct": 73.0,
                "status": "stable",
            },
            "signature_envelope": {
                "algorithm": "ECDSA_P256_SHA256",
                "signature": "MEUCIQCFIXEDTESTSIGNATURE==",
                "key_id": "factory-key-1",
            },
        }
    )

    payload = event.model_dump(mode="json")

    assert set(payload) == {
        "version",
        "device_id",
        "batch_id",
        "timestamp",
        "sensor_payload",
        "signature_envelope",
    }
    assert payload["sensor_payload"]["temperature_c"] == pytest.approx(4.2)
    assert payload["signature_envelope"]["algorithm"] == "ECDSA_P256_SHA256"


def test_trace_event_contract_requires_signature_envelope() -> None:
    with pytest.raises(ValidationError):
        TraceEvent.model_validate(
            {
                "version": "1.0.0",
                "device_id": "device-001",
                "batch_id": "batch-2026-02-10",
                "timestamp": datetime.now(UTC).isoformat(),
                "sensor_payload": {"temperature_c": 4.2},
            }
        )
