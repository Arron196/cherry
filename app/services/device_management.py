from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.persistence.models import Audit, Event, ManagedDevice, ManagedDeviceKey
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)


class DeviceManagementError(Exception):
    """Base class for device management workflow errors."""


class DeviceAlreadyExistsError(DeviceManagementError):
    pass


class DeviceNotFoundError(DeviceManagementError):
    pass


class DeviceDisabledError(DeviceManagementError):
    pass


class DeviceKeyAlreadyExistsError(DeviceManagementError):
    pass


@dataclass(frozen=True)
class DeviceRegistrationResult:
    device_id: str
    status: str
    audit_id: int
    initial_key: DeviceRegistrationInitialKeyResult | None = None


@dataclass(frozen=True)
class DeviceRegistrationInitialKeyResult:
    key_id: str
    algorithm: str
    status: str


@dataclass(frozen=True)
class DeviceKeyRotationResult:
    device_id: str
    key_id: str
    algorithm: str
    status: str
    retired_key_ids: list[str]
    audit_id: int


@dataclass(frozen=True)
class DeviceDisableResult:
    device_id: str
    status: str
    retired_key_ids: list[str]
    audit_id: int


DEFAULT_DEVICE_QUERY_LIMIT = 50
MAX_DEVICE_QUERY_LIMIT = 200
DEVICE_ONLINE_THRESHOLD = timedelta(minutes=15)
SIMULATION_DEVICE_LIKE = "dev-sim-%"


@dataclass(frozen=True)
class DeviceRecord:
    device_id: str
    name: str | None
    status: str
    last_seen_at: str | None
    created_at: str


@dataclass(frozen=True)
class DevicePage:
    total: int
    limit: int
    offset: int
    items: list[DeviceRecord]


@dataclass(frozen=True)
class DeviceKeyRecord:
    key_id: str
    algorithm: str
    status: str
    activated_at: str
    retired_at: str | None


@dataclass(frozen=True)
class DeviceActiveKeyRecord:
    key_id: str
    algorithm: str
    status: str
    activated_at: str


@dataclass(frozen=True)
class DeviceDetailRecord:
    device_id: str
    name: str | None
    status: str
    last_seen_at: str | None
    created_at: str
    key_count: int
    active_key: DeviceActiveKeyRecord | None
    signature_failures_last_24h: int
    latest_signature_failure_reason: str | None
    online_status_explanation: str


@dataclass(frozen=True)
class DeviceAuditRecord:
    audit_id: int
    actor: str
    action: str
    target: str
    metadata: dict | None
    created_at: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_iso8601_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _collect_recent_signature_failures(
    session: Session,
    *,
    device_id: str,
    now: datetime,
) -> tuple[int, str | None]:
    window_start = now - timedelta(hours=24)
    rows = list(
        session.scalars(
            select(Audit)
            .where(
                Audit.target == f"device:{device_id}",
                Audit.action == "ingest.signature.verify",
            )
            .order_by(Audit.created_at.desc(), Audit.id.desc())
        )
    )

    count = 0
    latest_reason: str | None = None
    for row in rows:
        created_at = _to_utc(row.created_at)
        if created_at < window_start:
            continue
        metadata = row.metadata_ if isinstance(row.metadata_, dict) else {}
        if metadata.get("result") != "failure":
            continue
        count += 1
        if latest_reason is None:
            reason = metadata.get("reason")
            latest_reason = str(reason) if reason is not None else None
    return count, latest_reason


def _online_status_explanation(
    *,
    status: str,
    disabled_reason: str | None,
    last_seen_at: datetime | None,
    now: datetime,
) -> str:
    if status == "disabled":
        if disabled_reason:
            return f"Offline: device is disabled (reason: {disabled_reason})."
        return "Offline: device is disabled."

    if last_seen_at is None:
        return "Offline: device has not reported any events yet."

    normalized_last_seen = _to_utc(last_seen_at)
    if now - normalized_last_seen <= DEVICE_ONLINE_THRESHOLD:
        return (
            f"Online: last event at {_to_iso8601_z(normalized_last_seen)} "
            "is within the 15-minute threshold."
        )
    return (
        f"Offline: last event at {_to_iso8601_z(normalized_last_seen)} "
        "is older than the 15-minute threshold."
    )


def _append_audit(
    session: Session,
    *,
    actor: str,
    action: str,
    target: str,
    metadata: dict | None = None,
) -> int:
    details = {"result": "success"}
    if metadata:
        details.update(metadata)
    audit = Audit(actor=actor, action=action, target=target, metadata_=details)
    session.add(audit)
    session.flush()
    return audit.id


