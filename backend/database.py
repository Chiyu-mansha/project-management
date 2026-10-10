"""PostgreSQL persistence for the formal POD-3 MVP service."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


class Database:
    def __init__(self, database_url: str):
        if not database_url:
            raise RuntimeError("POD3_DATABASE_URL is not configured")
        self.database_url = database_url

    def connect(self) -> Connection:
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
        )

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def decode_user(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None

        result = dict(row)

        roles = result.get("roles")
        organization_ids = result.get("organization_ids")

        if isinstance(roles, str):
            result["roles"] = json.loads(roles or "[]")

        if isinstance(organization_ids, str):
            result["organization_ids"] = json.loads(organization_ids or "[]")

        return result
