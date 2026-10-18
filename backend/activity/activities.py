"""活动发布管理：完整 CRUD（成员2 的域）。

接口（前缀 /api/activities）：
- POST   /api/activities        发布活动/竞赛
- GET    /api/activities        列表（类型/标签/关键词筛选 + 分页）
- GET    /api/activities/{id}   详情
- PUT    /api/activities/{id}   编辑/变更
"""
import os
from datetime import datetime
from typing import Optional

import requests
from fastapi import APIRouter
from pydantic import BaseModel, model_validator

from common import fail, ok
from database import get_conn, dict_row

router = APIRouter(prefix="/api/activities", tags=["activities"])

GATEWAY_URL = os.getenv("AI_GATEWAY_URL", "http://127.0.0.1:8100").rstrip("/")


class ActIn(BaseModel):
    """创建/更新的请求体，字段与 schema.sql 的 activities 表一一对应。"""
    title: str
    type: Optional[str] = ""                  # 学科类/文体类/科创竞赛/社会实践
    organizer_id: Optional[int] = None        # 发布人 organizers.id（MVP 先可空）
    start_time: Optional[str] = ""            # ISO8601
    end_time: Optional[str] = ""
    location: Optional[str] = ""
    description: Optional[str] = ""           # 活动介绍(推文生成基础信息)
    requirements: Optional[str] = ""          # 报名条件
    tags: Optional[str] = ""                  # 逗号分隔
    has_ticket: int = 1                       # 1/0 是否发电子票
    comprehensive_score: int = 0              # 0/1 能否加综合素养积分
    conduct_score: Optional[float] = None     # 操行分(具体分值)
    innovation_score: Optional[float] = None  # 创新分(具体分值)
    signup_deadline: Optional[str] = ""       # 报名截止
    min_team_member: int = 1                  # 最少人数(含队长)
    max_team_member: int = 1                  # 最多人数(含队长)
    max_participants: Optional[int] = None    # 报名上限(队伍数)
    status: Optional[str] = "draft"           # draft/published/ongoing/finished/cancelled

    @model_validator(mode="after")
    def _clear_scores_without_comprehensive(self):
        """不提供综测加分(comprehensive_score=0)时，操行分/创新分必须为空。"""
        if self.comprehensive_score != 1:
            self.conduct_score = None
            self.innovation_score = None
        return self


# 状态机：draft -> published、-> cancelled 手动；ongoing/finished 由时间自动流转；cancelled 终态
ALLOWED = {
    "draft": {"draft", "published", "cancelled"},
    "published": {"published", "cancelled"},
    "ongoing": {"ongoing", "cancelled"},
    "finished": {"finished"},
    "cancelled": {"cancelled"},
}


def _auto_transition(conn):
    """按时间自动流转：published 已到开始时间 -> ongoing；ongoing 已到结束时间 -> finished。"""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "UPDATE activities SET status='ongoing' WHERE status='published' "
        "AND start_time IS NOT NULL AND start_time != '' AND start_time <= ?",
        (now,),
    )
    conn.execute(
        "UPDATE activities SET status='finished' WHERE status='ongoing' "
        "AND end_time IS NOT NULL AND end_time != '' AND end_time <= ?",
        (now,),
    )
    conn.commit()

_COLUMNS = (
    "title, type, organizer_id, start_time, end_time, location, description, "
    "requirements, tags, has_ticket, comprehensive_score, conduct_score, innovation_score, "
    "signup_deadline, min_team_member, max_team_member, max_participants, status"
)


