from __future__ import annotations

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.security.auth import mint_access_token

router = APIRouter(prefix="/v1", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    role: str


DEFAULT_DEMO_CREDENTIALS = {
    "admin": {"password": "admin123", "role": "admin"},
    "regulator": {"password": "regulator123", "role": "regulator"},
}


def _load_demo_credentials() -> dict[str, dict[str, str]]:
    raw = os.getenv("AUTH_DEMO_CREDENTIALS")
    if raw is None:
        return DEFAULT_DEMO_CREDENTIALS
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_DEMO_CREDENTIALS

    if not isinstance(parsed, dict):
        return DEFAULT_DEMO_CREDENTIALS

    normalized: dict[str, dict[str, str]] = {}
    for username, config in parsed.items():
        if not isinstance(username, str) or not isinstance(config, dict):
            continue
        password = config.get("password")
        role = config.get("role")
        if isinstance(password, str) and role in {"admin", "regulator"}:
            normalized[username] = {"password": password, "role": role}

    return normalized or DEFAULT_DEMO_CREDENTIALS


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


@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse | JSONResponse:
    username = payload.username.strip()
    password = payload.password.strip()

    if not username or not password:
        return _problem(
            request,
            status=401,
            title="Unauthorized",
            detail="Invalid username or password.",
            type_path="auth-login-failed",
        )

    credentials = _load_demo_credentials()
    account = credentials.get(username)

    if account is None or account["password"] != password:
        return _problem(
            request,
            status=401,
            title="Unauthorized",
            detail="Invalid username or password.",
            type_path="auth-login-failed",
        )

    role = account["role"]
    token = mint_access_token(
        subject=username,
        roles=(role,),
        expires_in_seconds=86400,
    )

    return LoginResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=86400,
        role=role,
    )
