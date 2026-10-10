"""Small, dependency-free JWT HS256 implementation for the MVP.

The production deployment should use the team's shared identity provider and
rotate JWT_SECRET through the secret manager. Keeping the implementation here
avoids coupling POD-3 to a second authentication library while the modules are
being integrated.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer_scheme = HTTPBearer(auto_error=False)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(
    subject: str,
    roles: list[str] | None = None,
    organization_ids: list[str] | None = None,
    *,
    expires_in_seconds: int = 3600,
    secret: str | None = None,
) -> str:
    """Create a token for local integration tests and service smoke tests."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": roles or ["STUDENT"],
        "organization_ids": organization_ids or [],
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in_seconds,
    }
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    message = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(
        (secret or os.getenv("JWT_SECRET", "dev-only-change-me")).encode(),
        message,
        hashlib.sha256,
    ).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64encode(signature)}"


def decode_access_token(token: str, *, secret: str | None = None) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_b64decode(encoded_header))
        payload = json.loads(_b64decode(encoded_payload))
        if header.get("alg") != "HS256":
            raise ValueError("unsupported JWT algorithm")
        expected = hmac.new(
            (secret or os.getenv("JWT_SECRET", "dev-only-change-me")).encode(),
            f"{encoded_header}.{encoded_payload}".encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(encoded_signature)):
            raise ValueError("invalid JWT signature")
        if not isinstance(payload.get("sub"), str) or not payload["sub"]:
            raise ValueError("JWT subject is required")
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("JWT has expired")
        if isinstance(payload.get("roles"), str):
            payload["roles"] = [payload["roles"]]
        if not isinstance(payload.get("roles", []), list):
            raise ValueError("JWT roles must be a list")
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid JWT") from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Bearer JWT is required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_roles(*required_roles: str):
    required = {role.upper() for role in required_roles}

    def dependency(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        roles = {str(role).upper() for role in user.get("roles", [])}
        if required and not roles.intersection(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Insufficient role"},
            )
        return user

    return dependency
