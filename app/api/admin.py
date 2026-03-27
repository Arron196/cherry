from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi import Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.security.auth import Principal
from app.security.rbac import require_roles
from app.services.audit import append_audit_row
from app.services.device_management import (
    DeviceAlreadyExistsError,
    DeviceActiveKeyRecord,
    DeviceAuditRecord,
    DeviceDetailRecord,
    DeviceDisabledError,
    DeviceKeyAlreadyExistsError,
    DeviceKeyRecord,
    DeviceNotFoundError,
    DEFAULT_DEVICE_QUERY_LIMIT,
    MAX_DEVICE_QUERY_LIMIT,
    add_or_rotate_device_key,
    disable_device,
    query_managed_device_audits,
    query_managed_device_detail,
    query_managed_device_keys,
    query_managed_devices,
    register_device,
)
from app.services.simulation import (
    ensure_simulation_devices,
    is_simulation_device_id,
)

router = APIRouter(prefix="/admin", tags=["admin"])
v1_router = APIRouter(prefix="/v1", tags=["admin"])


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


class ActivatePolicyResponse(BaseModel):
    policy_id: str
    status: str
    audit_id: int


class RegisterDeviceInitialKeyRequest(BaseModel):
    key_id: str = Field(min_length=1, max_length=128)
    algorithm: str = Field(min_length=1, max_length=64)
    secret: str = Field(min_length=1)


class RegisterDeviceRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    initial_key: RegisterDeviceInitialKeyRequest | None = None


class RegisterDeviceInitialKeyResponse(BaseModel):
    key_id: str
    algorithm: str
    status: str


class RegisterDeviceResponse(BaseModel):
    device_id: str
    status: str
    audit_id: int
    initial_key: RegisterDeviceInitialKeyResponse | None = None


class RotateDeviceKeyRequest(BaseModel):
    key_id: str = Field(min_length=1, max_length=128)
    algorithm: str = Field(min_length=1, max_length=64)
    public_key: str = Field(min_length=1)


class RotateDeviceKeyResponse(BaseModel):
    device_id: str
    key_id: str
    algorithm: str
    status: str
    retired_key_ids: list[str]
    audit_id: int


class DisableDeviceRequest(BaseModel):
    reason: str | None = Field(default=None, min_length=1, max_length=1024)


class DisableDeviceResponse(BaseModel):
    device_id: str
    status: str
    retired_key_ids: list[str]
    audit_id: int


DeviceStatusFilter = Literal["active", "disabled"]


class DeviceListItemResponse(BaseModel):
    device_id: str
    name: str | None
    status: str
    last_seen_at: str | None
    created_at: str


class DeviceListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DeviceListItemResponse]


class DeviceKeyListItemResponse(BaseModel):
    key_id: str
    algorithm: str
    status: str
    activated_at: str
    retired_at: str | None


class DeviceKeyListResponse(BaseModel):
    device_id: str
    items: list[DeviceKeyListItemResponse]


class DeviceActiveKeyResponse(BaseModel):
    key_id: str
    algorithm: str
    status: str
    activated_at: str


class DeviceDetailResponse(BaseModel):
    device_id: str
    name: str | None
    status: str
    last_seen_at: str | None
    created_at: str
    key_count: int
    active_key: DeviceActiveKeyResponse | None
    signature_failures_last_24h: int
    latest_signature_failure_reason: str | None
    online_status_explanation: str


class DeviceAuditItemResponse(BaseModel):
    audit_id: int
    actor: str
    action: str
    target: str
    metadata: dict | None
    created_at: str


class DeviceAuditListResponse(BaseModel):
    device_id: str
    items: list[DeviceAuditItemResponse]


