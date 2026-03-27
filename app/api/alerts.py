from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.security.auth import Principal
from app.security.rbac import require_roles
from app.services.alerts import (
    AlertActionConflictError,
    AlertActionResult,
    AlertNotFoundError,
    acknowledge_alert,
    escalate_alert,
    query_recent_alerts,
    resolve_alert,
)

router = APIRouter(prefix="/v1", tags=["alerts"])


class AlertItemView(BaseModel):
    id: int
    event_id: int | None
    alert_type: str
    severity: str
    status: str
    message: str
    raised_at: str
    resolved_at: str | None


class AlertQueryResponse(BaseModel):
    order: Literal["newest_first"]
    total: int
    limit: int
    offset: int
    alerts: list[AlertItemView]


class AlertActionResponse(BaseModel):
    id: int
    status: str
    severity: str
    resolved_at: str | None
    audit_id: int


def _problem(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    type_path: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "type": f"https://example.com/problems/{type_path}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
        },
    )


def _action_response(result: AlertActionResult) -> AlertActionResponse:
    return AlertActionResponse(
        id=result.id,
        status=result.status,
        severity=result.severity,
        resolved_at=result.resolved_at,
        audit_id=result.audit_id,
    )


@router.get("/alerts", response_model=AlertQueryResponse)
async def get_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    include_simulation: bool = Query(default=True),
    _principal: Principal = Depends(require_roles("admin", "regulator")),
) -> AlertQueryResponse:
    page = query_recent_alerts(
        limit=limit,
        offset=offset,
        include_simulation=include_simulation,
    )
    return AlertQueryResponse(
        order="newest_first",
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        alerts=[AlertItemView(**alert.__dict__) for alert in page.alerts],
    )


@router.post("/alerts/{alert_id}/ack", response_model=AlertActionResponse)
async def acknowledge_existing_alert(
    alert_id: int,
    request: Request,
    principal: Principal = Depends(require_roles("admin", "regulator")),
) -> AlertActionResponse | JSONResponse:
    try:
        result = acknowledge_alert(actor=principal.subject, alert_id=alert_id)
    except AlertNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Alert was not found.",
            type_path="alert-not-found",
        )
    except AlertActionConflictError as exc:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail=exc.detail,
            type_path="alert-transition-conflict",
        )

    return _action_response(result)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertActionResponse)
async def resolve_existing_alert(
    alert_id: int,
    request: Request,
    principal: Principal = Depends(require_roles("admin", "regulator")),
) -> AlertActionResponse | JSONResponse:
    try:
        result = resolve_alert(actor=principal.subject, alert_id=alert_id)
    except AlertNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Alert was not found.",
            type_path="alert-not-found",
        )
    except AlertActionConflictError as exc:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail=exc.detail,
            type_path="alert-transition-conflict",
        )

    return _action_response(result)


@router.post("/alerts/{alert_id}/escalate", response_model=AlertActionResponse)
async def escalate_existing_alert(
    alert_id: int,
    request: Request,
    principal: Principal = Depends(require_roles("admin", "regulator")),
) -> AlertActionResponse | JSONResponse:
    try:
        result = escalate_alert(actor=principal.subject, alert_id=alert_id)
    except AlertNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Alert was not found.",
            type_path="alert-not-found",
        )
    except AlertActionConflictError as exc:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail=exc.detail,
            type_path="alert-transition-conflict",
        )

    return _action_response(result)
