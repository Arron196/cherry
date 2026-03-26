from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.contracts.hash_canonicalization import canonical_hash
from app.domain.contracts.trace_event import TraceEvent
from app.domain.persistence.models import Base, Event, IngestRequest
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)
from app.services.event_schema import table_columns


class IdempotencyConflictError(Exception):
    """Raised when idempotency key is reused with a different payload."""


@dataclass(frozen=True)
class IngestResult:
    event_id: int
    ingest_status: str


def ingest_trace_event(event: TraceEvent, idempotency_key: str) -> IngestResult:
    payload_hash = canonical_hash(event.canonical_payload())
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    with Session(engine) as session:
        try:
            event_columns = table_columns(engine, "events")
            existing_request = session.scalar(
                select(IngestRequest).where(
                    IngestRequest.idempotency_key == idempotency_key
                )
            )
            if existing_request is not None:
                if existing_request.payload_hash != payload_hash:
                    raise IdempotencyConflictError
                return IngestResult(
                    event_id=existing_request.event_id,
                    ingest_status=existing_request.ingest_status,
                )

            existing_event_id = session.scalar(
                select(Event.id).where(Event.canonical_hash == payload_hash)
            )
            if existing_event_id is None:
                event_values = {
                    "version": event.version,
                    "device_id": event.device_id,
                    "batch_id": event.batch_id,
                    "timestamp": event.timestamp,
                    "sensor_payload": event.sensor_payload.model_dump(mode="json"),
                    "signature_envelope": event.signature_envelope.model_dump(
                        mode="json"
                    ),
                    "canonical_hash": payload_hash,
                }
                if "co2_ppm" in event_columns:
                    event_values["co2_ppm"] = event.co2_ppm
                if "vibration_g" in event_columns:
                    event_values["vibration_g"] = event.vibration_g
                if "supply_chain_stage" in event_columns:
                    event_values["supply_chain_stage"] = event.supply_chain_stage

                event_table = Base.metadata.tables["events"]
                insert_result = session.connection().execute(
                    event_table.insert().values(event_values)
                )
                inserted_primary_key = insert_result.inserted_primary_key
                if inserted_primary_key:
                    existing_event_id = int(inserted_primary_key[0])
                else:
                    existing_event_id = session.scalar(
                        select(Event.id).where(Event.canonical_hash == payload_hash)
                    )
                if existing_event_id is None:
                    raise RuntimeError("failed to resolve inserted event id")

            ingest_request = IngestRequest(
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                ingest_status="RECEIVED",
                event_id=int(existing_event_id),
            )
            session.add(ingest_request)
            session.commit()

            return IngestResult(
                event_id=int(existing_event_id), ingest_status="RECEIVED"
            )
        except IntegrityError:
            session.rollback()
            existing_request = session.scalar(
                select(IngestRequest).where(
                    IngestRequest.idempotency_key == idempotency_key
                )
            )
            if existing_request is None:
                raise
            if existing_request.payload_hash != payload_hash:
                raise IdempotencyConflictError
            return IngestResult(
                event_id=existing_request.event_id,
                ingest_status=existing_request.ingest_status,
            )
