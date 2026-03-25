from __future__ import annotations

import os
from threading import Lock

from sqlalchemy import Engine, create_engine, inspect, text

from app.domain.persistence.models import Base

DEFAULT_DATABASE_URL = "sqlite:///./data/app.db"

_ENGINE_CACHE: dict[str, Engine] = {}
_SCHEMA_READY: set[str] = set()
_SCHEMA_LOCK = Lock()

_PERFORMANCE_INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_events_timestamp_id", "events", ("timestamp", "id")),
    ("ix_events_batch_timestamp_id", "events", ("batch_id", "timestamp", "id")),
    ("ix_events_device_timestamp_id", "events", ("device_id", "timestamp", "id")),
    ("ix_events_stage_timestamp_id", "events", ("supply_chain_stage", "timestamp", "id")),
    ("ix_ingest_requests_event_id_id", "ingest_requests", ("event_id", "id")),
    ("ix_quality_results_event_id_id", "quality_results", ("event_id", "id")),
    ("ix_anchor_receipts_event_id_id", "anchor_receipts", ("event_id", "id")),
    ("ix_alerts_status_event_id", "alerts", ("status", "event_id")),
    ("ix_managed_devices_status", "managed_devices", ("status",)),
)


def database_url() -> str:
    return os.getenv("TRACEABILITY_DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine(url: str) -> Engine:
    engine = _ENGINE_CACHE.get(url)
    if engine is None:
        engine = create_engine(url, future=True)
        _ENGINE_CACHE[url] = engine
    return engine


def _ensure_performance_indexes(engine: Engine) -> None:
    inspector = inspect(engine)
    preparer = engine.dialect.identifier_preparer

    with engine.begin() as connection:
        for index_name, table_name, column_names in _PERFORMANCE_INDEXES:
            if not inspector.has_table(table_name):
                continue

            available_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            if not set(column_names).issubset(available_columns):
                continue

            quoted_columns = ", ".join(preparer.quote(name) for name in column_names)
            statement = (
                f"CREATE INDEX IF NOT EXISTS {preparer.quote(index_name)} "
                f"ON {preparer.quote(table_name)} ({quoted_columns})"
            )
            connection.execute(text(statement))


def ensure_schema(url: str) -> None:
    if url in _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if url in _SCHEMA_READY:
            return
        engine = get_engine(url)
        Base.metadata.create_all(engine)
        _ensure_performance_indexes(engine)
        _SCHEMA_READY.add(url)
