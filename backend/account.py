"""账号管理接口：多账号列表 / 基本信息 / 修改密码 / 头像 / 切换账号。

放在 /api/account 下，学生与发布者通用：
- 学生账号来自 users 表（账号=学号），发布者账号来自 organizers 表（账号=工号）。
- 关联方式：同一姓名即视为同一个人，用于展示「我名下的多个账号」与账号切换。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import db
from auth import get_current_user
from auth_routes import hash_password, verify_password
from common import fail, ok

router = APIRouter(prefix="/api/account", tags=["account"])


def _role_upper(role: str | None) -> str:
    r = (role or "").strip().upper()
    if r in ("STUDENT", "S"):
        return "STUDENT"
    if r in ("ORGANIZER", "ORGANISER", "O", "PUBLISHER"):
        return "ORGANIZER"
    low = (role or "").strip().lower()
    if low == "student":
        return "STUDENT"
    if low == "organizer":
        return "ORGANIZER"
    fail(400, "角色仅支持 student / organizer")
    return "STUDENT"  # unreachable


def _role_lower(role: str | None) -> str:
    return "student" if _role_upper(role) == "STUDENT" else "organizer"


def _student_dto(row) -> dict:
    keys = row.keys() if hasattr(row, "keys") else []
    def get(col, default=None):
        return row[col] if col in keys else default
    return {
        "role": "student",
        "id": row["id"],
        "account": row["student_id"],
        "name": row["name"],
        "avatar": get("avatar"),
        "major": get("major"),
        "grade": get("grade"),
        "interests": get("interests"),
        "skills": get("skills"),
        "need_comprehensive_score": get("need_comprehensive_score"),
        "need_conduct_score": get("need_conduct_score"),
        "need_innovation_score": get("need_innovation_score"),
        "organization": None,
    }


def _organizer_dto(row) -> dict:
    keys = row.keys() if hasattr(row, "keys") else []
    def get(col, default=None):
        return row[col] if col in keys else default
    return {
        "role": "organizer",
        "id": row["id"],
        "account": row["account"],
        "name": row["name"],
        "avatar": get("avatar"),
        "major": None,
        "grade": None,
        "interests": None,
        "skills": None,
        "need_comprehensive_score": None,
        "need_conduct_score": None,
        "need_innovation_score": None,
        "organization": get("organization"),
    }


def _current_row(user: dict):
    if user["role"].upper() == "STUDENT":
        row = db.query_one("SELECT * FROM users WHERE id = ?", (user["id"],))
    else:
        row = db.query_one("SELECT * FROM organizers WHERE id = ?", (user["id"],))
    if row is None:
        fail(404, "账号不存在")
    return row


def _current_dto(user: dict) -> dict:
    row = _current_row(user)
    if user["role"].upper() == "STUDENT":
        return _student_dto(row)
    return _organizer_dto(row)


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """当前登录账号的基本信息。"""
    return ok(_current_dto(user))


@router.get("/list")
def list_accounts(user: dict = Depends(get_current_user)):
    """同一人名下的多个账号（学生号 + 发布者号），当前账号排第一。"""
    current = _current_dto(user)
    name = current["name"]
    accounts = []

    # 学生账号：同名；当前是学生时排除当前 id
    for row in db.query_all("SELECT * FROM users WHERE name = ?", (name,)):
        dto = _student_dto(row)
        if dto["id"] == current["id"] and current["role"] == "student":
            continue
        accounts.append(dto)

    # 发布者账号：同名；当前是发布者时排除当前 id
    for row in db.query_all("SELECT * FROM organizers WHERE name = ?", (name,)):
        dto = _organizer_dto(row)
        if dto["id"] == current["id"] and current["role"] == "organizer":
            continue
        accounts.append(dto)

    # 当前账号排第一
    accounts.insert(0, current)
    for a in accounts:
        a["current"] = (a["role"] == current["role"] and a["id"] == current["id"])
    return ok({"items": accounts, "total": len(accounts)})


class BasicBody(BaseModel):
    name: str | None = None
    major: str | None = None
    grade: str | None = None
    interests: str | None = None
    skills: str | None = None
    organization: str | None = None
    need_comprehensive_score: int | None = None
    need_conduct_score: int | None = None
    need_innovation_score: int | None = None


@router.put("/basic")
def update_basic(body: BasicBody, user: dict = Depends(get_current_user)):
    """修改基本信息：学生改姓名/专业/年级/兴趣/技能，发布者改姓名/组织。"""
    current = _current_dto(user)
    old_name = (current.get("name") or "").strip()
    if body.name is not None:
        new_name = body.name.strip()
        if new_name and new_name != old_name:
            if user["role"].upper() == "STUDENT":
                db.execute("UPDATE users SET name = ? WHERE name = ? AND id != ?", (new_name, old_name, user["id"]))
                db.execute("UPDATE organizers SET name = ? WHERE name = ?", (new_name, old_name))
            else:
                db.execute("UPDATE users SET name = ? WHERE name = ?", (new_name, old_name))
                db.execute("UPDATE organizers SET name = ? WHERE name = ? AND id != ?", (new_name, old_name, user["id"]))
    for key in ("need_comprehensive_score", "need_conduct_score", "need_innovation_score"):
        val = getattr(body, key)
        if val is not None and val not in (0, 1):
            fail(400, f"{key} 仅允许 0 或 1")

    if user["role"].upper() == "STUDENT":
        if body.name is not None and not body.name.strip():
            fail(400, "姓名不能为空")
        fields = []
        params = []
        if body.name is not None:
            fields.append("name = ?")
            params.append(body.name.strip())
        if body.major is not None:
            fields.append("major = ?")
            params.append(body.major)
        if body.grade is not None:
            fields.append("grade = ?")
            params.append(body.grade)
        if body.interests is not None:
            fields.append("interests = ?")
            params.append(body.interests)
        if body.skills is not None:
            fields.append("skills = ?")
            params.append(body.skills)
        if body.need_comprehensive_score is not None:
            fields.append("need_comprehensive_score = ?")
            params.append(body.need_comprehensive_score)
        if body.need_conduct_score is not None:
            fields.append("need_conduct_score = ?")
            params.append(body.need_conduct_score)
        if body.need_innovation_score is not None:
            fields.append("need_innovation_score = ?")
            params.append(body.need_innovation_score)
        if fields:
            fields.append("updated_at = datetime('now')")
            params.append(user["id"])
            db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", tuple(params))
    else:
        if body.name is not None and not body.name.strip():
            fail(400, "姓名不能为空")
        fields = []
        params = []
        if body.name is not None:
            fields.append("name = ?")
            params.append(body.name.strip())
        if body.organization is not None:
            fields.append("organization = ?")
            params.append(body.organization)
        if fields:
            params.append(user["id"])
            db.execute(f"UPDATE organizers SET {', '.join(fields)} WHERE id = ?", tuple(params))
    return ok(_current_dto(user))


class PasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.post("/password")
def change_password(body: PasswordBody, user: dict = Depends(get_current_user)):
    """修改密码：校验旧密码，新密码非空且不少于 6 位。"""
    if len(body.new_password or "") < 6:
        fail(400, "新密码至少 6 位")
    table = "users" if user["role"].upper() == "STUDENT" else "organizers"
    row = db.query_one(f"SELECT password_hash FROM {table} WHERE id = ?", (user["id"],))
    if row is None:
        fail(404, "账号不存在")
    if not verify_password(body.old_password or "", row["password_hash"]):
        fail(400, "旧密码不正确")
    db.execute(f"UPDATE {table} SET password_hash = ? WHERE id = ?", (hash_password(body.new_password), user["id"]))
    return ok({"updated": True})


class AvatarBody(BaseModel):
    url: str | None = None
    avatar: str | None = None


@router.post("/avatar")
def update_avatar(body: AvatarBody, user: dict = Depends(get_current_user)):
    """设置头像：前端先调 /api/upload 拿到 URL，再提交到这里。"""
    url = (body.url or body.avatar or "").strip()
    if not url:
        fail(400, "头像地址不能为空")
    table = "users" if user["role"].upper() == "STUDENT" else "organizers"
    db.execute(f"UPDATE {table} SET avatar = ? WHERE id = ?", (url, user["id"]))
    return ok({"avatar": url})


class SwitchBody(BaseModel):
    role: str | None = None
    id: int | None = None
    account: str | None = None
    target_role: str | None = None
    target_id: int | None = None
    target_account: str | None = None


@router.post("/switch")
def switch_account(body: SwitchBody, user: dict = Depends(get_current_user)):
    """切换到同一人名下的另一个账号，返回新的登录凭证。"""
    role_value = body.role or body.target_role
    id_value = body.id if body.id is not None else body.target_id
    account_value = body.account or body.target_account
    if not role_value:
        fail(400, "缺少目标角色")
    target_role = _role_upper(role_value)
    current = _current_dto(user)
    # 解析目标账号
    if target_role == "STUDENT":
        if id_value is not None:
            row = db.query_one("SELECT * FROM users WHERE id = ?", (id_value,))
        elif account_value:
            row = db.query_one("SELECT * FROM users WHERE student_id = ?", (account_value.strip(),))
        else:
            fail(400, "缺少目标账号 id 或学号")
        if row is None:
            fail(404, "目标账号不存在")
        target = _student_dto(row)
    else:
        if id_value is not None:
            row = db.query_one("SELECT * FROM organizers WHERE id = ?", (id_value,))
        elif account_value:
            row = db.query_one("SELECT * FROM organizers WHERE account = ?", (account_value.strip(),))
        else:
            fail(400, "缺少目标账号 id 或工号")
        if row is None:
            fail(404, "目标账号不存在")
        target = _organizer_dto(row)

    # 仅允许切换到同名账号（同一人）
    if (target.get("name") or "").strip() != (current.get("name") or "").strip():
        fail(403, "该账号与当前账号不属于同一人，无法切换")

    rid = target["id"]
    rlower = "student" if target["role"] == "student" else "organizer"
    return ok({"token": f"{rlower}:{rid}", "role": rlower, "id": rid})

# --- 兼容别名：不同前端/测试可能使用的路径与方法 ---
@router.post("/switch/{role}/{id}")
def switch_account_path(role: str, id: int, user: dict = Depends(get_current_user)):
    return switch_account(SwitchBody(role=role, id=id), user)


@router.post("/switch-account")
def switch_account_alias(body: SwitchBody, user: dict = Depends(get_current_user)):
    return switch_account(body, user)


@router.get("/switch")
def switch_account_get(role: str, id: int | None = None, account: str | None = None, user: dict = Depends(get_current_user)):
    return switch_account(SwitchBody(role=role, id=id, account=account), user)
