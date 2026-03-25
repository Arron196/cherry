from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import Header, Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class AuthProblem(Exception):
    status: int
    title: str
    detail: str
    type_path: str


def auth_problem_response(request: Request, exc: AuthProblem) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={
            "type": f"https://example.com/problems/{exc.type_path}",
            "title": exc.title,
            "status": exc.status,
            "detail": exc.detail,
            "instance": request.url.path,
        },
    )


def _jwt_secret() -> str:
    return os.getenv("AUTH_JWT_SECRET", "dev-auth-secret")


def _jwt_issuer() -> str:
    return os.getenv("AUTH_JWT_ISSUER", "traceability-auth")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_jwt(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Bearer token is malformed.",
            type_path="auth-unauthorized",
        )

    header_segment, payload_segment, signature_segment = parts
    try:
        header = json.loads(_b64url_decode(header_segment))
        payload = json.loads(_b64url_decode(payload_segment))
        provided_signature = _b64url_decode(signature_segment)
    except (ValueError, json.JSONDecodeError):
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Bearer token could not be decoded.",
            type_path="auth-unauthorized",
        ) from None

    if header.get("alg") != "HS256":
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Bearer token algorithm is not supported.",
            type_path="auth-unauthorized",
        )

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(
        _jwt_secret().encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Bearer token signature is invalid.",
            type_path="auth-unauthorized",
        )

    if payload.get("iss") != _jwt_issuer():
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Bearer token issuer is invalid.",
            type_path="auth-unauthorized",
        )

    expires_at = payload.get("exp")
    if isinstance(expires_at, (int, float)) and expires_at <= time.time():
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Bearer token is expired.",
            type_path="auth-unauthorized",
        )

    return payload


def _extract_roles(claim: Any) -> tuple[str, ...]:
    if isinstance(claim, str):
        return (claim,)
    if isinstance(claim, list):
        roles: list[str] = []
        for item in claim:
            if isinstance(item, str):
                roles.append(item)
        return tuple(roles)
    return tuple()


def mint_access_token(*, subject: str, roles: tuple[str, ...], expires_in_seconds: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "roles": list(roles),
        "iss": _jwt_issuer(),
        "exp": int(time.time()) + expires_in_seconds,
    }

    encoded_header = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    encoded_payload = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(_jwt_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _b64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


async def get_current_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Principal:
    if authorization is None:
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Missing bearer token.",
            type_path="auth-unauthorized",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Authorization header must use Bearer token.",
            type_path="auth-unauthorized",
        )

    claims = _decode_jwt(token)

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthProblem(
            status=401,
            title="Unauthorized",
            detail="Bearer token subject is missing.",
            type_path="auth-unauthorized",
        )

    return Principal(subject=subject, roles=_extract_roles(claims.get("roles")))
