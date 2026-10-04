from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
from database import get_conn, dict_row
from llm_gateway import gateway_chat

router = APIRouter(prefix="/api/faqs", tags=["faqs-auto"])


class AutoGenIn(BaseModel):
    activity_id: Optional[int] = None
    title: str = ""
    content: str = ""
    category: Optional[str] = "通知类"


@router.post("/auto-generate")
def auto_generate(body: AutoGenIn):
    """推文发布后调用：AI 从推文内容提取常见问答，以 draft 存入，待管理员审核。"""
    prompt = (
        f"活动标题：{body.title}\n推文内容：{body.content[:2000]}\n"
        "请从中提取3-5个同学最可能问的问题，以JSON数组返回，"
        '格式：[{"question":"...","answer":"..."}]，只返回JSON。'
    )
    raw = gateway_chat(prompt)
    items = []
    try:
        s, e = raw.find("["), raw.rfind("]") + 1
        items = json.loads(raw[s:e]) if s >= 0 and e > s else []
    except Exception:
        items = []
    if not items:
        # Mock/解析失败兜底：按模板生成，保证流程不断
        items = [
            {"question": f"{body.title}什么时候开始？", "answer": "见推文中的时间安排，详情咨询主办方。"},
            {"question": f"{body.title}怎么报名？", "answer": "在活动详情页点击报名即可。"},
            {"question": f"{body.title}有综测加分吗？", "answer": "见推文中的综测说明。"},
        ]
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
