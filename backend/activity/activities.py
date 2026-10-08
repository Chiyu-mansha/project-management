"""活动发布管理：完整 CRUD（成员2 的域）。

接口（前缀 /api/activities）：
- POST   /api/activities        发布活动/竞赛
- GET    /api/activities        列表（类型/标签/关键词筛选 + 分页）
- GET    /api/activities/{id}   详情
- PUT    /api/activities/{id}   编辑/变更
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_conn, dict_row

router = APIRouter(prefix="/api/activities", tags=["activities"])


class ActIn(BaseModel):
    """创建/更新的请求体，字段与 schema.sql 的 activities 表一一对应。"""
    title: str
    description: Optional[str] = ""
    organizer: Optional[str] = ""
    type: Optional[str] = ""          # 讲座/竞赛/文体...
    tags: Optional[str] = ""          # 逗号分隔
    location: Optional[str] = ""
    start_time: Optional[str] = ""    # ISO8601
    end_time: Optional[str] = ""
    signup_deadline: Optional[str] = ""
    max_participants: Optional[int] = None
    has_ticket: int = 0               # 0/1 是否发电子票
    zongce_score: Optional[str] = ""  # 综测加分说明
    status: Optional[str] = "draft"   # draft/published/cancelled


@router.post("")
def create_activity(body: ActIn):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO activities
           (title, description, organizer, type, tags, location,
            start_time, end_time, signup_deadline, max_participants,
            has_ticket, zongce_score, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (body.title, body.description, body.organizer, body.type, body.tags, body.location,
         body.start_time, body.end_time, body.signup_deadline, body.max_participants,
         body.has_ticket, body.zongce_score, body.status),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM activities WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict_row(row)


@router.get("")
def list_activities(
    type: Optional[str] = None,
    tags: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """活动列表：支持类型/标签/关键词筛选 + 分页。"""
    where, params = [], []
    if type:
        where.append("type = ?")
        params.append(type)
    if tags:
        where.append("tags LIKE ?")
        params.append(f"%{tags}%")
    if keyword:
        where.append("(title LIKE ? OR description LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%"]

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    total = conn.execute(f"SELECT COUNT(*) AS c FROM activities{clause}", params).fetchone()["c"]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT * FROM activities{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    conn.close()
    return {"items": [dict_row(r) for r in rows], "total": total}


@router.get("/{activity_id}")
def get_activity(activity_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM activities WHERE id=?", (activity_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    return dict_row(row)


@router.put("/{activity_id}")
def update_activity(activity_id: int, body: ActIn):
    # TODO(成员2 第3周)：变更后触发推送（调用通知接口），见接口文档「变更后触发推送」
    conn = get_conn()
    cur = conn.execute("SELECT status FROM activities WHERE id=?", (activity_id,)).fetchone()
    if cur is None:
        conn.close()
        raise HTTPException(status_code=404, detail="活动不存在")
    # 状态只能前进：draft -> published -> cancelled，不能后退
    RANK = {"draft": 0, "published": 1, "cancelled": 2}
    old = cur["status"] or "draft"
    if RANK.get(body.status, 0) < RANK.get(old, 0):
        conn.close()
        raise HTTPException(status_code=400, detail="状态只能前进：draft → published → cancelled")
    conn.execute(
        """UPDATE activities SET
           title=?, description=?, organizer=?, type=?, tags=?, location=?,
           start_time=?, end_time=?, signup_deadline=?, max_participants=?,
           has_ticket=?, zongce_score=?, status=?
           WHERE id=?""",
        (body.title, body.description, body.organizer, body.type, body.tags, body.location,
         body.start_time, body.end_time, body.signup_deadline, body.max_participants,
         body.has_ticket, body.zongce_score, body.status, activity_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM activities WHERE id=?", (activity_id,)).fetchone()
    conn.close()
    return dict_row(row)
