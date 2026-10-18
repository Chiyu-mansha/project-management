"""SQLite 连接与初始化。

约定：每次连接后必须开启外键，否则 ON DELETE CASCADE 不生效。
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "campus.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 关键：SQLite 默认关闭外键，需每次连接后手动开启
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """建表（幂等）：新库执行 schema.sql；老库补建后续新增的表。"""
    conn = get_conn()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        if exists is None:
            schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
            conn.executescript(schema)
            conn.commit()
        # 老库 users 已存在时 schema.sql 不会重跑，新增表在此补建（幂等）
        conn.execute(
            """CREATE TABLE IF NOT EXISTS activity_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activity_id INTEGER NOT NULL,
                signup_deadline TEXT,
                eligible INTEGER NOT NULL DEFAULT 0,
                major_score REAL,
                interests_score REAL,
                skills_score REAL,
                conduct_score INTEGER,
                innovation_score INTEGER,
                comprehensive_score INTEGER,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, activity_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(activity_id) REFERENCES activities(id)
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> int:
    """执行单条写语句并提交，返回 lastrowid（用于 INSERT）。"""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


@contextmanager
def transaction():
    """事务：正常退出则提交，异常则回滚并重抛。"""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
