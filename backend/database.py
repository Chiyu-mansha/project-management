import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "campus.db"   # PM 合并仪式统一:与 POD-2 db.py 共用同一个库文件(原 app.db)
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
    if "updated_at" not in cols:
        conn.execute("ALTER TABLE faqs ADD COLUMN updated_at TEXT")
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
    # 活动表迁移：老库是 v1.0 结构(organizer/type/status 等)，新 schema v1.3
    # 新增 organizer_id 等字段；缺列则补列，保证旧 app.db 也能跑
    try:
        act_cols = [r[1] for r in conn.execute("PRAGMA table_info(activities)").fetchall()]
        _need = {
            "type": "TEXT",
            "organizer_id": "INTEGER",
            "start_time": "TEXT",
            "end_time": "TEXT",
            "location": "TEXT",
            "description": "TEXT",
            "requirements": "TEXT",
            "tags": "TEXT",
            "has_ticket": "INTEGER DEFAULT 1",
            "comprehensive_score": "INTEGER",
            "conduct_score": "REAL",
            "innovation_score": "REAL",
            "signup_deadline": "TEXT",
            "min_team_member": "INTEGER DEFAULT 1",
            "max_team_member": "INTEGER DEFAULT 1",
            "max_participants": "INTEGER",
            "status": "TEXT DEFAULT 'draft'",
            "article": "TEXT",
            "cover_image": "TEXT",
            "created_at": "TEXT",
        }
        for _c, _t in _need.items():
            if _c not in act_cols:
                conn.execute(f"ALTER TABLE activities ADD COLUMN {_c} {_t}")
        # 兼容老字段名：organizer(文本主办方) -> 保留；新代码用 organizer_id
    except Exception:
        pass
    conn.commit()
    conn.close()


def dict_row(row):
    return dict(row) if row is not None else None