def register_device(
    *,
    actor: str,
    device_id: str,
    display_name: str | None,
    initial_key_id: str | None = None,
    initial_key_algorithm: str | None = None,
    initial_key_secret: str | None = None,
) -> DeviceRegistrationResult:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        existing_device = session.scalar(
            select(ManagedDevice).where(ManagedDevice.device_id == device_id)
        )
        if existing_device is not None:
            raise DeviceAlreadyExistsError

        if initial_key_id is not None:
            existing_key = session.scalar(
                select(ManagedDeviceKey).where(
                    ManagedDeviceKey.key_id == initial_key_id
                )
            )
            if existing_key is not None:
                raise DeviceKeyAlreadyExistsError

        managed_device = ManagedDevice(
            device_id=device_id,
            display_name=display_name,
            status="active",
        )
        session.add(managed_device)
        session.flush()

        initial_key_result: DeviceRegistrationInitialKeyResult | None = None
        if (
            initial_key_id is not None
            and initial_key_algorithm is not None
            and initial_key_secret is not None
        ):
            session.add(
                ManagedDeviceKey(
                    device_id=managed_device.id,
                    key_id=initial_key_id,
                    algorithm=initial_key_algorithm,
                    public_key=initial_key_secret,
                    status="active",
                )
            )
            initial_key_result = DeviceRegistrationInitialKeyResult(
                key_id=initial_key_id,
                algorithm=initial_key_algorithm,
                status="active",
            )

        register_metadata: dict[str, str | None] = {"display_name": display_name}
        if initial_key_id is not None:
            register_metadata["initial_key_id"] = initial_key_id
        if initial_key_algorithm is not None:
            register_metadata["initial_key_algorithm"] = initial_key_algorithm

        audit_id = _append_audit(
            session,
            actor=actor,
            action="admin.device.register",
            target=f"device:{device_id}",
            metadata=register_metadata,
        )
        session.commit()
        return DeviceRegistrationResult(
            device_id=device_id,
            status="active",
            audit_id=audit_id,
            initial_key=initial_key_result,
        )


def add_or_rotate_device_key(
    *,
    actor: str,
    device_id: str,
    key_id: str,
    algorithm: str,
    public_key: str,
) -> DeviceKeyRotationResult:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        managed_device = session.scalar(
            select(ManagedDevice).where(ManagedDevice.device_id == device_id)
        )
        if managed_device is None:
            raise DeviceNotFoundError
        if managed_device.status != "active":
            raise DeviceDisabledError

        existing_key = session.scalar(
            select(ManagedDeviceKey).where(ManagedDeviceKey.key_id == key_id)
        )
        if existing_key is not None:
            raise DeviceKeyAlreadyExistsError

        active_keys = list(
            session.scalars(
                select(ManagedDeviceKey).where(
                    ManagedDeviceKey.device_id == managed_device.id,
                    ManagedDeviceKey.status == "active",
                )
            )
        )
        retired_key_ids: list[str] = []
        retired_at = _utcnow()
        for row in active_keys:
            row.status = "retired"
            row.retired_at = retired_at
            retired_key_ids.append(row.key_id)

        session.add(
            ManagedDeviceKey(
                device_id=managed_device.id,
                key_id=key_id,
                algorithm=algorithm,
                public_key=public_key,
                status="active",
            )
        )
        audit_id = _append_audit(
            session,
            actor=actor,
            action="admin.device.key.rotate",
            target=f"device:{device_id}",
            metadata={
                "key_id": key_id,
                "algorithm": algorithm,
                "retired_key_ids": retired_key_ids,
            },
        )
        session.commit()

        return DeviceKeyRotationResult(
            device_id=device_id,
            key_id=key_id,
            algorithm=algorithm,
            status="active",
            retired_key_ids=retired_key_ids,
            audit_id=audit_id,
        )


def disable_device(
    *, actor: str, device_id: str, reason: str | None
) -> DeviceDisableResult:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        managed_device = session.scalar(
            select(ManagedDevice).where(ManagedDevice.device_id == device_id)
        )
        if managed_device is None:
            raise DeviceNotFoundError

        managed_device.status = "disabled"
        managed_device.disabled_reason = reason
        managed_device.disabled_at = _utcnow()

        active_keys = list(
            session.scalars(
                select(ManagedDeviceKey).where(
                    ManagedDeviceKey.device_id == managed_device.id,
                    ManagedDeviceKey.status == "active",
                )
            )
        )
        retired_key_ids: list[str] = []
        retired_at = _utcnow()
        for row in active_keys:
            row.status = "retired"
            row.retired_at = retired_at
            retired_key_ids.append(row.key_id)

        audit_id = _append_audit(
            session,
            actor=actor,
            action="admin.device.disable",
            target=f"device:{device_id}",
            metadata={"reason": reason, "retired_key_ids": retired_key_ids},
        )
        session.commit()

        return DeviceDisableResult(
            device_id=device_id,
            status="disabled",
            retired_key_ids=retired_key_ids,
            audit_id=audit_id,
        )


