from __future__ import annotations

from threading import Lock
from typing import Any

from sqlalchemy import Engine, inspect, literal

from app.domain.persistence.models import Event

_TABLE_COLUMNS_CACHE: dict[tuple[str, str], frozenset[str]] = {}
_TABLE_COLUMNS_LOCK = Lock()


def table_columns(engine: Engine, table_name: str) -> frozenset[str]:
    cache_key = (str(engine.url), table_name)
    columns = _TABLE_COLUMNS_CACHE.get(cache_key)
    if columns is not None:
        return columns

    with _TABLE_COLUMNS_LOCK:
        cached = _TABLE_COLUMNS_CACHE.get(cache_key)
        if cached is not None:
            return cached

        inspector = inspect(engine)
        resolved = frozenset(
            column["name"] for column in inspector.get_columns(table_name)
        )
        _TABLE_COLUMNS_CACHE[cache_key] = resolved
        return resolved


def event_has_column(engine: Engine, column_name: str) -> bool:
    return column_name in table_columns(engine, "events")


def optional_event_expressions(engine: Engine) -> tuple[Any, Any, Any, bool]:
    columns = table_columns(engine, "events")
    has_supply_chain_stage = "supply_chain_stage" in columns
    has_co2_ppm = "co2_ppm" in columns
    has_vibration_g = "vibration_g" in columns

    supply_chain_stage_expr = (
        Event.supply_chain_stage if has_supply_chain_stage else literal(None)
    )
    co2_ppm_expr = Event.co2_ppm if has_co2_ppm else literal(None)
    vibration_g_expr = Event.vibration_g if has_vibration_g else literal(None)

    return (
        supply_chain_stage_expr,
        co2_ppm_expr,
        vibration_g_expr,
        has_supply_chain_stage,
    )
