"""MVP 临时鉴权：明文 token ``role:id``（如 ``student:5`` / ``organizer:10``）。

TODO(迭代2): 技术负责人交付公共 token 生成/校验后，仅替换 get_current_user 内部实现，
保持返回结构 {id, role, student_id} 不变，8 个业务接口无需改动。
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import db

bearer = HTTPBearer(auto_error=False)


def get_current_user(cred: HTTPAuthorizationCredentials | None = Security(bearer)) -> dict:
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(401, detail={"code": 401, "message": "请先登录"})

    role, sep, id_str = cred.credentials.partition(":")
    role = role.lower()
    if not sep or role not in ("student", "organizer"):
        raise HTTPException(401, detail={"code": 401, "message": "登录凭证无效"})
    try:
        uid = int(id_str)
    except ValueError:
        raise HTTPException(401, detail={"code": 401, "message": "登录凭证无效"})

    if role == "student":
        row = db.query_one("SELECT id, student_id FROM users WHERE id = ?", (uid,))
        if row is None:
            raise HTTPException(401, detail={"code": 401, "message": "用户不存在"})
        return {"id": row["id"], "role": "STUDENT", "student_id": row["student_id"]}

    row = db.query_one("SELECT id FROM organizers WHERE id = ?", (uid,))
    if row is None:
        raise HTTPException(401, detail={"code": 401, "message": "发布者不存在"})
    return {"id": row["id"], "role": "ORGANIZER", "student_id": None}


def require_role(*roles: str):
    """要求当前用户角色 ∈ roles，否则 403。"""

    def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, detail={"code": 403, "message": "无权限访问"})
        return user

    return dep
