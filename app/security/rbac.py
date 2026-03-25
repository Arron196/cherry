from __future__ import annotations

from fastapi import Depends

from app.security.auth import AuthProblem, Principal, get_current_principal

SUPPORTED_ROLES = {"admin", "regulator"}


def require_roles(*allowed_roles: str):
    normalized_allowed = {role.lower() for role in allowed_roles}
    unknown_roles = normalized_allowed - SUPPORTED_ROLES
    if unknown_roles:
        raise ValueError(f"Unsupported role(s): {', '.join(sorted(unknown_roles))}")

    async def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        granted = {role.lower() for role in principal.roles if role.lower() in SUPPORTED_ROLES}
        if granted.intersection(normalized_allowed):
            return principal
        raise AuthProblem(
            status=403,
            title="Forbidden",
            detail="Bearer token does not include a role allowed for this operation.",
            type_path="auth-forbidden",
        )

    return dependency
