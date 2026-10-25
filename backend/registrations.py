"""报名接口：列表 / 提交 / 我的报名 / 详情 / 取消。"""
from __future__ import annotations

import json
import os
import sqlite3

import requests
from fastapi import APIRouter, Depends

import db
from auth import get_current_user, require_role
from common import deadline_passed, fail, ok, to_iso
from schemas import RegistrationPayload

router = APIRouter(prefix="/api", tags=["registrations"])

# POD-1 通知接口：报名成功时内部 HTTP 调用写入，不直接连 notifications 表
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
NOTIFY_TIMEOUT = 5


def _notify_signup_success(activity_id: int, activity_title: str, user_ids: list[int]) -> None:
    """报名成功后调 POD-1 的 POST /api/notifications，给全队每个队员各写一条「报名提醒」。

    尽力而为：某条通知失败不影响报名结果，仅静默忽略。
    """
    content = f"您已成功报名活动《{activity_title}》，请关注后续通知。"
    for uid in user_ids:
        try:
            requests.post(
                f"{BACKEND_BASE_URL}/api/notifications",
                json={
                    "user_id": uid,
                    "activity_id": activity_id,
                    "type": "报名提醒",
                    "content": content,
                },
                timeout=NOTIFY_TIMEOUT,
            )
        except Exception:  # 连接失败 / 超时等：不阻断报名流程
            pass


def _activity_or_404(activity_id: int) -> dict:
    row = db.query_one("SELECT * FROM activities WHERE id = ?", (activity_id,))
    if row is None:
        fail(404, "活动不存在")
    return dict(row)


@router.get("/activities/{id}/registrations")
def list_registrations(
    id: int,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(require_role("ORGANIZER")),
):
    """发布者查看该活动全部报名清单。"""
    activity = _activity_or_404(id)
    if activity["organizer_id"] != user["id"]:
        fail(403, "无权限访问：仅该活动发布者可操作")

    total = db.query_one("SELECT COUNT(*) AS c FROM registrations WHERE activity_id = ?", (id,))["c"]
    rows = db.query_all(
        "SELECT * FROM registrations WHERE activity_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
        (id, page_size, (page - 1) * page_size),
    )
    items = [
        {
            "registration_id": r["id"],
            "user_id": r["user_id"],
            "registered_at": to_iso(r["registered_at"]),
            "extra_fields": json.loads(r["extra_fields"] or "{}"),
        }
        for r in rows
    ]
    return ok({"items": items, "total": total})


@router.post("/activities/{id}/registrations")
def submit_registration(
    id: int,
    payload: RegistrationPayload,
    user: dict = Depends(require_role("STUDENT")),
):
    """队长提交整支队伍报名，写入 registrations + registration_members。"""
    activity = _activity_or_404(id)

    if activity["status"] != "published":
        fail(400, "活动未开放报名")
    if deadline_passed(activity["signup_deadline"]):
        fail(400, "报名已截止")
    if activity["max_participants"] is not None:
        count = db.query_one("SELECT COUNT(*) AS c FROM registrations WHERE activity_id = ?", (id,))["c"]
        if count >= activity["max_participants"]:
            fail(400, "报名已满")

    form = db.query_one("SELECT * FROM forms WHERE activity_id = ?", (id,))
    if form is None:
        fail(404, "该活动未创建报名表单")
    team_schema = json.loads(form["form_team_schema"] or "[]")
    member_schema = json.loads(form["form_member_schema"] or "[]")
    min_m = activity["min_team_member"]
    max_m = activity["max_team_member"]

    ef = payload.extra_fields
    members = ef.members
    if not members:
        fail(400, "队员列表不能为空")
    if not (min_m <= len(members) <= max_m):
        fail(400, f"报名人数须为 {min_m}–{max_m} 人（含队长）")
    for i, m in enumerate(members):
        expected = "captain" if i == 0 else "member"
        if m.role != expected:
            fail(400, "队长须为第一位报名人")

    # 队长学号须与登录用户一致
    captain_sid = str(members[0].member_extra.get("student_id", "")).strip()
    if captain_sid != (user["student_id"] or "").strip():
        fail(400, "队长学号与登录用户不一致")

    # 必填校验（对照表单模板）
    for f in team_schema:
        if f["required"]:
            v = ef.team_extra.get(f["field_key"])
            if v is None or (isinstance(v, str) and not v.strip()):
                fail(400, f"请填写队伍信息的“{f['label']}”")
    student_ids: list[str] = []
    for i, m in enumerate(members):
        for f in member_schema:
            if f["required"]:
                v = m.member_extra.get(f["field_key"])
                if v is None or (isinstance(v, str) and not v.strip()):
                    fail(400, f"请填写第 {i + 1} 位报名人的“{f['label']}”")
        student_ids.append(str(m.member_extra.get("student_id", "")).strip())

    if len(set(student_ids)) != len(student_ids):
        fail(400, "队员学号重复")

    # 学号有效性 → user_id
    user_ids: list[int] = []
    for sid in student_ids:
        urow = db.query_one("SELECT id FROM users WHERE student_id = ?", (sid,))
        if urow is None:
            fail(400, "该同学未注册")
        user_ids.append(urow["id"])

    # 重复报名：任一队员已在本活动其他报名单
    for uid in user_ids:
        dup = db.query_one(
            "SELECT id FROM registration_members WHERE activity_id = ? AND user_id = ?",
            (id, uid),
        )
        if dup:
            fail(409, "该成员已报名本活动")

    extra = {
        "team_extra": ef.team_extra,
        "members": [{"role": m.role, "member_extra": m.member_extra} for m in members],
    }
    try:
        with db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO registrations (activity_id, user_id, form_id, extra_fields) "
                "VALUES (?, ?, ?, ?)",
                (id, user["id"], form["id"], json.dumps(extra, ensure_ascii=False)),
            )
            reg_id = cur.lastrowid
            for idx, uid in enumerate(user_ids):
                conn.execute(
                    "INSERT INTO registration_members (registration_id, user_id, role, activity_id) "
                    "VALUES (?, ?, ?, ?)",
                    (reg_id, uid, "captain" if idx == 0 else "member", id),
                )
    except sqlite3.IntegrityError:
        fail(409, "该成员已报名本活动")

    _notify_signup_success(id, activity["title"], user_ids)
    return ok({"registration_id": reg_id})