@router.post("/policies/{policy_id}/activate", response_model=ActivatePolicyResponse)
async def activate_policy(
    policy_id: str,
    principal: Principal = Depends(require_roles("admin")),
) -> ActivatePolicyResponse:
    audit_id = append_audit_row(
        actor=principal.subject,
        action="admin.policy.activate",
        target=f"policy:{policy_id}",
        result="success",
        metadata={"roles": list(principal.roles)},
    )
    return ActivatePolicyResponse(
        policy_id=policy_id,
        status="activated",
        audit_id=audit_id,
    )


@router.post("/devices", status_code=201, response_model=RegisterDeviceResponse)
async def create_device(
    request: Request,
    payload: RegisterDeviceRequest,
    principal: Principal = Depends(require_roles("admin")),
) -> RegisterDeviceResponse | JSONResponse:
    try:
        result = register_device(
            actor=principal.subject,
            device_id=payload.device_id,
            display_name=payload.display_name,
            initial_key_id=payload.initial_key.key_id if payload.initial_key else None,
            initial_key_algorithm=payload.initial_key.algorithm
            if payload.initial_key
            else None,
            initial_key_secret=payload.initial_key.secret
            if payload.initial_key
            else None,
        )
    except DeviceAlreadyExistsError:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail="A managed device with this device_id already exists.",
            type_path="device-already-exists",
        )
    except DeviceKeyAlreadyExistsError:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail="A managed key with this key_id already exists.",
            type_path="device-key-already-exists",
        )

    return RegisterDeviceResponse(
        device_id=result.device_id,
        status=result.status,
        audit_id=result.audit_id,
        initial_key=(
            RegisterDeviceInitialKeyResponse(
                key_id=result.initial_key.key_id,
                algorithm=result.initial_key.algorithm,
                status=result.initial_key.status,
            )
            if result.initial_key is not None
            else None
        ),
    )


@router.post(
    "/devices/{device_id}/keys", status_code=201, response_model=RotateDeviceKeyResponse
)
async def rotate_device_key(
    device_id: str,
    request: Request,
    payload: RotateDeviceKeyRequest,
    principal: Principal = Depends(require_roles("admin")),
) -> RotateDeviceKeyResponse | JSONResponse:
    try:
        result = add_or_rotate_device_key(
            actor=principal.subject,
            device_id=device_id,
            key_id=payload.key_id,
            algorithm=payload.algorithm,
            public_key=payload.public_key,
        )
    except DeviceNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Managed device was not found.",
            type_path="device-not-found",
        )
    except DeviceDisabledError:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail="Cannot add or rotate keys for a disabled device.",
            type_path="device-disabled",
        )
    except DeviceKeyAlreadyExistsError:
        return _problem(
            request,
            status=409,
            title="Conflict",
            detail="A managed key with this key_id already exists.",
            type_path="device-key-already-exists",
        )

    return RotateDeviceKeyResponse(
        device_id=result.device_id,
        key_id=result.key_id,
        algorithm=result.algorithm,
        status=result.status,
        retired_key_ids=result.retired_key_ids,
        audit_id=result.audit_id,
    )


@router.post("/devices/{device_id}/disable", response_model=DisableDeviceResponse)
async def disable_managed_device(
    device_id: str,
    request: Request,
    payload: DisableDeviceRequest,
    principal: Principal = Depends(require_roles("admin")),
) -> DisableDeviceResponse | JSONResponse:
    try:
        result = disable_device(
            actor=principal.subject,
            device_id=device_id,
            reason=payload.reason,
        )
    except DeviceNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Managed device was not found.",
            type_path="device-not-found",
        )

    return DisableDeviceResponse(
        device_id=result.device_id,
        status=result.status,
        retired_key_ids=result.retired_key_ids,
        audit_id=result.audit_id,
    )


