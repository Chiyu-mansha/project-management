import re
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_conn, dict_row
from .llm_gateway import extract_faq

router = APIRouter(prefix="/api/faqs", tags=["faqs-auto"])


def _norm(q: str) -> str:
    q = (q or "").lower().strip()
    q = re.sub(r"[\s，。？！,\.\?\!、：:；;\"'“”‘’（）()【】\[\]…~-]", "", q)
    return q


def _save_items(conn, activity_id, items, category, origin_title):
    """写入前三层去重：空值跳过；库里已有同归一化问题跳过；本批内重复跳过。"""
    existing = {_norm(r[0]) for r in conn.execute(
        "SELECT question FROM faqs WHERE (activity_id IS ? OR activity_id = ?) OR activity_id IS NULL",
        (activity_id, activity_id),
    ).fetchall()}
    seen, saved = set(), []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    skipped = 0
    for it in items[:5]:
        q = str(it.get("question", "")).strip()
        a = str(it.get("answer", "")).strip()
        if not q or not a:
            continue
        key = _norm(q)
        if not key or key in existing or key in seen:
            skipped += 1
            continue
        seen.add(key)
        cur = conn.execute(
            "INSERT INTO faqs(activity_id,question,answer,category,source,status,origin_title,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (activity_id, q, a, category, "auto", "draft", origin_title, now),
        )
        saved.append(cur.lastrowid)
    return saved, skipped


class AutoGenIn(BaseModel):
    activity_id: Optional[int] = None
    title: str = ""
    content: str = ""
    category: Optional[str] = "通知类"


@router.post("/auto-generate")
def auto_generate(body: AutoGenIn):
    """推文发布后调用：AI 从推文内容提取常见问答，以 draft 存入，待管理员审核。"""
    # 调 AI 网关服务提取（未开启/失败自动降级模板）
    items = extract_faq(body.title, body.content, count=5)
    conn = get_conn()
    saved, skipped = _save_items(conn, body.activity_id, items, body.category, body.title)
    conn.commit()
    rows = [dict_row(r) for r in conn.execute(f"SELECT *, (SELECT title FROM activities WHERE activities.id=faqs.activity_id) AS activity_title FROM faqs WHERE id IN ({','.join('?'*len(saved))})", saved).fetchall()] if saved else []
    conn.close()
    return {"items": rows, "total": len(rows), "skipped": skipped, "tip": "已存为草稿(draft)，请管理员审核修改后发布"}


class FromActivityIn(BaseModel):
    activity_id: int
    category: Optional[str] = "通知类"
    count: int = 5


@router.post("/from-activity")
def from_activity(body: FromActivityIn):
    """活动发布后一键提取：按 activity_id 读活动详情，拼成推文内容，提取 3-5 条 draft。

    由成员2发布活动后调用（或管理员在 FAQ 页点“一键导入”），粘贴提取入口不变。
    """
    conn = get_conn()
    act = conn.execute("SELECT * FROM activities WHERE id=?", (body.activity_id,)).fetchone()
    if not act:
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(404, "活动不存在")
    a = dict_row(act)
    title = a.get("title", "")
    content = "\n".join([
        f"标题：{a.get('title','')}",
        f"类型：{a.get('type','')}",
        f"时间：{a.get('start_time','')} ~ {a.get('end_time','')}",
        f"地点：{a.get('location','')}",
        f"报名截止：{a.get('signup_deadline','')}",
        f"组队：{a.get('min_team_member','')}~{a.get('max_team_member','')}人",
        f"简介：{a.get('description','')}",
        f"要求：{a.get('requirements','')}",
    ])
    items = extract_faq(title, content, count=max(3, min(5, body.count or 5)))
    saved, skipped = _save_items(conn, body.activity_id, items, body.category, title)
    conn.commit()
    rows = [dict_row(r) for r in conn.execute(f"SELECT *, (SELECT title FROM activities WHERE activities.id=faqs.activity_id) AS activity_title FROM faqs WHERE id IN ({','.join('?'*len(saved))})", saved).fetchall()] if saved else []
    conn.close()
    return {"items": rows, "total": len(rows), "skipped": skipped, "tip": "已从活动一键提取为草稿(draft)，请管理员审核修改后发布"}


@router.get("/import-status")
def import_status(activity_id: Optional[int] = None):
    """查某活动是否已导入过：返回 auto 草稿数和已发布数，前端据此禁用按钮。"""
    conn = get_conn()
    if activity_id is not None:
        draft = conn.execute("SELECT COUNT(*) FROM faqs WHERE activity_id=? AND source='auto' AND status='draft'", (activity_id,)).fetchone()[0]
        pub = conn.execute("SELECT COUNT(*) FROM faqs WHERE activity_id=? AND status='published'", (activity_id,)).fetchone()[0]
    else:
        draft = conn.execute("SELECT COUNT(*) FROM faqs WHERE activity_id IS NULL AND source='auto' AND status='draft'").fetchone()[0]
        pub = conn.execute("SELECT COUNT(*) FROM faqs WHERE activity_id IS NULL AND status='published'").fetchone()[0]
    conn.close()
    return {"activity_id": activity_id, "auto_draft": draft, "published": pub, "imported": (draft + pub) > 0}
