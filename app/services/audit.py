from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.persistence.models import Audit
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)


def append_audit_row(
    *,
    actor: str,
    action: str,
    target: str,
    result: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)

    details: dict[str, Any] = {"result": result}
    if metadata:
        details.update(metadata)

    with Session(engine) as session:
        audit = Audit(
            actor=actor,
            action=action,
            target=target,
            metadata_=details,
        )
        # Append-only usage: API writes new audit rows, never updates/deletes them.
        session.add(audit)
        session.commit()
        session.refresh(audit)
        return audit.id
