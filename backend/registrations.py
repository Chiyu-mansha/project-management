"""报名接口：列表 / 提交 / 我的报名 / 详情 / 取消。"""
from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, Query

import db
from auth import require_role
from common import deadline_passed, fail, ok, to_iso
from schemas import RegistrationPayload

router = APIRouter(prefix="/api", tags=["registrations"])


def _activity_or_404(activity_id: int, conn=None) -> dict:
    sql = "SELECT * FROM activities WHERE id = ?"
    row = (conn.execute(sql, (activity_id,)).fetchone() if conn is not None
           else db.query_one(sql, (activity_id,)))
    if row is None:
        fail(404, "活动不存在")
    return dict(row)


@router.get("/activities/{id}/registrations")
def list_registrations(
    id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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
    try:
        with db.transaction(immediate=True) as conn:
            return _submit_registration(id, payload, user, conn)
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            fail(409, "该成员已报名本活动")
        raise


def _submit_registration(id: int, payload: RegistrationPayload, user: dict, conn):
    # Lock before reading capacity/status/template, not only before INSERT.
    activity = _activity_or_404(id, conn)

    if activity["status"] != "published":
        fail(400, "活动未开放报名")
    if deadline_passed(activity["signup_deadline"]):
        fail(400, "报名已截止")
    if activity["max_participants"] is not None:
        count = conn.execute("SELECT COUNT(*) AS c FROM registrations WHERE activity_id = ?", (id,)).fetchone()["c"]
        if count >= activity["max_participants"]:
            fail(400, "报名已满")

    form = conn.execute("SELECT * FROM forms WHERE activity_id = ?", (id,)).fetchone()
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
        urow = conn.execute("SELECT id FROM users WHERE student_id = ?", (sid,)).fetchone()
        if urow is None:
            fail(400, "该同学未注册")
        user_ids.append(urow["id"])

    # 重复报名：任一队员已在本活动其他报名单
    for uid in user_ids:
        dup = conn.execute(
            "SELECT id FROM registration_members WHERE activity_id = ? AND user_id = ?",
            (id, uid),
        ).fetchone()
        if dup:
            fail(409, "该成员已报名本活动")

    extra = {
        "team_extra": ef.team_extra,
        "members": [{"role": m.role, "member_extra": m.member_extra} for m in members],
    }
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

    return ok({"registration_id": reg_id})


@router.get("/users/{id}/registrations")
def my_registrations(
    id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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
    with db.transaction(immediate=True) as conn:
        return _cancel_registration(registration_id, user, conn)


def _cancel_registration(registration_id: int, user: dict, conn):
    reg = conn.execute("SELECT * FROM registrations WHERE id = ?", (registration_id,)).fetchone()
    if reg is None:
        fail(404, "报名记录不存在")
    if reg["user_id"] != user["id"]:
        fail(403, "仅队长可取消报名")

    activity = _activity_or_404(reg["activity_id"], conn)
    if deadline_passed(activity["signup_deadline"]) or activity["status"] == "finished":
        fail(400, "活动已截止/已结束，禁止取消报名")

    # 已签到/已发凭证不能取消（只读 credentials 表）
    member_ids = {reg["user_id"]} | {
        r["user_id"]
        for r in conn.execute(
            "SELECT user_id FROM registration_members WHERE registration_id = ?", (registration_id,)
        ).fetchall()
    }
    placeholders = ",".join("?" * len(member_ids))
    cred = conn.execute(
        f"SELECT id FROM credentials WHERE activity_id = ? AND user_id IN ({placeholders}) "
        f"AND (status IN ('issued', 'confirmed', 'signed') OR checkin_time IS NOT NULL) LIMIT 1",
        (reg["activity_id"], *member_ids),
    ).fetchone()
    if cred:
        fail(409, "已签到或已发凭证，请线下处理")

    conn.execute("DELETE FROM registrations WHERE id = ?", (registration_id,))
    return ok(None)
