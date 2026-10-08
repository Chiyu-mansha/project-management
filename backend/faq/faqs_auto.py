from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_conn, dict_row
from .llm_gateway import extract_faq

router = APIRouter(prefix="/api/faqs", tags=["faqs-auto"])


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
    # 每次提取前清理该活动的旧自动草稿，避免重复堆积；已发布的不动
    if body.activity_id is not None:
        conn.execute("DELETE FROM faqs WHERE activity_id=? AND source='auto' AND status='draft'", (body.activity_id,))
    else:
        conn.execute("DELETE FROM faqs WHERE activity_id IS NULL AND source='auto' AND status='draft'")
    saved = []
    for it in items[:5]:
        q = str(it.get("question", "")).strip()
        a = str(it.get("answer", "")).strip()
        if not q or not a:
            continue
        cur = conn.execute(
            "INSERT INTO faqs(activity_id,question,answer,category,source,status,origin_title) VALUES(?,?,?,?,?,?,?)",
            (body.activity_id, q, a, body.category, "auto", "draft", body.title),
        )
        saved.append(cur.lastrowid)
    conn.commit()
    rows = [dict_row(r) for r in conn.execute(f"SELECT *, (SELECT title FROM activities WHERE activities.id=faqs.activity_id) AS activity_title FROM faqs WHERE id IN ({','.join('?'*len(saved))})", saved).fetchall()] if saved else []
    conn.close()
    return {"items": rows, "total": len(rows), "tip": "已存为草稿(draft)，请管理员审核修改后发布"}
