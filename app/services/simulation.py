from __future__ import annotations

import hmac
import math
import random
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.contracts.hash_canonicalization import canonicalize_payload
from app.domain.contracts.trace_event import TraceEvent
from app.domain.persistence.models import (
    AnchorReceipt,
    Event,
    IngestRequest,
    ManagedDevice,
    ManagedDeviceKey,
    QualityResult,
)
from app.domain.quality.grading import grade_quality
from app.services.alerts import create_alert
from app.services.anchoring import run_anchor_state_machine
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)
from app.services.idempotency import ingest_trace_event
from app.services.signature_verification import verify_trace_event_signature_with_reason


SIMULATION_BATCH_ID_PATTERN = re.compile(r"^batch-sim-\d+$")
SIMULATION_DEVICE_ID_PATTERN = re.compile(r"^dev-sim-(\d+)$")
DEFAULT_SIMULATION_EVENT_COUNT = 8
SIMULATION_QUALITY_CHECK_NAME = "simulation.auto_grade"
DEFAULT_GENERATOR_INTERVAL_SECONDS = 5.0
DEFAULT_GENERATOR_BATCHES_PER_TICK = 4
DEFAULT_GENERATOR_MAX_DEVICE_COUNT = 24


class SimulationBatchNotSupportedError(ValueError):
    """Raised when a requested batch id is outside the simulation namespace."""


@dataclass(frozen=True)
class SimulationBatchResult:
    batch_id: str
    total_events: int
    created_events: int
    existing_events: int
    anchored_events: int
    processed_anchoring: int


@dataclass(frozen=True)
class SimulationTickResult:
    generated_events: int
    processed_anchoring: int
    alerts_created: int
    active_batches: list[str]


@dataclass(frozen=True)
class SimulationGeneratorStatus:
    running: bool
    interval_seconds: float
    batches_per_tick: int
    generated_events: int
    generated_alerts: int
    active_batches: list[str]
    started_at: str | None
    last_tick_at: str | None
    last_error: str | None


@dataclass
class _SimulationGeneratorRuntime:
    lock: threading.Lock
    stop_event: threading.Event
    thread: threading.Thread | None = None
    interval_seconds: float = DEFAULT_GENERATOR_INTERVAL_SECONDS
    batches_per_tick: int = DEFAULT_GENERATOR_BATCHES_PER_TICK
    generated_events: int = 0
    generated_alerts: int = 0
    sequence: int = 0
    active_batches: list[str] | None = None
    started_at: datetime | None = None
    last_tick_at: datetime | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class _SimulationDevice:
    device_id: str
    display_name: str
    key_id: str
    secret: str


_SIMULATION_DEVICES = [
    _SimulationDevice(
        device_id="dev-sim-1",
        display_name="采摘端温湿度节点",
        key_id="dev-sim-1-key-active",
        secret="simulation-secret-dev-sim-1",
    ),
    _SimulationDevice(
        device_id="dev-sim-2",
        display_name="冷链车厢网关",
        key_id="dev-sim-2-key-active",
        secret="simulation-secret-dev-sim-2",
    ),
    _SimulationDevice(
        device_id="dev-sim-3",
        display_name="仓储环境采集器",
        key_id="dev-sim-3-key-active",
        secret="simulation-secret-dev-sim-3",
    ),
]

_SIMULATION_RUNTIME = _SimulationGeneratorRuntime(
    lock=threading.Lock(),
    stop_event=threading.Event(),
)

_STAGE_EVENT_COUNTS = {
    "harvest": 1,
    "storage": 1,
    "transport": 1,
    "retail": 1,
}

_STAGE_DEVICE_ORDER = {
    "harvest": "dev-sim-1",
    "storage": "dev-sim-3",
    "transport": "dev-sim-2",
    "retail": "dev-sim-3",
}


def is_simulation_batch_id(batch_id: str) -> bool:
    return SIMULATION_BATCH_ID_PATTERN.fullmatch(batch_id) is not None


