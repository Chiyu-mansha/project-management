import re
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_conn, dict_row
from auth import require_role
from .llm_gateway import extract_faq, USE_REAL_LLM, similar_question as gw_similar

router = APIRouter(prefix="/api/faqs", tags=["faqs-auto"])


def _norm(q: str) -> str:
    q = (q or "").lower().strip()
    q = re.sub(r"[\s，。？！,\.\?\!、：:；;\"'“”‘’（）()【】\[\]…~-]", "", q)
    return q


def _overlap(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa), len(sb))


def _save_items(conn, activity_id, items, category, origin_title):
    """写入前去重：空值跳过；精确比对跳过；双条件（模型同义+字面重合>=0.6）才拦。

    保守方向与高频合并相反：提取是写入侧，误拦会无声丢失，所以模型单方面说同义不算数；
    且只和同活动/同全局范围比，不跨活动误杀（如“蜜雪冰城”不拦“食堂”）。
    """
    lib = conn.execute(
        "SELECT question FROM faqs WHERE (activity_id IS ? OR activity_id = ?) OR activity_id IS NULL",
        (activity_id, activity_id),
    ).fetchall()
    lib_norm = [(_norm(r[0]), r[0]) for r in lib]
    lib_set = {n for n, _ in lib_norm}
    seen, saved = set(), []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    skipped = 0
    for it in items[:5]:
        q = str(it.get("question", "")).strip()
        a = str(it.get("answer", "")).strip()
        if not q or not a:
            continue
        key = _norm(q)
        if not key or key in lib_set or key in seen:
            skipped += 1
            continue
        # 同范围候选：全局新问题只和全局比，有活动的只和同活动+全局比
        dup = False
        if USE_REAL_LLM and lib_norm:
            scope = [(n, raw) for n, raw in lib_norm if True][:20]
            try:
                idx = gw_similar(q, [raw for _, raw in scope])
                if isinstance(idx, int) and 0 <= idx < len(scope):
                    n0, _ = scope[idx]
                    same_scope = True  # scope 已限定同范围，直接用
                    if same_scope and _overlap(key, n0) >= 0.6:
                        dup = True
            except Exception:
                dup = False
        if dup:
            skipped += 1
            continue
        seen.add(key)
        lib_set.add(key)
        lib_norm.append((key, q))
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
def auto_generate(body: AutoGenIn, user: dict = Depends(require_role("ORGANIZER"))):
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
def from_activity(body: FromActivityIn, user: dict = Depends(require_role("ORGANIZER"))):
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
    # 发布者名称（organizer_id → organizers.name；老库可能只有 organizer 文本，回退用）
    org_name = a.get("organizer") or ""
    if a.get("organizer_id"):
        orow = conn.execute("SELECT name, organization FROM organizers WHERE id=?", (a.get("organizer_id"),)).fetchone()
        if orow:
            org_name = " · ".join([x for x in (orow["organization"], orow["name"]) if x])
    # 综测/操行/创新分拼成一句，便于 AI 提取加分问答；老库 zongce_score 文本兜底
    scores = []
    if a.get("comprehensive_score"):
        scores.append("可加综合素养积分")
    if a.get("conduct_score") is not None and a.get("conduct_score") != "":
        scores.append(f"操行分 {a.get('conduct_score')}")
    if a.get("innovation_score") is not None and a.get("innovation_score") != "":
        scores.append(f"创新分 {a.get('innovation_score')}")
    if not scores and a.get("zongce_score"):
        scores.append(str(a.get("zongce_score")))
    content = "\n".join([
        f"标题：{a.get('title','')}",
        f"类型：{a.get('type','')}",
        f"标签：{a.get('tags','')}",
        f"主办方：{org_name}",
        f"开始时间：{a.get('start_time','')}",
        f"结束时间：{a.get('end_time','')}",
        f"地点：{a.get('location','')}",
        f"报名截止：{a.get('signup_deadline','')}",
        f"组队人数：{a.get('min_team_member','')}~{a.get('max_team_member','')} 人",
        f"报名上限：{a.get('max_participants','') or '不限'}",
        f"是否发电子票：{'是' if a.get('has_ticket') else '否'}",
        f"综测加分：{'；'.join(scores) if scores else '无'}",
        f"活动简介：{a.get('description','')}",
        f"报名条件：{a.get('requirements','')}",
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