@router.get("/devices/{device_id}/keys", response_model=DeviceKeyListResponse)
async def list_managed_device_keys(
    device_id: str,
    request: Request,
    principal: Principal = Depends(require_roles("admin")),
) -> DeviceKeyListResponse | JSONResponse:
    _ = principal
    if is_simulation_device_id(device_id):
        ensure_simulation_devices()
    try:
        items = query_managed_device_keys(device_id=device_id)
    except DeviceNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Managed device was not found.",
            type_path="device-not-found",
        )

    return DeviceKeyListResponse(
        device_id=device_id,
        items=[_device_key_response(item) for item in items],
    )


@router.get("/devices/{device_id}", response_model=DeviceDetailResponse)
async def get_managed_device_detail(
    device_id: str,
    request: Request,
    principal: Principal = Depends(require_roles("admin")),
) -> DeviceDetailResponse | JSONResponse:
    _ = principal
    if is_simulation_device_id(device_id):
        ensure_simulation_devices()
    try:
        item = query_managed_device_detail(device_id=device_id)
    except DeviceNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Managed device was not found.",
            type_path="device-not-found",
        )

    return _device_detail_response(item)


@router.get("/devices/{device_id}/audits", response_model=DeviceAuditListResponse)
async def list_managed_device_audits(
    device_id: str,
    request: Request,
    principal: Principal = Depends(require_roles("admin")),
) -> DeviceAuditListResponse | JSONResponse:
    _ = principal
    if is_simulation_device_id(device_id):
        ensure_simulation_devices()
    try:
        items = query_managed_device_audits(device_id=device_id)
    except DeviceNotFoundError:
        return _problem(
            request,
            status=404,
            title="Not Found",
            detail="Managed device was not found.",
            type_path="device-not-found",
        )

    return DeviceAuditListResponse(
        device_id=device_id,
        items=[_device_audit_response(item) for item in items],
    )


@v1_router.get("/devices", response_model=DeviceListResponse)
async def list_managed_devices(
    limit: int = Query(
        default=DEFAULT_DEVICE_QUERY_LIMIT, ge=1, le=MAX_DEVICE_QUERY_LIMIT
    ),
    offset: int = Query(default=0, ge=0),
    status: DeviceStatusFilter | None = Query(default=None),
    include_simulation: bool = Query(default=True),
    principal: Principal = Depends(require_roles("admin")),
) -> DeviceListResponse:
    _ = principal
    page = query_managed_devices(
        limit=limit,
        offset=offset,
        status=status,
        include_simulation=include_simulation,
    )
    return DeviceListResponse(
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        items=[DeviceListItemResponse(**item.__dict__) for item in page.items],
    )


def _device_key_response(item: DeviceKeyRecord) -> DeviceKeyListItemResponse:
    return DeviceKeyListItemResponse(
        key_id=item.key_id,
        algorithm=item.algorithm,
        status=item.status,
        activated_at=item.activated_at,
        retired_at=item.retired_at,
    )


def _device_active_key_response(item: DeviceActiveKeyRecord) -> DeviceActiveKeyResponse:
    return DeviceActiveKeyResponse(
        key_id=item.key_id,
        algorithm=item.algorithm,
        status=item.status,
        activated_at=item.activated_at,
    )


def _device_detail_response(item: DeviceDetailRecord) -> DeviceDetailResponse:
    return DeviceDetailResponse(
        device_id=item.device_id,
        name=item.name,
        status=item.status,
        last_seen_at=item.last_seen_at,
        created_at=item.created_at,
        key_count=item.key_count,
        active_key=(
            _device_active_key_response(item.active_key)
            if item.active_key is not None
            else None
        ),
        signature_failures_last_24h=item.signature_failures_last_24h,
        latest_signature_failure_reason=item.latest_signature_failure_reason,
        online_status_explanation=item.online_status_explanation,
    )


def _device_audit_response(item: DeviceAuditRecord) -> DeviceAuditItemResponse:
    return DeviceAuditItemResponse(
        audit_id=item.audit_id,
        actor=item.actor,
        action=item.action,
        target=item.target,
        metadata=item.metadata,
        created_at=item.created_at,
    )
