"""Authentication adapter for the shared authentication domain.

POD-3 deliberately treats the value in ``Authorization: Bearer`` as an
opaque simple token. It does not issue, decode, or verify JWTs. In the
integrated environment the token is validated by the shared authentication
service through ``AUTH_SERVICE_URL``. ``POD3_TEST_TOKENS`` exists only for
isolated automated tests and is never a production authentication mechanism.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _normalize_user(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("data") is not None:
        payload = payload["data"]
    if not isinstance(payload, dict):
        raise ValueError("authentication service returned an invalid user")

    subject = payload.get("sub") or payload.get("user_id") or payload.get("id")
    if not isinstance(subject, str) or not subject:
        raise ValueError("authentication service did not return a user id")

    roles = payload.get("roles")
    if roles is None and payload.get("role") is not None:
        roles = [payload["role"]]
    if isinstance(roles, str):
        roles = [roles]
    if not isinstance(roles, list):
        roles = []

    return {**payload, "sub": subject, "roles": roles}


def _test_user(token: str) -> dict[str, Any] | None:
    raw = os.getenv("POD3_TEST_TOKENS", "")
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
        payload = mapping.get(token)
    except (TypeError, AttributeError, json.JSONDecodeError):
        return None
    return _normalize_user(payload) if payload is not None else None


def _resolve_from_auth_service(token: str) -> dict[str, Any]:
    base_url = os.getenv("AUTH_SERVICE_URL", "").rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_SERVICE_UNAVAILABLE", "message": "AUTH_SERVICE_URL is not configured"},
        )

    endpoint = os.getenv("AUTH_SERVICE_ME_PATH", "/api/auth/me")
    url = endpoint if endpoint.startswith(("http://", "https://")) else f"{base_url}/{endpoint.lstrip('/')}"
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=3)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_SERVICE_UNAVAILABLE", "message": "Unable to reach authentication service"},
        ) from exc
    if response.status_code in {401, 403}:
        raise _unauthorized("Invalid or expired token")
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_SERVICE_ERROR", "message": "Authentication service rejected the request"},
        )
    try:
        return _normalize_user(response.json())
    except (ValueError, requests.exceptions.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_SERVICE_ERROR", "message": "Authentication service returned invalid data"},
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise _unauthorized("Bearer token is required")

    token = credentials.credentials.strip()
    local_user = _test_user(token)
    if local_user is not None:
        return local_user
    return _resolve_from_auth_service(token)


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
