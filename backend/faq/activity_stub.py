"""临时活动占位路由：仅供成员3的 FAQ 页联调使用。

归属说明：
- 完整活动 CRUD 归成员2所有。
- 本文件只保留最小读写（列表、创建），成员2的正式活动模块落地后删除。
- 不要在其它业务中引用本占位路由。
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_conn, dict_row

router = APIRouter(prefix="/api/activities", tags=["activities-stub"])


class ActIn(BaseModel):
    title: str
    description: Optional[str] = ""
    organizer: Optional[str] = ""
    type: Optional[str] = ""
    status: Optional[str] = "published"


@router.get("")
def list_activities():
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id, title FROM activities ORDER BY id DESC LIMIT 200").fetchall()
    except Exception:
        rows = []
    conn.close()
    return {"items": [dict_row(r) for r in rows], "total": len(rows)}


@router.post("")
def create_activity(body: ActIn):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO activities(title,description,organizer,type,status) VALUES(?,?,?,?,?)",
        (body.title, body.description, body.organizer, body.type, body.status),
    )
    conn.commit()
    nid = cur.lastrowid
    row = conn.execute("SELECT id, title FROM activities WHERE id=?", (nid,)).fetchone()
    conn.close()
    return dict_row(row)
