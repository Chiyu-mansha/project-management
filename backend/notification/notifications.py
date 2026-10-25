"""通知推送模块（POD-1 / member-1）

接口（接口文档 v1.0 定稿）：
- GET  /api/notifications                   我的通知列表（分页）
- POST /api/notifications                   创建通知（POD-2 报名成功时内部调用）
- PUT  /api/notifications/{id}/read         标记已读
- POST /api/notifications/check-deadlines   截止前 24h 预警扫描（MVP 手动触发，第 4 周加定时任务）

返回统一为 {"code":0,"data":...}，与接口文档通用约定一致。
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

ALLOWED_TYPES = {"报名提醒", "截止预警", "变更通知", "开奖提醒", "凭证通知"}


class NotificationCreateReq(BaseModel):
    user_id: int
    activity_id: Optional[int] = None
    type: str
    content: str


@router.get("")
def list_my_notifications(
    user_id: int = Query(..., description="当前用户 id（MVP 简化，等 POD-2 认证上线后从 token 取）"),
    page: int = 1,
    page_size: int = 20,
):
    offset = (page - 1) * page_size
    rows = db.query_all(
        """
        SELECT id, user_id, activity_id, type, content, is_read, sent_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY sent_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, page_size, offset),
    )
    total_row = db.query_one(
        "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ?",
        (user_id,),
    )
    total = total_row["n"] if total_row else 0
    return {"code": 0, "data": {"items": [dict(r) for r in rows], "total": total}}


@router.post("")
def create_notification(req: NotificationCreateReq):
    if req.type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"type 必须为 {ALLOWED_TYPES} 之一")
    db.execute(
        """
        INSERT INTO notifications (user_id, activity_id, type, content, is_read)
        VALUES (?, ?, ?, ?, 0)
        """,
        (req.user_id, req.activity_id, req.type, req.content),
    )
    row = db.query_one(
        """
        SELECT id, user_id, activity_id, type, content, is_read, sent_at
        FROM notifications
        WHERE user_id = ? ORDER BY id DESC LIMIT 1
        """,
        (req.user_id,),
    )
    return {"code": 0, "data": dict(row) if row else {}}


@router.put("/{notification_id}/read")
def mark_as_read(notification_id: int):
    existing = db.query_one(
        "SELECT id FROM notifications WHERE id = ?",
        (notification_id,),
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="通知不存在")

    db.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ?",
        (notification_id,),
    )
    row = db.query_one(
        """
        SELECT id, user_id, activity_id, type, content, is_read, sent_at
        FROM notifications WHERE id = ?
        """,
        (notification_id,),
    )
    return {"code": 0, "data": dict(row)}


# ---------- 截止前 24h 预警 ----------
# 设计说明（做法 B：业务逻辑与触发方式分离）：
#   - _do_check_deadlines() 是纯业务逻辑，无 HTTP 依赖，第 4 周定时任务可直接 import 调用
#   - /check-deadlines 是 HTTP 包装，MVP 阶段供手动触发 / 测试
#   - 未来加 APScheduler 时，只需 scheduler.add_job(_do_check_deadlines, ...)，本文件不动

def _do_check_deadlines() -> int:
    """扫描所有 published 活动，为已报名学生生成 24h 截止预警通知，返回新生成条数。

    幂等：同一 (user_id, activity_id, content) 已存在则跳过，重复触发不会重复插入。
    """
    rows = db.query_all(
        """
        SELECT a.id AS activity_id, a.title, r.user_id
        FROM activities a
        JOIN registrations r ON r.activity_id = a.id
        WHERE a.status = 'published'
          AND a.signup_deadline IS NOT NULL
          AND datetime(a.signup_deadline) <= datetime('now', '+24 hours')
          AND datetime(a.signup_deadline) > datetime('now')
        """
    )
    created = 0
    for r in rows:
        content = f"您报名的《{r['title']}》将于 24 小时内截止报名，请及时确认。"
        existing = db.query_one(
            """
            SELECT id FROM notifications
            WHERE user_id = ? AND activity_id = ? AND type = '截止预警' AND content = ?
            """,
            (r["user_id"], r["activity_id"], content),
        )
        if existing:
            continue
        db.execute(
            """
            INSERT INTO notifications (user_id, activity_id, type, content, is_read)
            VALUES (?, ?, '截止预警', ?, 0)
            """,
            (r["user_id"], r["activity_id"], content),
        )
        created += 1
    return created


@router.post("/check-deadlines")
def check_deadlines():
    """手动触发 24h 截止预警扫描。响应：{"code":0, "data":{"created": N}}"""
    return {"code": 0, "data": {"created": _do_check_deadlines()}}