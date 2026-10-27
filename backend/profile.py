"""画像接口：GET/PUT /api/users/{id}/profile（仅本人）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import db
from auth import require_role
from common import fail, ok

router = APIRouter(prefix="/api/users", tags=["profile"])


class ProfileBody(BaseModel):
    major: str | None = None
    grade: str | None = None
    interests: str | None = None
    skills: str | None = None
    need_comprehensive_score: int = 0
    need_conduct_score: int = 0
    need_innovation_score: int = 0


def _payload(row) -> dict:
    return {
        "id": row["id"],
        "major": row["major"],
        "grade": row["grade"],
        "interests": row["interests"],
        "skills": row["skills"],
        "need_comprehensive_score": row["need_comprehensive_score"],
        "need_conduct_score": row["need_conduct_score"],
        "need_innovation_score": row["need_innovation_score"],
    }


@router.get("/{id}/profile")
def get_profile(id: int, user: dict = Depends(require_role("STUDENT"))):
    if id != user["id"]:
        fail(403, "无权查看他人画像")
    row = db.query_one("SELECT * FROM users WHERE id = ?", (id,))
    if row is None:
        fail(404, "用户不存在")
    return ok(_payload(row))


@router.put("/{id}/profile")
def update_profile(id: int, body: ProfileBody, user: dict = Depends(require_role("STUDENT"))):
    if id != user["id"]:
        fail(403, "无权修改他人画像")
    if db.query_one("SELECT id FROM users WHERE id = ?", (id,)) is None:
        fail(404, "用户不存在")
    for key in ("need_comprehensive_score", "need_conduct_score", "need_innovation_score"):
        if getattr(body, key) not in (0, 1):
            fail(400, f"{key} 仅允许 0 或 1")

    db.execute(
        "UPDATE users SET major = ?, grade = ?, interests = ?, skills = ?, "
        "need_comprehensive_score = ?, need_conduct_score = ?, need_innovation_score = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (
            body.major, body.grade, body.interests, body.skills,
            body.need_comprehensive_score, body.need_conduct_score, body.need_innovation_score,
            id,
        ),
    )
    return ok(_payload(db.query_one("SELECT * FROM users WHERE id = ?", (id,))))