def simulation_device_number(device_id: str) -> int | None:
    match = SIMULATION_DEVICE_ID_PATTERN.fullmatch(device_id)
    if match is None:
        return None
    return int(match.group(1))


def is_simulation_device_id(device_id: str) -> bool:
    return simulation_device_number(device_id) is not None


def _batch_number(batch_id: str) -> int:
    try:
        return int(batch_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 1000


def _simulation_base_time(batch_id: str) -> datetime:
    batch_offset = max(_batch_number(batch_id) - 1000, 0)
    return datetime(2026, 5, 7, 12, 0, tzinfo=UTC) + timedelta(hours=batch_offset)


def _stage_for_index(index: int) -> str:
    if index < 2:
        return "harvest"
    if index < 4:
        return "storage"
    if index < 7:
        return "transport"
    return "retail"


def _stage_for_stream_index(index: int) -> str:
    index %= sum(_STAGE_EVENT_COUNTS.values())
    cursor = 0
    for stage, count in _STAGE_EVENT_COUNTS.items():
        if index < cursor + count:
            return stage
        cursor += count
    return "retail"


def _simulation_device_for_number(number: int) -> _SimulationDevice:
    if 1 <= number <= len(_SIMULATION_DEVICES):
        return _SIMULATION_DEVICES[number - 1]

    role_names = [
        "田间边缘节点",
        "预冷仓传感器",
        "干线冷链网关",
        "分拨仓采集器",
        "零售柜环境探头",
        "质检手持终端",
    ]
    role_name = role_names[(number - len(_SIMULATION_DEVICES) - 1) % len(role_names)]
    return _SimulationDevice(
        device_id=f"dev-sim-{number}",
        display_name=f"仿真{role_name} #{number:02d}",
        key_id=f"dev-sim-{number}-key-active",
        secret=f"simulation-secret-dev-sim-{number}",
    )


def _simulation_devices(min_device_count: int | None = None) -> list[_SimulationDevice]:
    device_count = max(
        len(_SIMULATION_DEVICES),
        min(
            min_device_count or len(_SIMULATION_DEVICES),
            DEFAULT_GENERATOR_MAX_DEVICE_COUNT,
        ),
    )
    return [_simulation_device_for_number(number) for number in range(1, device_count + 1)]


def _device_for_stage(
    stage: str,
    *,
    stream_index: int = 0,
    active_device_count: int | None = None,
) -> _SimulationDevice:
    if active_device_count is None:
        return _simulation_device_for_number(
            simulation_device_number(_STAGE_DEVICE_ORDER.get(stage, "dev-sim-3")) or 3
        )

    stage_offsets = {
        "harvest": 0,
        "storage": 2,
        "transport": 1,
        "retail": 3,
    }
    device_number = ((stream_index + stage_offsets.get(stage, 0)) % active_device_count) + 1
    return _simulation_device_for_number(device_number)


def _to_iso8601_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _active_stream_batch_ids(sequence: int, count: int) -> list[str]:
    base = 3000 + max(sequence, 0)
    return [f"batch-sim-{base + offset}" for offset in range(count)]


def _ensure_simulation_devices(
    session: Session,
    *,
    min_device_count: int | None = None,
) -> None:
    for device in _simulation_devices(min_device_count):
        managed_device = session.scalar(
            select(ManagedDevice).where(ManagedDevice.device_id == device.device_id)
        )
        if managed_device is None:
            managed_device = ManagedDevice(
                device_id=device.device_id,
                display_name=device.display_name,
                status="active",
            )
            session.add(managed_device)
            session.flush()
        elif managed_device.status != "active":
            continue

        key = session.scalar(
            select(ManagedDeviceKey).where(ManagedDeviceKey.key_id == device.key_id)
        )
        if key is None:
            session.add(
                ManagedDeviceKey(
                    device_id=managed_device.id,
                    key_id=device.key_id,
                    algorithm="HMAC_SHA256",
                    public_key=device.secret,
                    status="active",
                )
            )
        elif key.device_id == managed_device.id:
            key.algorithm = "HMAC_SHA256"
            key.public_key = device.secret
            key.status = "active"
            key.retired_at = None


def ensure_simulation_devices(*, min_device_count: int | None = None) -> None:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    with Session(engine) as session:
        _ensure_simulation_devices(session, min_device_count=min_device_count)
        session.commit()


def _sign_event_payload(payload: dict[str, Any], secret: str) -> str:
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
    canonical_payload = canonicalize_payload(signing_payload)
    return hmac.new(
        secret.encode("utf-8"), canonical_payload.encode("utf-8"), sha256
    ).hexdigest()


def _simulation_event_payload(batch_id: str, index: int) -> dict[str, Any]:
    stage = _stage_for_index(index)
    device = _device_for_stage(stage)
    timestamp = _simulation_base_time(batch_id) + timedelta(hours=index)
    batch_offset = max(_batch_number(batch_id) - 1000, 0)
    temperature_c = round(3.8 + index * 0.28 + (batch_offset % 3) * 0.12, 1)
    humidity_pct = round(76.0 - index * 0.7 + (batch_offset % 2) * 0.4, 1)
    co2_ppm = round(418 + index * 5 + (batch_offset % 4) * 3, 1)
    vibration_g = round(0.02 + (0.012 * (index % 4)), 3)

    payload: dict[str, Any] = {
        "version": "1.0.0",
        "device_id": device.device_id,
        "batch_id": batch_id,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "sensor_payload": {
            "temperature_c": temperature_c,
            "humidity_pct": humidity_pct,
            "co2_ppm": co2_ppm,
            "vibration_g": vibration_g,
            "source": "backend-simulation",
            "supply_chain_stage": stage,
        },
        "signature_envelope": {
            "algorithm": "HMAC_SHA256",
            "signature": "",
            "key_id": device.key_id,
        },
        "co2_ppm": co2_ppm,
        "vibration_g": vibration_g,
        "supply_chain_stage": stage,
    }
    payload["signature_envelope"]["signature"] = _sign_event_payload(
        payload, device.secret
    )
    return payload


def _stream_event_payload(
    batch_id: str,
    stream_index: int,
    *,
    active_device_count: int,
) -> tuple[dict[str, Any], str | None]:
    stage = _stage_for_stream_index(stream_index)
    device = _device_for_stage(
        stage,
        stream_index=stream_index,
        active_device_count=active_device_count,
    )
    timestamp = datetime.now(UTC)
    batch_offset = max(_batch_number(batch_id) - 3000, 0)
    phase = (stream_index + batch_offset * 3) / 3.0
    rng = random.Random(f"{batch_id}:{stream_index}:v2")
    anomaly: str | None = None

    temperature_base = {
        "harvest": 6.6,
        "storage": 3.7,
        "transport": 4.9,
        "retail": 7.1,
    }.get(stage, 5.0)
    humidity_base = {
        "harvest": 78.0,
        "storage": 73.0,
        "transport": 76.0,
        "retail": 68.0,
    }.get(stage, 74.0)
    co2_base = {
        "harvest": 112000.0,
        "storage": 132000.0,
        "transport": 124000.0,
        "retail": 108000.0,
    }.get(stage, 120000.0)
    vibration_base = 0.04 if stage != "transport" else 0.13

    temperature_c = temperature_base + math.sin(phase) * 0.55 + rng.uniform(-0.18, 0.18)
    humidity_pct = humidity_base + math.cos(phase * 0.8) * 1.6 + rng.uniform(-0.7, 0.7)
    co2_ppm = co2_base + math.sin(phase * 0.45) * 4200 + rng.uniform(-900, 900)
    vibration_g = vibration_base + abs(math.sin(phase * 1.7)) * 0.05 + rng.uniform(0, 0.015)

    anomaly_roll = (stream_index + batch_offset) % 17
    if anomaly_roll == 0 and stage in {"storage", "transport"}:
        temperature_c += 4.6
        humidity_pct -= 5.5
        anomaly = "temperature_excursion"
    elif anomaly_roll == 7 and stage == "transport":
        vibration_g += 1.18
        anomaly = "shock_event"
    elif anomaly_roll == 12 and stage == "retail":
        co2_ppm -= 33000
        anomaly = "door_opening"

    payload: dict[str, Any] = {
        "version": "1.0.0",
        "device_id": device.device_id,
        "batch_id": batch_id,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "sensor_payload": {
            "temperature_c": round(temperature_c, 1),
            "humidity_pct": round(max(45.0, min(humidity_pct, 92.0)), 1),
            "co2_ppm": round(max(60000.0, co2_ppm), 1),
            "vibration_g": round(max(0.0, vibration_g), 3),
            "source": "backend-stream-simulation",
            "supply_chain_stage": stage,
            "route_segment": stage,
            "battery_pct": round(93 - (stream_index % 60) * 0.08, 1),
            "rssi_dbm": round(-54 - (batch_offset % 5) * 2 + rng.uniform(-3, 3), 1),
        },
        "signature_envelope": {
            "algorithm": "HMAC_SHA256",
            "signature": "",
            "key_id": device.key_id,
        },
        "co2_ppm": round(max(60000.0, co2_ppm), 1),
        "vibration_g": round(max(0.0, vibration_g), 3),
        "supply_chain_stage": stage,
    }
    if anomaly is not None:
        payload["sensor_payload"]["anomaly"] = anomaly
    payload["signature_envelope"]["signature"] = _sign_event_payload(
        payload, device.secret
    )
    return payload, anomaly


def _ensure_quality_result(event_id: int, sensor_payload: dict[str, Any]) -> None:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    temperature_c = sensor_payload.get("temperature_c")
    humidity_pct = sensor_payload.get("humidity_pct")
    co2_ppm = sensor_payload.get("co2_ppm")
    vibration_g = sensor_payload.get("vibration_g")
    if not isinstance(temperature_c, (int, float)) or not isinstance(
        humidity_pct, (int, float)
    ):
        return

    result = grade_quality(
        temperature_c=float(temperature_c),
        humidity_pct=float(humidity_pct),
        co2_ppm=float(co2_ppm) if isinstance(co2_ppm, (int, float)) else None,
        vibration_g=float(vibration_g)
        if isinstance(vibration_g, (int, float))
        else None,
    )

    with Session(engine) as session:
        existing_quality_id = session.scalar(
            select(QualityResult.id).where(
                QualityResult.event_id == event_id,
                QualityResult.check_name == SIMULATION_QUALITY_CHECK_NAME,
            )
        )
        if existing_quality_id is not None:
            return

        session.add(
            QualityResult(
                event_id=event_id,
                check_name=SIMULATION_QUALITY_CHECK_NAME,
                status=result.grade,
                score=float(result.score),
                details={
                    "grade": result.grade,
                    "score": result.score,
                    "max_score": result.max_score,
                    "reasons": result.reasons,
                    "threshold_context": result.threshold_context,
                    "source": "backend-simulation",
                },
            )
        )
        session.commit()


def _create_stream_alert_if_needed(event_id: int, anomaly: str | None) -> int:
    if anomaly is None:
        return 0

    alert_config = {
        "temperature_excursion": (
            "simulation.temperature_excursion",
            "high",
            "仿真告警：冷链温度短时超出安全区间，需复核运输/仓储环境。",
        ),
        "shock_event": (
            "simulation.shock_event",
            "medium",
            "仿真告警：运输阶段检测到异常震动冲击。",
        ),
        "door_opening": (
            "simulation.door_opening",
            "medium",
            "仿真告警：零售交接阶段检测到疑似开门换气事件。",
        ),
    }
    config = alert_config.get(anomaly)
    if config is None:
        return 0

    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    with Session(engine) as session:
        alert_id = create_alert(
            session,
            event_id=event_id,
            alert_type=config[0],
            severity=config[1],
            message=config[2],
            suppression_window_seconds=0,
        )
        session.commit()
        return 1 if alert_id is not None else 0


def _ingest_simulation_payload(
    payload: dict[str, Any],
    *,
    idempotency_key: str,
) -> tuple[bool, int]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    event = TraceEvent.model_validate(payload)

    verification = verify_trace_event_signature_with_reason(event)
    if not verification.is_valid:
        raise RuntimeError(
            "simulation event signature verification failed: "
            f"{verification.reason or 'unknown'}"
        )

    with Session(engine) as session:
        already_ingested = session.scalar(
            select(IngestRequest.id).where(
                IngestRequest.idempotency_key == idempotency_key
            )
        )
    created = already_ingested is None
    result = ingest_trace_event(event, idempotency_key=idempotency_key)
    _ensure_quality_result(result.event_id, payload["sensor_payload"])
    return created, result.event_id


def _count_batch_state(batch_id: str) -> tuple[int, int]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        total_events = int(
            session.scalar(select(func.count()).where(Event.batch_id == batch_id)) or 0
        )
        event_ids = list(
            session.scalars(select(Event.id).where(Event.batch_id == batch_id))
        )
        if not event_ids:
            return total_events, 0
        anchored_events = int(
            session.scalar(
                select(func.count(func.distinct(AnchorReceipt.event_id))).where(
                    AnchorReceipt.event_id.in_(event_ids)
                )
            )
            or 0
        )
        return total_events, anchored_events


def ensure_simulation_batch(
    batch_id: str,
    *,
    event_count: int = DEFAULT_SIMULATION_EVENT_COUNT,
    run_anchoring: bool = True,
) -> SimulationBatchResult:
    if not is_simulation_batch_id(batch_id):
        raise SimulationBatchNotSupportedError(
            f"batch id '{batch_id}' is outside the simulation namespace"
        )

    event_count = max(1, min(event_count, 50))
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        _ensure_simulation_devices(session)
        session.commit()

    created_events = 0
    existing_events = 0
    for index in range(event_count):
        idempotency_key = f"simulation:{batch_id}:{index}:v1"
        payload = _simulation_event_payload(batch_id, index)
        created, _ = _ingest_simulation_payload(
            payload,
            idempotency_key=idempotency_key,
        )
        if created:
            created_events += 1
        else:
            existing_events += 1

    processed_anchoring = (
        run_anchor_state_machine(limit=event_count, batch_id=batch_id)
        if run_anchoring
        else 0
    )
    total_events, anchored_events = _count_batch_state(batch_id)

    return SimulationBatchResult(
        batch_id=batch_id,
        total_events=total_events,
        created_events=created_events,
        existing_events=existing_events,
        anchored_events=anchored_events,
        processed_anchoring=processed_anchoring,
    )


def run_simulation_tick(
    *, batches_per_tick: int = DEFAULT_GENERATOR_BATCHES_PER_TICK
) -> SimulationTickResult:
    batches_per_tick = max(1, min(batches_per_tick, 8))
    with _SIMULATION_RUNTIME.lock:
        sequence_start = _SIMULATION_RUNTIME.sequence
        batch_ids = _active_stream_batch_ids(sequence_start, batches_per_tick)
        _SIMULATION_RUNTIME.sequence += batches_per_tick

    active_device_count = min(
        DEFAULT_GENERATOR_MAX_DEVICE_COUNT,
        3 + sequence_start // DEFAULT_GENERATOR_BATCHES_PER_TICK,
    )
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    with Session(engine) as session:
        _ensure_simulation_devices(session, min_device_count=active_device_count)
        session.commit()

    generated_events = 0
    alerts_created = 0
    for offset, batch_id in enumerate(batch_ids):
        stream_index = sequence_start + offset
        payload, anomaly = _stream_event_payload(
            batch_id,
            stream_index,
            active_device_count=active_device_count,
        )
        idempotency_key = f"simulation-stream:{batch_id}:{stream_index}:v2"
        created, event_id = _ingest_simulation_payload(
            payload,
            idempotency_key=idempotency_key,
        )
        if created:
            generated_events += 1
            alerts_created += _create_stream_alert_if_needed(event_id, anomaly)

    processed_anchoring = run_anchor_state_machine(
        limit=max(generated_events, batches_per_tick)
    )
    with _SIMULATION_RUNTIME.lock:
        _SIMULATION_RUNTIME.generated_events += generated_events
        _SIMULATION_RUNTIME.generated_alerts += alerts_created
        _SIMULATION_RUNTIME.active_batches = batch_ids
        _SIMULATION_RUNTIME.last_tick_at = datetime.now(UTC)
        _SIMULATION_RUNTIME.last_error = None

    return SimulationTickResult(
        generated_events=generated_events,
        processed_anchoring=processed_anchoring,
        alerts_created=alerts_created,
        active_batches=batch_ids,
    )


def _generator_loop() -> None:
    while not _SIMULATION_RUNTIME.stop_event.wait(_SIMULATION_RUNTIME.interval_seconds):
        try:
            run_simulation_tick(
                batches_per_tick=_SIMULATION_RUNTIME.batches_per_tick,
            )
        except Exception as exc:  # noqa: BLE001 - keep the generator alive.
            with _SIMULATION_RUNTIME.lock:
                _SIMULATION_RUNTIME.last_error = str(exc)


def start_simulation_generator(
    *,
    interval_seconds: float = DEFAULT_GENERATOR_INTERVAL_SECONDS,
    batches_per_tick: int = DEFAULT_GENERATOR_BATCHES_PER_TICK,
) -> SimulationGeneratorStatus:
    interval_seconds = max(1.0, min(interval_seconds, 60.0))
    batches_per_tick = max(1, min(batches_per_tick, 8))
    should_prime = False
    with _SIMULATION_RUNTIME.lock:
        _SIMULATION_RUNTIME.interval_seconds = interval_seconds
        _SIMULATION_RUNTIME.batches_per_tick = batches_per_tick
        thread = _SIMULATION_RUNTIME.thread
        already_running = thread is not None and thread.is_alive()

        if not already_running:
            _SIMULATION_RUNTIME.stop_event = threading.Event()
            _SIMULATION_RUNTIME.started_at = datetime.now(UTC)
            _SIMULATION_RUNTIME.last_error = None
            _SIMULATION_RUNTIME.thread = threading.Thread(
                target=_generator_loop,
                name="simulation-generator",
                daemon=True,
            )
            _SIMULATION_RUNTIME.thread.start()
            should_prime = True

    if should_prime:
        run_simulation_tick(batches_per_tick=batches_per_tick)
    return get_simulation_generator_status()


def stop_simulation_generator() -> SimulationGeneratorStatus:
    with _SIMULATION_RUNTIME.lock:
        thread = _SIMULATION_RUNTIME.thread
        stop_event = _SIMULATION_RUNTIME.stop_event
        stop_event.set()
    if thread is not None and thread.is_alive():
        thread.join(timeout=2)
    with _SIMULATION_RUNTIME.lock:
        _SIMULATION_RUNTIME.thread = None
    return get_simulation_generator_status()


def get_simulation_generator_status() -> SimulationGeneratorStatus:
    with _SIMULATION_RUNTIME.lock:
        thread = _SIMULATION_RUNTIME.thread
        running = thread is not None and thread.is_alive() and not _SIMULATION_RUNTIME.stop_event.is_set()
        return SimulationGeneratorStatus(
            running=running,
            interval_seconds=_SIMULATION_RUNTIME.interval_seconds,
            batches_per_tick=_SIMULATION_RUNTIME.batches_per_tick,
            generated_events=_SIMULATION_RUNTIME.generated_events,
            generated_alerts=_SIMULATION_RUNTIME.generated_alerts,
            active_batches=list(_SIMULATION_RUNTIME.active_batches or []),
            started_at=_to_iso8601_z(_SIMULATION_RUNTIME.started_at),
            last_tick_at=_to_iso8601_z(_SIMULATION_RUNTIME.last_tick_at),
            last_error=_SIMULATION_RUNTIME.last_error,
        )
