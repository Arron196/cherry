from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from httpx import ASGITransport, AsyncClient

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.domain.contracts.trace_event import (
    SensorPayload,
    SignatureEnvelope,
    SupplyChainStage,
    TraceEvent,
)
from app.main import app
from app.services.signature_verification import (
    ECDSA_CANONICAL_ALGORITHM,
    normalize_signature_algorithm,
    verify_trace_event_signature_with_reason,
)


def _configure_runtime(db_path: Path, *, signature_mode: str) -> None:
    os.environ["TRACEABILITY_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["AUTH_JWT_SECRET"] = "auth-secret-compat-signature"
    os.environ["AUTH_JWT_ISSUER"] = "traceability-auth"
    os.environ["INGEST_SIGNING_KEYS"] = json.dumps({})
    os.environ["COMPAT_TELEMETRY_SIGNATURE_MODE"] = signature_mode


def _compat_telemetry_enabled() -> bool:
    paths = app.openapi().get("paths", {})
    return isinstance(paths, dict) and "/api/cherry/telemetry" in paths


def _compat_expect_routes_disabled() -> bool:
    raw = os.getenv("COMPAT_EXPECT_ROUTES_DISABLED", "0").strip()
    if raw not in {"0", "1"}:
        raise AssertionError("COMPAT_EXPECT_ROUTES_DISABLED must be '0' or '1'")
    return raw == "1"


def _assert_compat_telemetry_route_expectation() -> bool:
    expect_routes_disabled = _compat_expect_routes_disabled()
    actual_enabled = _compat_telemetry_enabled()
    assert actual_enabled is (not expect_routes_disabled), (
        "Compat route expectation mismatch for /api/cherry/telemetry: "
        f"COMPAT_EXPECT_ROUTES_DISABLED={int(expect_routes_disabled)} but route is "
        f"{'present' if actual_enabled else 'absent'} in OpenAPI"
    )
    return expect_routes_disabled


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _mint_jwt(*, subject: str, roles: list[str], issuer: str, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "iss": issuer, "roles": roles}
    encoded_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _b64url(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def _base_telemetry_payload(*, device_id: str, key_id: str) -> dict[str, Any]:
    return {
        "seq": 42,
        "ts": 1770688800,
        "temp_c": 4.2,
        "hum_rh": 71.0,
        "co2": 420.0,
        "vibration": True,
        "digest": "a1" * 32,
        "device_id": device_id,
        "batch_id": "compat-signature-batch",
        "stage": "transport",
        "key_id": key_id,
    }


def _trace_event_from_telemetry(
    payload: dict[str, Any], *, algorithm: str, signature: str
) -> TraceEvent:
    timestamp = datetime.now(UTC)
    if payload.get("ts") is not None:
        timestamp = datetime.fromtimestamp(int(payload["ts"]), tz=UTC)

    sensor_payload: dict[str, Any] = {
        "temperature_c": float(payload["temp_c"]),
        "humidity_pct": float(payload["hum_rh"]),
        "seq": int(payload["seq"]),
    }
    if payload.get("co2") is not None:
        sensor_payload["co2_ppm"] = float(payload["co2"])
    if payload.get("vibration") is not None:
        sensor_payload["vibration"] = bool(payload["vibration"])
    if payload.get("digest") is not None:
        sensor_payload["digest"] = str(payload["digest"])

    stage: SupplyChainStage = cast(
        SupplyChainStage,
        payload["stage"]
        if payload.get("stage") in {"harvest", "storage", "transport", "retail"}
        else "transport",
    )

    return TraceEvent(
        version="1.0.0",
        device_id=str(payload["device_id"]),
        batch_id=str(payload["batch_id"]),
        timestamp=timestamp,
        sensor_payload=SensorPayload.model_validate(sensor_payload),
        signature_envelope=SignatureEnvelope(
            algorithm=algorithm,
            signature=signature,
            key_id=str(payload["key_id"]),
        ),
        co2_ppm=float(payload["co2"]) if payload.get("co2") is not None else None,
        vibration_g=(
            float(payload["vibration_g"])
            if payload.get("vibration_g") is not None
            else (1.0 if payload.get("vibration") else 0.0)
        ),
        supply_chain_stage=stage,
    )


def _signing_payload(event: TraceEvent) -> dict[str, Any]:
    payload = event.model_dump(mode="json")
    envelope = payload["signature_envelope"]
    return {
        "version": payload["version"],
        "device_id": payload["device_id"],
        "batch_id": payload["batch_id"],
        "timestamp": payload["timestamp"],
        "sensor_payload": payload["sensor_payload"],
        "signature_envelope": {
            "algorithm": envelope["algorithm"],
            "key_id": envelope["key_id"],
        },
    }


def _sign_event_ecdsa(
    *,
    event: TraceEvent,
    private_key: ec.EllipticCurvePrivateKey,
    encoding: Literal["der", "raw"],
) -> str:
    canonical = canonicalize_payload(_signing_payload(event)).encode("utf-8")
    der_signature = private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
    if encoding == "der":
        return der_signature.hex()
    r_value, s_value = decode_dss_signature(der_signature)
    raw_signature = r_value.to_bytes(32, byteorder="big") + s_value.to_bytes(
        32, byteorder="big"
    )
    return raw_signature.hex()


def _event_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert row is not None
    return int(row[0])


def _latest_signature_audit(
    db_path: Path, *, device_id: str
) -> tuple[str, str, str, str, str] | None:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT json_extract(metadata, '$.result') AS result,
                   json_extract(metadata, '$.mode') AS mode,
                   json_extract(metadata, '$.reason') AS reason,
                   json_extract(metadata, '$.algorithm') AS algorithm,
                   json_extract(metadata, '$.source_algorithm') AS source_algorithm
            FROM audits
            WHERE target = ? AND action = 'ingest.signature.verify'
            ORDER BY id DESC
            LIMIT 1
            """,
            (f"device:{device_id}",),
        ).fetchone()
    if row is None:
        return None
    return (str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))


async def _register_ecdsa_key(
    *,
    client: AsyncClient,
    token: str,
    device_id: str,
    key_id: str,
    public_key_pem: str,
) -> None:
    register_response = await client.post(
        "/admin/devices",
        headers={"Authorization": f"Bearer {token}"},
        json={"device_id": device_id, "display_name": device_id},
    )
    assert register_response.status_code == 201

    rotate_response = await client.post(
        f"/admin/devices/{device_id}/keys",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "key_id": key_id,
            "algorithm": ECDSA_CANONICAL_ALGORITHM,
            "public_key": public_key_pem,
        },
    )
    assert rotate_response.status_code == 201


@pytest.mark.asyncio
async def test_compat_ingest_accepts_valid_raw_signature_in_enforce_mode(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "compat-raw-signature-enforce.db"
    _configure_runtime(db_path, signature_mode="enforce")

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    token = _mint_jwt(
        subject="admin-compat-signature",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-compat-signature",
    )

    device_id = "compat-ecdsa-device-raw"
    key_id = "compat-ecdsa-key-raw"
    payload = _base_telemetry_payload(device_id=device_id, key_id=key_id)
    unsigned_event = _trace_event_from_telemetry(
        payload,
        algorithm=ECDSA_CANONICAL_ALGORITHM,
        signature="00" * 64,
    )
    payload["signature"] = _sign_event_ecdsa(
        event=unsigned_event,
        private_key=private_key,
        encoding="raw",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register_ecdsa_key(
            client=client,
            token=token,
            device_id=device_id,
            key_id=key_id,
            public_key_pem=public_key_pem,
        )

        response = await client.post(
            "/api/cherry/telemetry",
            headers={"Idempotency-Key": "idem-compat-raw-enforce"},
            json=payload,
        )

    expect_routes_disabled = _assert_compat_telemetry_route_expectation()
    if expect_routes_disabled:
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}
    else:
        assert response.status_code == 202
        body = response.json()
        assert body["accepted"] is True
        assert body["ingest_status"] == "RECEIVED"
        assert _event_count(db_path) == 1


@pytest.mark.asyncio
async def test_compat_ingest_rejects_invalid_signature_in_enforce_mode(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "compat-invalid-signature-enforce.db"
    _configure_runtime(db_path, signature_mode="enforce")

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    token = _mint_jwt(
        subject="admin-compat-signature",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-compat-signature",
    )

    device_id = "compat-ecdsa-device-invalid"
    key_id = "compat-ecdsa-key-invalid"
    payload = _base_telemetry_payload(device_id=device_id, key_id=key_id)
    payload["signature"] = "00" * 64

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register_ecdsa_key(
            client=client,
            token=token,
            device_id=device_id,
            key_id=key_id,
            public_key_pem=public_key_pem,
        )

        response = await client.post(
            "/api/cherry/telemetry",
            headers={"Idempotency-Key": "idem-compat-invalid-enforce"},
            json=payload,
        )

    expect_routes_disabled = _assert_compat_telemetry_route_expectation()
    if expect_routes_disabled:
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}
    else:
        assert response.status_code == 401
        body = response.json()
        assert set(body) >= {"type", "title", "status", "detail", "instance"}
        assert body["status"] == 401
        assert body["instance"] == "/api/cherry/telemetry"


@pytest.mark.asyncio
async def test_compat_ingest_observe_mode_accepts_invalid_signature_and_records_reason(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "compat-invalid-signature-observe.db"
    _configure_runtime(db_path, signature_mode="observe")

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    token = _mint_jwt(
        subject="admin-compat-signature",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-compat-signature",
    )

    device_id = "compat-ecdsa-device-observe"
    key_id = "compat-ecdsa-key-observe"
    payload = _base_telemetry_payload(device_id=device_id, key_id=key_id)
    payload["signature"] = "00" * 64

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register_ecdsa_key(
            client=client,
            token=token,
            device_id=device_id,
            key_id=key_id,
            public_key_pem=public_key_pem,
        )

        response = await client.post(
            "/api/cherry/telemetry",
            headers={"Idempotency-Key": "idem-compat-invalid-observe"},
            json=payload,
        )

    expect_routes_disabled = _assert_compat_telemetry_route_expectation()
    if expect_routes_disabled:
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}
    else:
        assert response.status_code == 202
        body = response.json()
        assert body["accepted"] is True
        assert body["ingest_status"] == "RECEIVED"

        audit_row = _latest_signature_audit(db_path, device_id=device_id)
        assert audit_row is not None
        assert audit_row[0] == "observed"
        assert audit_row[1] == "observe"
        assert audit_row[2] == "signature_mismatch"
        assert audit_row[3] == ECDSA_CANONICAL_ALGORITHM
        assert audit_row[4] == "ECDSA"


def test_signature_algorithm_alias_normalization_to_canonical() -> None:
    assert normalize_signature_algorithm("ECDSA") == ECDSA_CANONICAL_ALGORITHM
    assert (
        normalize_signature_algorithm(ECDSA_CANONICAL_ALGORITHM)
        == ECDSA_CANONICAL_ALGORITHM
    )


def test_compat_telemetry_openapi_contract_shape() -> None:
    openapi = app.openapi()
    paths = openapi.get("paths", {})
    telemetry_path = paths.get("/api/cherry/telemetry")
    expect_routes_disabled = _assert_compat_telemetry_route_expectation()

    if expect_routes_disabled:
        assert telemetry_path is None
        assert "/v1/events" in paths
    else:
        assert isinstance(telemetry_path, dict)
        assert "post" in telemetry_path

        post_operation = telemetry_path["post"]
        assert isinstance(post_operation, dict)
        responses = post_operation.get("responses", {})
        assert isinstance(responses, dict)
        accepted_response = responses.get("202") or responses.get("200")
        assert isinstance(accepted_response, dict)

        content = accepted_response.get("content", {})
        assert isinstance(content, dict)
        app_json = content.get("application/json", {})
        assert isinstance(app_json, dict)
        schema = app_json.get("schema", {})
        assert isinstance(schema, dict)
        assert schema.get("$ref") == "#/components/schemas/CherryTelemetryResponse"

        components = openapi.get("components", {})
        assert isinstance(components, dict)
        schemas = components.get("schemas", {})
        assert isinstance(schemas, dict)
        telemetry_schema = schemas.get("CherryTelemetryResponse", {})
        assert isinstance(telemetry_schema, dict)
        required = telemetry_schema.get("required", [])
        assert isinstance(required, list)
        assert {"accepted", "event_id", "ingest_status"}.issubset(set(required))


@pytest.mark.asyncio
async def test_verifier_accepts_der_and_raw_ecdsa_signature_encodings(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "compat-signature-encoding-branches.db"
    _configure_runtime(db_path, signature_mode="enforce")

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    token = _mint_jwt(
        subject="admin-compat-signature",
        roles=["admin"],
        issuer="traceability-auth",
        secret="auth-secret-compat-signature",
    )

    device_id = "compat-ecdsa-device-encoding"
    key_id = "compat-ecdsa-key-encoding"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register_ecdsa_key(
            client=client,
            token=token,
            device_id=device_id,
            key_id=key_id,
            public_key_pem=public_key_pem,
        )

    base_payload = _base_telemetry_payload(device_id=device_id, key_id=key_id)

    der_event = _trace_event_from_telemetry(
        base_payload,
        algorithm=ECDSA_CANONICAL_ALGORITHM,
        signature="00" * 64,
    )
    der_event.signature_envelope.signature = _sign_event_ecdsa(
        event=der_event,
        private_key=private_key,
        encoding="der",
    )
    der_result = verify_trace_event_signature_with_reason(der_event)

    raw_alias_event = _trace_event_from_telemetry(
        base_payload,
        algorithm="ECDSA",
        signature="00" * 64,
    )
    raw_alias_event.signature_envelope.signature = _sign_event_ecdsa(
        event=raw_alias_event,
        private_key=private_key,
        encoding="raw",
    )
    raw_result = verify_trace_event_signature_with_reason(raw_alias_event)

    assert der_result.is_valid is True
    assert raw_result.is_valid is True