@router.get("/users/{id}/registrations")
def my_registrations(
    id: int,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(require_role("STUDENT")),
):
    """查看【我】报名的比赛列表（队长 + 队员身份都覆盖）。"""
    if id != user["id"]:
        fail(403, "无权查看他人报名记录")
    if db.query_one("SELECT id FROM users WHERE id = ?", (id,)) is None:
        fail(404, "用户不存在")

    total = db.query_one("SELECT COUNT(*) AS c FROM registration_members WHERE user_id = ?", (id,))["c"]
    rows = db.query_all(
        """SELECT r.id AS registration_id, a.title AS activity_name, a.status AS activity_status,
                  r.registered_at AS registered_at, rm.role AS my_role
           FROM registration_members rm
           JOIN registrations r ON r.id = rm.registration_id
           JOIN activities a ON a.id = r.activity_id
           WHERE rm.user_id = ?
           ORDER BY r.registered_at DESC, r.id DESC LIMIT ? OFFSET ?""",
        (id, page_size, (page - 1) * page_size),
    )
    items = [
        {
            "registration_id": r["registration_id"],
            "activity_name": r["activity_name"],
            "activity_status": r["activity_status"],
            "registered_at": to_iso(r["registered_at"]),
            "my_role": r["my_role"],
        }
        for r in rows
    ]
    return ok({"items": items, "total": total})


@router.get("/registrations/{registration_id}")
def get_registration(registration_id: int, user: dict = Depends(require_role("STUDENT"))):
    """查看报名表填报详情（队长或任一队员）。"""
    reg = db.query_one("SELECT * FROM registrations WHERE id = ?", (registration_id,))
    if reg is None:
        fail(404, "报名记录不存在")
    mem = db.query_one(
        "SELECT role FROM registration_members WHERE registration_id = ? AND user_id = ?",
        (registration_id, user["id"]),
    )
    if mem is None:
        fail(403, "无权限查看该报名详情")

    activity = _activity_or_404(reg["activity_id"])
    form = db.query_one("SELECT * FROM forms WHERE id = ?", (reg["form_id"],))
    if form is None:
        fail(404, "表单不存在")

    return ok({
        "registration_id": reg["id"],
        "activity_id": reg["activity_id"],
        "form_id": reg["form_id"],
        "activity_name": activity["title"],
        "activity_status": activity["status"],
        "registered_at": to_iso(reg["registered_at"]),
        "my_role": mem["role"],
        "form": {
            "form_team_schema": json.loads(form["form_team_schema"] or "[]"),
            "form_member_schema": json.loads(form["form_member_schema"] or "[]"),
            "min_team_member": activity["min_team_member"],
            "max_team_member": activity["max_team_member"],
        },
        "extra_fields": json.loads(reg["extra_fields"] or "{}"),
    })


@router.delete("/registrations/{registration_id}")
def cancel_registration(registration_id: int, user: dict = Depends(require_role("STUDENT"))):
    """队长取消整队报名（级联删除 registration_members）。"""
    reg = db.query_one("SELECT * FROM registrations WHERE id = ?", (registration_id,))
    if reg is None:
        fail(404, "报名记录不存在")
    if reg["user_id"] != user["id"]:
        fail(403, "仅队长可取消报名")

    activity = _activity_or_404(reg["activity_id"])
    if deadline_passed(activity["signup_deadline"]) or activity["status"] == "finished":
        fail(400, "活动已截止/已结束，禁止取消报名")

    # 已签到/已发凭证不能取消（只读 credentials 表）
    member_ids = {reg["user_id"]} | {
        r["user_id"]
        for r in db.query_all(
            "SELECT user_id FROM registration_members WHERE registration_id = ?", (registration_id,)
        )
    }
    placeholders = ",".join("?" * len(member_ids))
    cred = db.query_one(
        f"SELECT id FROM credentials WHERE activity_id = ? AND user_id IN ({placeholders}) "
        f"AND (status IN ('issued', 'confirmed', 'signed') OR checkin_time IS NOT NULL) LIMIT 1",
        (reg["activity_id"], *member_ids),
    )
    if cred:
        fail(409, "已签到或已发凭证，请线下处理")

    db.execute("DELETE FROM registrations WHERE id = ?", (registration_id,))
    return ok(None)
