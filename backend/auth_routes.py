"""认证接口：POST /api/auth/register、POST /api/auth/login（按 role 分叉）。

学生 → users 表（学号 + 密码），发布者 → organizers 表（工号 + 密码）。
MVP 简单 token 沿用明文 role:id（如 student:1），迭代 2 由技术负责人更换正式 token。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

import db
from common import fail, ok

router = APIRouter(prefix="/api/auth", tags=["auth"])

_PBKDF2_ROUNDS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ROUNDS
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        new = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(rounds)
        ).hex()
        return hmac.compare_digest(new, digest)
    except Exception:
        return False


class RegisterBody(BaseModel):
    role: Literal["student", "organizer"]
    password: str
    name: str
    # 学生
    student_id: str | None = None
    major: str | None = None
    grade: str | None = None
    # 发布者
    account: str | None = None
    organization: str | None = None


class LoginBody(BaseModel):
    role: Literal["student", "organizer"]
    account: str  # 学生=学号，发布者=工号
    password: str


@router.post("/register")
def register(body: RegisterBody):
    if not body.password:
        fail(400, "密码不能为空")
    if not body.name.strip():
        fail(400, "姓名不能为空")

    if body.role == "student":
        sid = (body.student_id or "").strip()
        if not sid:
            fail(400, "学号不能为空")
        if db.query_one("SELECT id FROM users WHERE student_id = ?", (sid,)):
            fail(409, "该学号已注册")
        uid = db.execute(
            "INSERT INTO users (password_hash, name, student_id, major, grade) VALUES (?, ?, ?, ?, ?)",
            (hash_password(body.password), body.name.strip(), sid, body.major, body.grade),
        )
        return ok({"id": uid, "role": "student"})

    account = (body.account or "").strip()
    if not account:
        fail(400, "工号不能为空")
    if db.query_one("SELECT id FROM organizers WHERE account = ?", (account,)):
        fail(409, "该工号已注册")
    oid = db.execute(
        "INSERT INTO organizers (account, password_hash, name, organization) VALUES (?, ?, ?, ?)",
        (account, hash_password(body.password), body.name.strip(), body.organization),
    )
    return ok({"id": oid, "role": "organizer"})


@router.post("/login")
def login(body: LoginBody):
    account = (body.account or "").strip()
    if not account or not body.password:
        fail(400, "账号和密码不能为空")

    if body.role == "student":
        row = db.query_one("SELECT id, password_hash FROM users WHERE student_id = ?", (account,))
        if row is None or not verify_password(body.password, row["password_hash"]):
            fail(401, "学号或密码错误")
        return ok({"token": f"student:{row['id']}", "role": "student", "id": row["id"]})

    row = db.query_one("SELECT id, password_hash FROM organizers WHERE account = ?", (account,))
    if row is None or not verify_password(body.password, row["password_hash"]):
        fail(401, "工号或密码错误")
    return ok({"token": f"organizer:{row['id']}", "role": "organizer", "id": row["id"]})
