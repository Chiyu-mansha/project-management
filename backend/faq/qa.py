import re
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_conn, dict_row
from .llm_gateway import chat, USE_REAL_LLM, similar_question as gw_similar


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

router = APIRouter(prefix="/api/qa", tags=["qa"])


class AskIn(BaseModel):
    activity_id: Optional[int] = None
    question: str
    no_cache: Optional[bool] = False  # 重新生成：跳过 FAQ，直接走大模型


class AcceptIn(BaseModel):
    activity_id: Optional[int] = None
    question: str
    answer: str
    category: Optional[str] = "通知类"


class FeedbackIn(BaseModel):
    faq_id: Optional[int] = None
    action: str  # like / dislike
    question: Optional[str] = ""


def _norm(q: str) -> str:
    """问题归一化：去标点/空白/疑问语气词，便于同类问题聚到一起。"""
    q = (q or "").lower().strip()
    q = re.sub(r"[\s，。？！,\.\?\!、：:；;\"'“”‘’（）()【】\[\]…~-]", "", q)
    q = re.sub(r"(请问|我想问|我想知道|想问一下|谢谢|呢|吗|呀|啊|吧)+$", "", q)
    return q


def _overlap(a: str, b: str) -> float:
    """归一化字面重合度：交集字符数 / 较长者长度，用于双条件判重的第二道门槛。"""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa), len(sb))


@router.post("/ask")
def ask(body: AskIn):
    q = (body.question or "").strip()
    if not q:
        return {"answer": "问题不能为空", "source": "faq", "faq_id": None}
    conn = get_conn()
    # 1. 先查 FAQ（重新生成时 no_cache=True 跳过）
    #    选了具体活动 → 先查该活动，没有再查通用(activity_id 为空)；都不跨到别的活动
    #    未选活动   → 在整个知识库搜索（所有活动 + 通用）
    row = None
    if not body.no_cache:
        if body.activity_id is not None:
            row = conn.execute(
                "SELECT * FROM faqs WHERE (status='published' OR status IS NULL OR status='') AND activity_id=? AND (question LIKE ? OR ? LIKE '%'||question||'%') LIMIT 1",
                (body.activity_id, f"%{q}%", q),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM faqs WHERE (status='published' OR status IS NULL OR status='') AND activity_id IS NULL AND (question LIKE ? OR ? LIKE '%'||question||'%') LIMIT 1",
                    (f"%{q}%", q),
                ).fetchone()
        else:
            # 全局搜索：LIKE 可能命中多条（如“蜜雪冰城开门时间”命中“食堂开门时间”），
            # 按归一化字面重合度排序，低于 0.5 宁可走网关也不硬返回，避免串台。
            rows = conn.execute(
                "SELECT * FROM faqs WHERE (status='published' OR status IS NULL OR status='') AND (question LIKE ? OR ? LIKE '%'||question||'%') LIMIT 10",
                (f"%{q}%", q),
            ).fetchall()
            if rows:
                nq = _norm(q)
                scored = sorted(
                    (dict_row(r) for r in rows),
                    key=lambda d: _overlap(nq, _norm(d.get("question", ""))),
                    reverse=True,
                )
                if _overlap(nq, _norm(scored[0].get("question", ""))) >= 0.5:
                    row = next((r for r in rows if dict_row(r)["id"] == scored[0]["id"]), None)
    if row:
        d = dict_row(row)
        _log(conn, body.activity_id, q, d["answer"], "faq")
        conn.commit(); conn.close()
        return {"answer": d["answer"], "source": "faq", "faq_id": d["id"]}
    # 2. 未命中 → 调 AI 网关服务兜底（未开启/失败自动降级 Mock）
    result = chat(q, body.activity_id)
    answer = result["answer"]
    _log(conn, body.activity_id, q, answer, "llm")
    conn.commit(); conn.close()
    return {"answer": answer, "source": "llm", "faq_id": None}


def _log(conn, activity_id, question, answer, source):
    conn.execute(
        "INSERT INTO qa_logs(activity_id,question,answer,source,count,created_at) VALUES(?,?,?,?,1,?)",
        (activity_id, question, answer, source, datetime.now().isoformat(timespec="seconds")),
    )


@router.get("/candidates")
def candidates(min_count: int = 3, activity_id: Optional[int] = None):
    """高频未命中问题 → 待沉淀候选，供管理员审核转 FAQ。"""
    conn = get_conn()
    logs = conn.execute("SELECT question, answer, activity_id, source FROM qa_logs").fetchall()
    faq_norm = {_norm(r[0]) for r in conn.execute("SELECT question FROM faqs").fetchall()}
    groups = {}
    for r in logs:
        if r["source"] != "llm":  # 只统计没被 FAQ 命中的
            continue
        if activity_id is not None and r["activity_id"] != activity_id:
            continue
        key = (r["activity_id"], _norm(r["question"]))
        g = groups.setdefault(key, {"question": r["question"], "answer": r["answer"], "activity_id": r["activity_id"], "count": 0})
        g["count"] += 1
        g["answer"] = r["answer"] or g["answer"]
    conn.close()
    # 规则归一化先聚一轮（快）
    basics = list(groups.values())
    # 开启真实网关时，再用 AI 做同义词合并（把不同问法归为一类）
    # 保守策略：循环逐个比对；网关异常/返回-1/格式不对一律不并（宁可漏，不错并）；
    # 只合并同一活动（activity_id 相等）的组，不跨活动归并。
    if USE_REAL_LLM and len(basics) > 1:
        merged = []
        for g in basics:
            hit = -1
            try:
                cands = [m["question"] for m in merged]
                if cands:
                    idx = gw_similar(g["question"], cands)
                    if isinstance(idx, int) and 0 <= idx < len(merged):
                        if merged[idx]["activity_id"] == g["activity_id"]:
                            hit = idx
            except Exception:
                hit = -1
            if hit >= 0:
                merged[hit]["count"] += g["count"]
            else:
                merged.append(g)
        basics = merged
    out = [g for g in basics if _norm(g["question"]) not in faq_norm and g["count"] >= min_count]
    out.sort(key=lambda x: -x["count"])
    return {"items": out, "total": len(out), "min_count": min_count}


@router.post("/feedback")
def feedback(body: FeedbackIn):
    """赞/踩。踩且命中知识库 → 该 FAQ 立即转为待审核(draft)。"""
    conn = get_conn()
    changed = False
    if body.action == "dislike" and body.faq_id:
        conn.execute("UPDATE faqs SET status='draft',updated_at=? WHERE id=?", (_now(), body.faq_id,))
        conn.commit(); changed = True
    conn.close()
    return {"ok": True, "faq_downgraded": changed}


@router.post("/candidates/accept")
def accept(body: AcceptIn):
    """把候选问答沉淀为 FAQ 草稿，等管理员审核。source=auto, status=draft。"""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO faqs(activity_id,question,answer,category,source,status,origin_title,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (body.activity_id, body.question, body.answer, body.category, "auto", "draft", "高频提问", _now()),
    )
    conn.commit()
    nid = cur.lastrowid
    row = conn.execute("SELECT * FROM faqs WHERE id=?", (nid,)).fetchone()
    conn.close()
    return dict_row(row)
