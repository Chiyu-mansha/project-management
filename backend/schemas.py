"""Pydantic 请求体模型 + 表单 schema 校验。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from common import fail

# 队员表单固定字段（硬性要求，不能删除/改 type/取消必填）
FIXED_MEMBER_FIELDS = (
    {"field_key": "student_id", "label": "学号", "type": "text", "required": True},
    {"field_key": "name", "label": "姓名", "type": "text", "required": True},
)


class FieldDef(BaseModel):
    field_key: str
    label: str
    type: Literal["text", "textarea"]
    required: bool


class FormPayload(BaseModel):
    form_team_schema: list[FieldDef] = []
    form_member_schema: list[FieldDef] = []


class MemberEntry(BaseModel):
    role: Literal["captain", "member"]
    member_extra: dict


class ExtraFields(BaseModel):
    team_extra: dict
    members: list[MemberEntry]


class RegistrationPayload(BaseModel):
    extra_fields: ExtraFields


def _validate_schema(schema: list[FieldDef], is_member: bool) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for field in schema:
        if not field.field_key.strip():
            fail(400, "字段标识 field_key 不能为空")
        if field.field_key in seen:
            fail(400, "同一表单内 field_key 不能重复")
        if not field.label.strip():
            fail(400, "题干 label 不能为空")
        seen.add(field.field_key)
        out.append({
            "field_key": field.field_key,
            "label": field.label,
            "type": field.type,
            "required": field.required,
        })
    if is_member:
        for fixed in FIXED_MEMBER_FIELDS:
            found = next((f for f in out if f["field_key"] == fixed["field_key"]), None)
            if found is None or found["type"] != fixed["type"] or found["required"] is not True:
                fail(400, f"队员表单必须包含固定字段 {fixed['field_key']}（type=text、required=true）")
    return out


def validate_form_payload(payload: FormPayload) -> dict:
    team = _validate_schema(payload.form_team_schema, is_member=False)
    member = _validate_schema(payload.form_member_schema, is_member=True)
    return {"form_team_schema": team, "form_member_schema": member}