def query_managed_devices(
    *,
    limit: int = DEFAULT_DEVICE_QUERY_LIMIT,
    offset: int = 0,
    status: str | None = None,
    include_simulation: bool = True,
) -> DevicePage:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    base_query = (
        select(
            ManagedDevice.id.label("id"),
            ManagedDevice.device_id.label("device_id"),
            ManagedDevice.display_name.label("name"),
            ManagedDevice.status.label("status"),
            func.max(Event.timestamp).label("last_seen_at"),
            ManagedDevice.created_at.label("created_at"),
        )
        .select_from(ManagedDevice)
        .outerjoin(Event, Event.device_id == ManagedDevice.device_id)
        .group_by(
            ManagedDevice.id,
            ManagedDevice.device_id,
            ManagedDevice.display_name,
            ManagedDevice.status,
            ManagedDevice.created_at,
        )
    )
    if status is not None:
        base_query = base_query.where(ManagedDevice.status == status)
    if not include_simulation:
        base_query = base_query.where(
            ~ManagedDevice.device_id.like(SIMULATION_DEVICE_LIKE)
        )

    filtered_subquery = base_query.subquery()
    with Session(engine) as session:
        total = int(
            session.scalar(select(func.count()).select_from(filtered_subquery)) or 0
        )
        rows = session.execute(
            select(filtered_subquery)
            .order_by(
                filtered_subquery.c.created_at.desc(), filtered_subquery.c.id.desc()
            )
            .offset(offset)
            .limit(limit)
        ).all()

    return DevicePage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            DeviceRecord(
                device_id=str(row.device_id),
                name=row.name,
                status=str(row.status),
                last_seen_at=_to_iso8601_z(row.last_seen_at),
                created_at=_to_iso8601_z(row.created_at) or "",
            )
            for row in rows
        ],
    )


def query_managed_device_keys(*, device_id: str) -> list[DeviceKeyRecord]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        managed_device = session.scalar(
            select(ManagedDevice).where(ManagedDevice.device_id == device_id)
        )
        if managed_device is None:
            raise DeviceNotFoundError

        rows = list(
            session.scalars(
                select(ManagedDeviceKey)
                .where(ManagedDeviceKey.device_id == managed_device.id)
                .order_by(
                    ManagedDeviceKey.activated_at.desc(), ManagedDeviceKey.id.desc()
                )
            )
        )

    return [
        DeviceKeyRecord(
            key_id=row.key_id,
            algorithm=row.algorithm,
            status=row.status,
            activated_at=_to_iso8601_z(row.activated_at) or "",
            retired_at=_to_iso8601_z(row.retired_at),
        )
        for row in rows
    ]


def query_managed_device_detail(*, device_id: str) -> DeviceDetailRecord:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    now = _utcnow()

    with Session(engine) as session:
        managed_device = session.scalar(
            select(ManagedDevice).where(ManagedDevice.device_id == device_id)
        )
        if managed_device is None:
            raise DeviceNotFoundError

        last_seen_at = session.scalar(
            select(func.max(Event.timestamp)).where(
                Event.device_id == managed_device.device_id
            )
        )
        key_count = int(
            session.scalar(
                select(func.count())
                .select_from(ManagedDeviceKey)
                .where(ManagedDeviceKey.device_id == managed_device.id)
            )
            or 0
        )
        active_key_row = session.scalar(
            select(ManagedDeviceKey)
            .where(
                ManagedDeviceKey.device_id == managed_device.id,
                ManagedDeviceKey.status == "active",
            )
            .order_by(ManagedDeviceKey.activated_at.desc(), ManagedDeviceKey.id.desc())
        )
        signature_failures_last_24h, latest_signature_failure_reason = (
            _collect_recent_signature_failures(
                session,
                device_id=managed_device.device_id,
                now=now,
            )
        )

    return DeviceDetailRecord(
        device_id=managed_device.device_id,
        name=managed_device.display_name,
        status=managed_device.status,
        last_seen_at=_to_iso8601_z(last_seen_at),
        created_at=_to_iso8601_z(managed_device.created_at) or "",
        key_count=key_count,
        active_key=(
            DeviceActiveKeyRecord(
                key_id=active_key_row.key_id,
                algorithm=active_key_row.algorithm,
                status=active_key_row.status,
                activated_at=_to_iso8601_z(active_key_row.activated_at) or "",
            )
            if active_key_row is not None
            else None
        ),
        signature_failures_last_24h=signature_failures_last_24h,
        latest_signature_failure_reason=latest_signature_failure_reason,
        online_status_explanation=_online_status_explanation(
            status=managed_device.status,
            disabled_reason=managed_device.disabled_reason,
            last_seen_at=last_seen_at,
            now=now,
        ),
    )


def query_managed_device_audits(
    *, device_id: str, limit: int = 100
) -> list[DeviceAuditRecord]:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        managed_device = session.scalar(
            select(ManagedDevice).where(ManagedDevice.device_id == device_id)
        )
        if managed_device is None:
            raise DeviceNotFoundError

        rows = list(
            session.scalars(
                select(Audit)
                .where(
                    Audit.target == f"device:{device_id}",
                    Audit.action.like("admin.device.%"),
                )
                .order_by(Audit.created_at.desc(), Audit.id.desc())
                .limit(limit)
            )
        )

    return [
        DeviceAuditRecord(
            audit_id=int(row.id),
            actor=row.actor,
            action=row.action,
            target=row.target,
            metadata=row.metadata_,
            created_at=_to_iso8601_z(row.created_at) or "",
        )
        for row in rows
    ]
