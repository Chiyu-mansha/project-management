"""Adapters for the Activity and User modules.

When a module URL is configured, requests are forwarded to that module. In a
single-process MVP the local PostgreSQL database is used as the integration
seam, so the same POD-3 code works before the other services are deployed.
"""

from __future__ import annotations

import os
from contextlib import closing
from typing import Any

from database import Database


class ActivityClient:
    def __init__(self, database: Database):
        self.database = database
        self.base_url = os.getenv("ACTIVITY_SERVICE_URL", "").rstrip("/")

    def get(
        self,
        activity_id: str,
        token: str | None = None,
    ) -> dict[str, Any] | None:
        if self.base_url:
            import requests

            response = requests.get(
                f"{self.base_url}/api/activities/{activity_id}",
                headers={"Authorization": f"Bearer {token}"} if token else {},
                timeout=3,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

        with closing(self.database.connect()) as connection:
            return self.database.row(
                connection.execute(
                    "SELECT * FROM activities WHERE id = %s",
                    (activity_id,),
                ).fetchone()
            )


class UserClient:
    def __init__(self, database: Database):
        self.database = database
        self.base_url = os.getenv("USER_SERVICE_URL", "").rstrip("/")

    def get(
        self,
        user_id: str,
        token: str | None = None,
    ) -> dict[str, Any] | None:
        if self.base_url:
            import requests

            response = requests.get(
                f"{self.base_url}/api/users/{user_id}",
                headers={"Authorization": f"Bearer {token}"} if token else {},
                timeout=3,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

        with closing(self.database.connect()) as connection:
            return self.database.decode_user(
                self.database.row(
                    connection.execute(
                        "SELECT * FROM users WHERE id = %s",
                        (user_id,),
                    ).fetchone()
                )
            )
