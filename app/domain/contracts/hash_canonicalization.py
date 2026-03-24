from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
import json

from pydantic import BaseModel


def _normalize_datetime(value: str) -> str:
    try:
        if "T" not in value:
            return value
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    return parsed.isoformat().replace("+00:00", "Z")


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        stripped = value.strip()
        return _normalize_datetime(stripped)
    return value


def canonicalize_payload(payload: Any) -> str:
    normalized = _normalize(payload)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def canonical_hash(payload: Any) -> str:
    canonical_payload = canonicalize_payload(payload)
    return sha256(canonical_payload.encode("utf-8")).hexdigest()
