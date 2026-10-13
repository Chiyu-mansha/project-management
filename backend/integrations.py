"""Read-only adapters for the shared User and Activity domains."""

from __future__ import annotations

import os
from contextlib import closing
from typing import Any

import requests

from database import Database


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and payload.get("data") is not None:
        return payload["data"]
    return payload


class ActivityClient:
    def __init__(self, database: Database):
        self.database = database
        self.base_url = os.getenv("ACTIVITY_SERVICE_URL", "").rstrip("/")

    def get(self, activity_id: str, token: str | None = None) -> dict[str, Any] | None:
        if self.base_url:
            response = requests.get(
                f"{self.base_url}/api/activities/{activity_id}",
                headers={"Authorization": f"Bearer {token}"} if token else {},
                timeout=3,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            activity = _unwrap_data(response.json())
        else:
            with closing(self.database.connect()) as connection:
                row = connection.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
                activity = self.database.row(row)

        if not activity:
            return None
        result = dict(activity)
        # Normalize shared-schema naming variants for authorization checks
        # without writing back to the shared table.
        result.setdefault("organizer_id", result.get("organizer_id") or result.get("organizer"))
        result.setdefault("organizer_name", result.get("organizer_name") or result.get("organizer"))
        if result.get("comprehensive_score") is None and result.get("zongce_score") is not None:
            try:
                result["comprehensive_score"] = float(result["zongce_score"])
            except (TypeError, ValueError):
                result["comprehensive_score"] = None
        return result


class UserClient:
    """Read-only user adapter retained for shared-domain integration."""

    def __init__(self, database: Database):
        self.database = database
        self.base_url = os.getenv("USER_SERVICE_URL", "").rstrip("/")

    def get(self, user_id: str, token: str | None = None) -> dict[str, Any] | None:
        if self.base_url:
            response = requests.get(
                f"{self.base_url}/api/users/{user_id}",
                headers={"Authorization": f"Bearer {token}"} if token else {},
                timeout=3,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return self.database.decode_user(_unwrap_data(response.json()))

        with closing(self.database.connect()) as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self.database.decode_user(self.database.row(row))
