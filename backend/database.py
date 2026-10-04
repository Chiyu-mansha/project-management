import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "app.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()
    conn = get_conn()
    try:
        conn.executescript(schema)
    except Exception:
        pass  # 表已存在时忽略，保证幂等
    # 兼容评论里约定的 category/status：老库没有就补列
    cols = [r[1] for r in conn.execute("PRAGMA table_info(faqs)").fetchall()]
    if "category" not in cols:
        conn.execute("ALTER TABLE faqs ADD COLUMN category TEXT DEFAULT ''")
    if "status" not in cols:
        conn.execute("ALTER TABLE faqs ADD COLUMN status TEXT DEFAULT 'published'")
    if "origin_title" not in cols:
        conn.execute("ALTER TABLE faqs ADD COLUMN origin_title TEXT DEFAULT ''")
    # 答疑日志表：用于统计高频提问、自动沉淀候选（本地新增，不动共享 schema）
    conn.execute(
        """CREATE TABLE IF NOT EXISTS qa_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER,
            question    TEXT NOT NULL,
            answer      TEXT,
            source      TEXT,
            count       INTEGER DEFAULT 1,
            created_at  TEXT
        )"""
    )
    qa_cols = [r[1] for r in conn.execute("PRAGMA table_info(qa_logs)").fetchall()]
    if "count" not in qa_cols:
        conn.execute("ALTER TABLE qa_logs ADD COLUMN count INTEGER DEFAULT 1")
    conn.commit()
    conn.close()


def dict_row(row):
    return dict(row) if row is not None else None