@router.post("")
def create_activity(body: ActIn):
    conn = get_conn()
    cur = conn.execute(
        f"""INSERT INTO activities ({_COLUMNS})
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (body.title, body.type, body.organizer_id, body.start_time, body.end_time, body.location,
         body.description, body.requirements, body.tags, body.has_ticket,
         body.comprehensive_score, body.conduct_score, body.innovation_score,
         body.signup_deadline, body.min_team_member, body.max_team_member,
         body.max_participants, body.status),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM activities WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return ok(dict_row(row))


@router.get("")
def list_activities(
    type: Optional[str] = None,
    tags: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """活动列表：支持类型/标签/关键词/状态筛选 + 分页。"""
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
    if status:
        where.append("status = ?")
        params.append(status)
    else:
        # 默认隐藏已取消的活动（想查看时传 status=cancelled）
        where.append("status != 'cancelled'")

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    _auto_transition(conn)
    total = conn.execute(f"SELECT COUNT(*) AS c FROM activities{clause}", params).fetchone()["c"]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT * FROM activities{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    conn.close()
    return ok({"items": [dict_row(r) for r in rows], "total": total})


@router.get("/{activity_id}")
def get_activity(activity_id: int):
    conn = get_conn()
    _auto_transition(conn)
    row = conn.execute("SELECT * FROM activities WHERE id=?", (activity_id,)).fetchone()
    conn.close()
    if row is None:
        fail(404, "活动不存在")
    return ok(dict_row(row))


@router.put("/{activity_id}")
def update_activity(activity_id: int, body: ActIn):
    # TODO(成员2 第3周)：变更后触发推送（调用通知接口），见接口文档「变更后触发推送」
    conn = get_conn()
    cur = conn.execute("SELECT status FROM activities WHERE id=?", (activity_id,)).fetchone()
    if cur is None:
        conn.close()
        fail(404, "活动不存在")
    # 状态机校验：只能按 draft -> published -> ongoing -> finished 前进，cancelled 为终态
    old = cur["status"] or "draft"
    if body.status not in ALLOWED.get(old, {old}):
        conn.close()
        fail(400, f"状态不能从 {old} 变为 {body.status}")
    conn.execute(
        f"""UPDATE activities SET
            title=?, type=?, organizer_id=?, start_time=?, end_time=?, location=?,
            description=?, requirements=?, tags=?, has_ticket=?, comprehensive_score=?,
            conduct_score=?, innovation_score=?, signup_deadline=?, min_team_member=?,
            max_team_member=?, max_participants=?, status=?
            WHERE id=?""",
        (body.title, body.type, body.organizer_id, body.start_time, body.end_time, body.location,
         body.description, body.requirements, body.tags, body.has_ticket,
         body.comprehensive_score, body.conduct_score, body.innovation_score,
         body.signup_deadline, body.min_team_member, body.max_team_member,
         body.max_participants, body.status, activity_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM activities WHERE id=?", (activity_id,)).fetchone()
    conn.close()
    return ok(dict_row(row))


class ArticleGenReq(BaseModel):
    style: str = "简约"   # 简约 / 活泼 / 正式


@router.post("/{activity_id}/generate-article")
def generate_article(activity_id: int, body: ArticleGenReq):
    """AI 推文生成：查活动 -> 调网关 generate-article -> 返回推文 Markdown。"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM activities WHERE id=?", (activity_id,)).fetchone()
    if row is None:
        conn.close()
        fail(404, "活动不存在")
    act = dict_row(row)
    # 补充主办方名称（网关拼 prompt 用 organizer 字段显示）
    if act.get("organizer_id"):
        org = conn.execute("SELECT name, organization FROM organizers WHERE id=?", (act["organizer_id"],)).fetchone()
        if org:
            act["organizer"] = org["name"] + (f"（{org['organization']}）" if org["organization"] else "")
    conn.close()
    # 综测加分文案（网关拼 prompt 用 zongce_score 字段显示）
    parts = []
    if act.get("comprehensive_score"):
        parts.append("综合素养积分")
    if act.get("conduct_score"):
        parts.append(f"操行分 +{act['conduct_score']}")
    if act.get("innovation_score"):
        parts.append(f"创新分 +{act['innovation_score']}")
    act["zongce_score"] = "、".join(parts) if parts else ""
    try:
        resp = requests.post(
            f"{GATEWAY_URL}/api/ai/generate-article",
            json={"style": body.style, "activity": act, "activity_id": activity_id},
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json().get("content", "")
    except Exception:
        # 网关不可用，降级返回活动基础信息
        content = (
            f"> 网关暂不可用，已降级。请手动为「{act.get('title', '')}」编写推文。\n\n"
            f"- 时间：{act.get('start_time', '') or '待定'}\n"
            f"- 地点：{act.get('location', '') or '待定'}"
        )
    return ok({"content": content})
