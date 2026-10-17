from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from database import get_conn, dict_row

router = APIRouter(prefix="/api/faqs", tags=["faqs"])


class FaqIn(BaseModel):
    activity_id: Optional[int] = None
    question: str
    answer: str
    category: Optional[str] = ""
    source: Optional[str] = "manual"
    status: Optional[str] = "published"
    origin_title: Optional[str] = ""


@router.get("")
def list_faqs(
    activity_id: Optional[int] = None,
    activity_title: Optional[str] = None,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_conn()
    where, params = ["1=1"], []
    if activity_id is not None:
        where.append("faqs.activity_id = ?")
        params.append(activity_id)
    if activity_title:
        where.append("faqs.activity_id IN (SELECT id FROM activities WHERE title LIKE ?)")
        params.append(f"%{activity_title}%")
    if category:
        where.append("faqs.category = ?")
        params.append(category)
    if status:
        where.append("faqs.status = ?")
        params.append(status)
    if keyword:
        where.append("(faqs.question LIKE ? OR faqs.answer LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%"]
    sql_base = f"FROM faqs WHERE {' AND '.join(where)}"
    total = conn.execute(f"SELECT COUNT(*) {sql_base}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT faqs.*, (SELECT title FROM activities WHERE activities.id=faqs.activity_id) AS activity_title {sql_base} ORDER BY faqs.id DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    conn.close()
    return {"items": [dict_row(r) for r in rows], "total": total}


@router.post("")
def create_faq(body: FaqIn):
    if not body.question.strip() or not body.answer.strip():
        raise HTTPException(400, "question/answer 不能为空")
    if body.source not in ("manual", "auto", "llm"):
        body.source = "manual"
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO faqs(activity_id,question,answer,category,source,status,origin_title) VALUES(?,?,?,?,?,?,?)",
        (body.activity_id, body.question, body.answer, body.category, body.source, body.status, body.origin_title),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM faqs WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return dict_row(row)


@router.put("/{faq_id}")
def update_faq(faq_id: int, body: FaqIn):
    conn = get_conn()
    old = conn.execute("SELECT * FROM faqs WHERE id=?", (faq_id,)).fetchone()
    if not old:
        conn.close()
        raise HTTPException(404, "FAQ 不存在")
    conn.execute(
        "UPDATE faqs SET activity_id=?,question=?,answer=?,category=?,source=?,status=?,origin_title=? WHERE id=?",
        (body.activity_id, body.question, body.answer, body.category, body.source, body.status, body.origin_title, faq_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM faqs WHERE id=?", (faq_id,)).fetchone()
    conn.close()
    return dict_row(row)


@router.delete("/{faq_id}")
def delete_faq(faq_id: int):
    conn = get_conn()
    cur = conn.execute("DELETE FROM faqs WHERE id=?", (faq_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "FAQ 不存在")
    return {"ok": True, "id": faq_id}


@router.post("/from-qa")
def from_qa(body: FaqIn):
    """答疑沉淀：高频/有用问答一键转 FAQ，source=auto"""
    body.source = "auto"
    return create_faq(body)
