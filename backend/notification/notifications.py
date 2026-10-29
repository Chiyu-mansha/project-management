"""通知推送模块（POD-1 / member-1）

接口（接口文档 v1.0 定稿）：
- GET  /api/notifications                   我的通知列表（分页，需登录）
- GET  /api/notifications/unread-count      获取未读通知数量（需登录）
- POST /api/notifications                   创建通知（供内部调用，无需用户 Token）
- PUT  /api/notifications/{id}/read         标记已读（需登录）
- POST /api/notifications/check-deadlines   截止前 24h 预警扫描（手动触发/定时任务）
- POST /api/notifications/check-lottery     开奖提醒扫描（手动触发/定时任务）
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

import db
from auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

ALLOWED_TYPES = {"报名提醒", "截止预警", "变更通知", "开奖提醒", "凭证通知"}


class NotificationCreateReq(BaseModel):
    user_id: int
    activity_id: Optional[int] = None
    type: str
    content: str


@router.get("")
def list_my_notifications(
    user: dict = Depends(get_current_user),  # 从 Token 解析用户
    page: int = 1,
    page_size: int = 20,
):
    user_id = user["id"]
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


@router.get("/unread-count")
def get_unread_count(user: dict = Depends(get_current_user)):
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND is_read = 0",
        (user["id"],),
    )
    return {"code": 0, "data": {"count": row["n"] if row else 0}}


@router.post("")
def create_notification(req: NotificationCreateReq):
    """内部接口：供 POD-2 报名成功、或系统定时任务调用，不校验用户 Token。"""
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
def mark_as_read(notification_id: int, user: dict = Depends(get_current_user)):
    # 只能标记自己的通知
    existing = db.query_one(
        "SELECT id FROM notifications WHERE id = ? AND user_id = ?",
        (notification_id, user["id"]),
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="通知不存在或无权操作")

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


# ---------- 截止前 24h 预警（供定时任务调用） ----------

def _do_check_deadlines() -> int:
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
    return {"code": 0, "data": {"created": _do_check_deadlines()}}


# ---------- 开奖提醒（供定时任务调用） ----------

def _do_check_lottery() -> int:
    """扫描状态为 finished 的活动，给已报名学生发开奖提醒。"""
    rows = db.query_all(
        """
        SELECT a.id AS activity_id, a.title, r.user_id
        FROM activities a
        JOIN registrations r ON r.activity_id = a.id
        WHERE a.status = 'finished'
        """
    )
    created = 0
    for r in rows:
        content = f"您报名的《{r['title']}》已结束，获奖名单已出炉，请前往活动详情页查看结果！"
        # 去重校验
        existing = db.query_one(
            """
            SELECT id FROM notifications
            WHERE user_id = ? AND activity_id = ? AND type = '开奖提醒'
            """,
            (r["user_id"], r["activity_id"]),
        )
        if existing:
            continue
        
        db.execute(
            """
            INSERT INTO notifications (user_id, activity_id, type, content, is_read)
            VALUES (?, ?, '开奖提醒', ?, 0)
            """,
            (r["user_id"], r["activity_id"], content),
        )
        created += 1
    return created


@router.post("/check-lottery")
def check_lottery():
    """手动触发开奖提醒扫描（方便测试）"""
    return {"code": 0, "data": {"created": _do_check_lottery()}}