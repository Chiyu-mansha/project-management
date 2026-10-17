"""报名表单模板接口：POST/GET/PUT /api/activities/{id}/forms。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends

import db
from auth import get_current_user, require_role
from common import fail, ok, to_iso
from schemas import FormPayload, validate_form_payload

router = APIRouter(prefix="/api/activities", tags=["forms"])


def _activity_or_404(activity_id: int, conn=None) -> dict:
    sql = "SELECT * FROM activities WHERE id = ?"
    row = (conn.execute(sql, (activity_id,)).fetchone() if conn is not None
           else db.query_one(sql, (activity_id,)))
    if row is None:
        fail(404, "活动不存在")
    return dict(row)


@router.post("/{id}/forms")
def create_form(id: int, payload: FormPayload, user: dict = Depends(require_role("ORGANIZER"))):
    with db.transaction(immediate=True) as conn:
        return _create_form(id, payload, user, conn)


def _create_form(id: int, payload: FormPayload, user: dict, conn):
    activity = _activity_or_404(id, conn)
    if activity["organizer_id"] != user["id"]:
        fail(403, "无权限访问：仅该活动发布者可操作")
    if conn.execute("SELECT id FROM forms WHERE activity_id = ?", (id,)).fetchone():
        fail(409, "该活动已存在报名表单")

    data = validate_form_payload(payload)
    cur = conn.execute(
        "INSERT INTO forms (activity_id, organizer_id, form_team_schema, form_member_schema) "
        "VALUES (?, ?, ?, ?)",
        (
            id,
            user["id"],
            json.dumps(data["form_team_schema"], ensure_ascii=False),
            json.dumps(data["form_member_schema"], ensure_ascii=False),
        ),
    )
    return ok({"form_id": cur.lastrowid})


@router.get("/{id}/forms")
def get_form(id: int, user: dict = Depends(get_current_user)):
    activity = _activity_or_404(id)
    row = db.query_one("SELECT * FROM forms WHERE activity_id = ?", (id,))
    if row is None:
        fail(404, "该活动尚未创建报名表单")

    return ok({
        "form_id": row["id"],
        "organizer_id": row["organizer_id"],
        "form_team_schema": json.loads(row["form_team_schema"] or "[]"),
        "form_member_schema": json.loads(row["form_member_schema"] or "[]"),
        "min_team_member": activity["min_team_member"],
        "max_team_member": activity["max_team_member"],
        "created_at": to_iso(row["created_at"]),
    })


@router.put("/{id}/forms")
def update_form(id: int, payload: FormPayload, user: dict = Depends(require_role("ORGANIZER"))):
    with db.transaction(immediate=True) as conn:
        return _update_form(id, payload, user, conn)


def _update_form(id: int, payload: FormPayload, user: dict, conn):
    activity = _activity_or_404(id, conn)
    if activity["organizer_id"] != user["id"]:
        fail(403, "无权限访问：仅该活动发布者可操作")
    row = conn.execute("SELECT id FROM forms WHERE activity_id = ?", (id,)).fetchone()
    if row is None:
        fail(404, "该活动尚未创建报名表单")
    if conn.execute("SELECT id FROM registrations WHERE activity_id = ?", (id,)).fetchone():
        fail(400, "活动已有报名记录，禁止修改表单")

    data = validate_form_payload(payload)
    conn.execute(
        "UPDATE forms SET form_team_schema = ?, form_member_schema = ?, updated_at = datetime('now') "
        "WHERE activity_id = ?",
        (
            json.dumps(data["form_team_schema"], ensure_ascii=False),
            json.dumps(data["form_member_schema"], ensure_ascii=False),
            id,
        ),
    )
    return ok({"form_id": row["id"]})
