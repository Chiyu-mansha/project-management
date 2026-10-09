"""SQLite persistence for the formal POD-3 MVP service."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterator


class Database:
    def __init__(self, path: str | Path, schema_path: str | Path):
        self.path = str(path)
        self.schema_path = Path(schema_path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(self.schema_path.read_text(encoding="utf-8"))

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
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
    def row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def decode_user(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        row["roles"] = json.loads(row.get("roles") or "[]")
        row["organization_ids"] = json.loads(row.get("organization_ids") or "[]")
        return row
