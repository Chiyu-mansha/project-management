"""报名表单模板接口：POST/GET/PUT /api/activities/{id}/forms。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends

import db
from auth import get_current_user, require_role
from common import fail, ok, to_iso
from schemas import FormPayload, validate_form_payload

router = APIRouter(prefix="/api/activities", tags=["forms"])


def _activity_or_404(activity_id: int) -> dict:
    row = db.query_one("SELECT * FROM activities WHERE id = ?", (activity_id,))
    if row is None:
        fail(404, "活动不存在")
    return dict(row)


@router.post("/{id}/forms")
def create_form(id: int, payload: FormPayload, user: dict = Depends(require_role("ORGANIZER"))):
    activity = _activity_or_404(id)
    if activity["organizer_id"] != user["id"]:
        fail(403, "无权限访问：仅该活动发布者可操作")
    if db.query_one("SELECT id FROM forms WHERE activity_id = ?", (id,)):
        fail(409, "该活动已存在报名表单")

    data = validate_form_payload(payload)
    form_id = db.execute(
        "INSERT INTO forms (activity_id, organizer_id, form_team_schema, form_member_schema) "
        "VALUES (?, ?, ?, ?)",
        (
            id,
            user["id"],
            json.dumps(data["form_team_schema"], ensure_ascii=False),
            json.dumps(data["form_member_schema"], ensure_ascii=False),
        ),
    )
    return ok({"form_id": form_id})


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
    activity = _activity_or_404(id)
    if activity["organizer_id"] != user["id"]:
        fail(403, "无权限访问：仅该活动发布者可操作")
    row = db.query_one("SELECT id FROM forms WHERE activity_id = ?", (id,))
    if row is None:
        fail(404, "该活动尚未创建报名表单")
    if db.query_one("SELECT id FROM registrations WHERE activity_id = ?", (id,)):
        fail(400, "活动已有报名记录，禁止修改表单")

    data = validate_form_payload(payload)
    db.execute(
        "UPDATE forms SET form_team_schema = ?, form_member_schema = ?, updated_at = datetime('now') "
        "WHERE activity_id = ?",
        (
            json.dumps(data["form_team_schema"], ensure_ascii=False),
            json.dumps(data["form_member_schema"], ensure_ascii=False),
            id,
        ),
    )
    return ok({"form_id": row["id"]})
