import json
import re
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from database import get_conn, dict_row
from auth import require_role
from .llm_gateway import chat, chat_stream, USE_REAL_LLM, similar_question as gw_similar


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

router = APIRouter(prefix="/api/qa", tags=["qa"])


class AskIn(BaseModel):
    activity_id: Optional[int] = None
    question: str
    no_cache: Optional[bool] = False  # 重新生成：跳过 FAQ，直接走大模型
    # 最近几轮对话，前端按 [{role:'user'|'assistant', content:str}] 传入
    history: Optional[List[dict]] = []


class AcceptIn(BaseModel):
    activity_id: Optional[int] = None
    question: str
    answer: str
    category: Optional[str] = "通知类"


class FeedbackIn(BaseModel):
    faq_id: Optional[int] = None
    log_id: Optional[int] = None
    activity_id: Optional[int] = None
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


_MOCK_ANSWER_PREFIXES = ("[网关不可用", "[真实网关失败", "[Mock")


def _is_degraded_answer(answer: str) -> bool:
    """判断答案是否来自网关降级/本地 Mock，避免把兜底话术当成真实答案缓存。"""
    return (answer or "").lstrip().startswith(_MOCK_ANSWER_PREFIXES)


MAX_HISTORY_TURNS = 8


def _clean_history(history) -> list:
    """只保留最近 N 轮 user/assistant 文本，防止前端传入过长或非法结构。"""
    if not isinstance(history, list):
        return []
    cleaned = []
    for item in history[-MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content[:2000]})
    return cleaned


def _activity_context(conn, activity_id) -> str:
    """把当前活动关键信息压缩成一段上下文，供大模型回答时引用。"""
    if activity_id is None:
        return ""
    row = conn.execute(
        """SELECT title,type,location,start_time,end_time,signup_deadline,
                  description,requirements,comprehensive_score,conduct_score,innovation_score
           FROM activities WHERE id=?""",
        (activity_id,),
    ).fetchone()
    if not row:
        return ""
    a = dict_row(row)
    lines = [
        f"活动标题：{a.get('title') or '未知'}",
        f"类型：{a.get('type') or '未知'}",
        f"地点：{a.get('location') or '待定'}",
        f"开始时间：{a.get('start_time') or '待定'}",
        f"结束时间：{a.get('end_time') or '待定'}",
        f"报名截止：{a.get('signup_deadline') or '待定'}",
        f"活动简介：{a.get('description') or '无'}",
        f"报名条件：{a.get('requirements') or '无'}",
    ]
    scores = []
    if a.get("comprehensive_score"):
        scores.append("可加综合素养积分")
    if a.get("conduct_score"):
        scores.append(f"操行分 {a['conduct_score']}")
    if a.get("innovation_score"):
        scores.append(f"创新分 {a['innovation_score']}")
    lines.append(f"加分：{'；'.join(scores) if scores else '无'}")
    return "\n".join(lines)


def _find_faq(conn, body: "AskIn", q: str):
    """按活动/全局范围查已发布 FAQ，返回 sqlite Row 或 None。"""
    if body.no_cache:
        return None
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
        return row
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
            return next((r for r in rows if dict_row(r)["id"] == scored[0]["id"]), None)
    return None


def _find_cached(conn, body: "AskIn", q: str, history: list):
    """查 7 天内同归一化问题的真实 LLM 缓存；有历史上下文时不读缓存。"""
    if body.no_cache or history:
        return None
    nq = _norm(q)
    logs = conn.execute(
        """SELECT question, answer FROM qa_logs WHERE source='llm'
           AND ((activity_id IS ? AND ? IS NULL) OR activity_id = ?)
           AND created_at >= datetime('now','-7 days') ORDER BY id DESC LIMIT 50""",
        (body.activity_id, body.activity_id, body.activity_id),
    ).fetchall()
    for lq, la in logs:
        if _norm(lq) == nq and la and not _is_degraded_answer(la):
            return la
    return None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/ask")
def ask(body: AskIn):
    q = (body.question or "").strip()
    if not q:
        return {"answer": "问题不能为空", "source": "faq", "faq_id": None}
    conn = get_conn()
    history = _clean_history(body.history)
    activity_context = _activity_context(conn, body.activity_id)
    # 1. 先查 FAQ（重新生成时 no_cache=True 跳过）
    row = _find_faq(conn, body, q)
    if row:
        d = dict_row(row)
        log_id = _log(conn, body.activity_id, q, d["answer"], "faq")
        conn.commit(); conn.close()
        return {"answer": d["answer"], "source": "faq", "faq_id": d["id"], "faq_question": d.get("question", ""), "log_id": log_id}
    # 2. 未命中 → 先看 7 天内同样归一化问题有没有 llm 缓存，有直接复用，不调网关
    cached = _find_cached(conn, body, q, history)
    if cached:
        log_id = _log(conn, body.activity_id, q, cached, "llm")
        conn.commit(); conn.close()
        return {"answer": cached, "source": "llm", "faq_id": None, "cached": True, "log_id": log_id}
    # 3. 无缓存 → 调 AI 网关服务兜底（未开启/失败自动降级 Mock）
    result = chat(q, body.activity_id, history=history, activity_context=activity_context or None)
    answer = result["answer"]
    source = result.get("source", "llm")
    # 关键：降级 Mock 不写 source='llm'，因此不会被上面的 7 天缓存命中；
    # 仍保留一条 source='mock' 日志用于统计网关失败率，但不参与候选沉淀。
    # 带多轮上下文的答案写 llm_ctx，避免后续单轮问题误命中上下文相关答案。
    if source == "mock":
        log_source = "mock"
    elif history:
        log_source = "llm_ctx"
    else:
        log_source = "llm"
    log_id = _log(conn, body.activity_id, q, answer, log_source)
    conn.commit(); conn.close()
    return {"answer": answer, "source": source, "faq_id": None, "cached": False, "log_id": log_id}


@router.post("/ask-stream")
def ask_stream(body: AskIn):
    """SSE 流式答疑：meta -> delta* -> done；FAQ/缓存命中也会以单段 delta 返回。"""
    q = (body.question or "").strip()
    if not q:
        def empty():
            yield _sse("error", {"message": "问题不能为空"})
        return StreamingResponse(empty(), media_type="text/event-stream")

    def gen():
        conn = get_conn()
        history = _clean_history(body.history)
        activity_context = _activity_context(conn, body.activity_id)
        try:
            row = _find_faq(conn, body, q)
            if row:
                d = dict_row(row)
                log_id = _log(conn, body.activity_id, q, d["answer"], "faq")
                conn.commit()
                meta = {"source": "faq", "faq_id": d["id"], "faq_question": d.get("question", "")}
                yield _sse("meta", meta)
                yield _sse("delta", {"content": d["answer"]})
                yield _sse("done", {**meta, "log_id": log_id, "cached": False})
                return
            cached = _find_cached(conn, body, q, history)
            if cached:
                log_id = _log(conn, body.activity_id, q, cached, "llm")
                conn.commit()
                yield _sse("meta", {"source": "llm", "cached": True})
                yield _sse("delta", {"content": cached})
                yield _sse("done", {"source": "llm", "cached": True, "log_id": log_id})
                return

            yield _sse("meta", {"source": "llm", "cached": False})
            parts = []
            source = "llm"
            stream_meta = {"source": "llm"}
            log_id = None
            try:
                for ev in chat_stream(q, body.activity_id, history=history, activity_context=activity_context or None, meta=stream_meta):
                    if ev.get("delta"):
                        parts.append(ev["delta"])
                        yield _sse("delta", {"content": ev["delta"]})
                    elif ev.get("done"):
                        source = ev.get("source", stream_meta.get("source", "llm"))
                    elif ev.get("error"):
                        yield _sse("error", {"message": ev["error"]})
            finally:
                source = stream_meta.get("source", source)
                answer = "".join(parts)
                if answer:
                    log_source = "mock" if source == "mock" else ("llm_ctx" if history else "llm")
                    log_id = _log(conn, body.activity_id, q, answer, log_source)
                    conn.commit()
            yield _sse("done", {"source": source, "log_id": log_id, "cached": False})
        finally:
            conn.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _log(conn, activity_id, question, answer, source):
    cur = conn.execute(
        "INSERT INTO qa_logs(activity_id,question,answer,source,count,created_at) VALUES(?,?,?,?,1,?)",
        (activity_id, question, answer, source, datetime.now().isoformat(timespec="seconds")),
    )
    return cur.lastrowid


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
        if _is_degraded_answer(r["answer"]):
            continue
        if activity_id is not None and r["activity_id"] != activity_id:
            continue
        key = (r["activity_id"], _norm(r["question"]))
        g = groups.setdefault(key, {"question": r["question"], "answer": r["answer"], "activity_id": r["activity_id"], "count": 0})
        g["count"] += 1
        g["answer"] = r["answer"] or g["answer"]
    # 规则归一化先聚一轮（快）
    basics = list(groups.values())
    # 连接要留到合并块之后（合并要用它读写 sim_cache），不能提前 close
    # 开启真实网关时，再用 AI 做同义词合并（把不同问法归为一类）
    # 保守策略：循环逐个比对；网关异常/返回-1/格式不对一律不并（宁可漏，不错并）；
    # 只合并同一活动（activity_id 相等）的组，不跨活动归并。
    # 同义结果缓存一天：同一组问题串拼成 key，命中直接用，不调网关。
    if USE_REAL_LLM and len(basics) > 1:
        merged = []
        for g in basics:
            hit = -1
            try:
                cands = [m["question"] for m in merged]
                if cands:
                    cache_key = "SIM:" + _norm(g["question"]) + "||" + "||".join(sorted(_norm(c) for c in cands))
                    row = conn.execute(
                        "SELECT answer FROM qa_logs WHERE source='sim_cache' AND question=? AND created_at >= datetime('now','-1 day')",
                        (cache_key,),
                    ).fetchone()
                    if row:
                        idx = int(row[0])
                    else:
                        idx = gw_similar(g["question"], cands)
                        conn.execute(
                            "INSERT INTO qa_logs(activity_id,question,answer,source,count,created_at) VALUES(NULL,?,?,'sim_cache',1,?)",
                            (cache_key, str(idx), datetime.now().isoformat(timespec="seconds")),
                        )
                        conn.commit()
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
    conn.close()
    out = [g for g in basics if _norm(g["question"]) not in faq_norm and g["count"] >= min_count]
    out.sort(key=lambda x: -x["count"])
    return {"items": out, "total": len(out), "min_count": min_count}


@router.post("/feedback")
def feedback(body: FeedbackIn):
    """赞/踩。写入 qa_logs.feedback；踩且命中知识库 → 该 FAQ 立即转为待审核(draft)。"""
    if body.action not in ("like", "dislike"):
        return {"ok": False, "message": "action 只能是 like/dislike"}
    conn = get_conn()
    now = _now()
    faq_downgraded = False
    feedback_updated = False
    # 优先按 log_id 精确更新，避免同一问题多次提问时改错记录
    if body.log_id:
        cur = conn.execute(
            "UPDATE qa_logs SET feedback=?, feedback_at=? WHERE id=?",
            (body.action, now, body.log_id),
        )
        feedback_updated = cur.rowcount > 0
    elif body.question:
        if body.activity_id is None:
            cur = conn.execute(
                """UPDATE qa_logs SET feedback=?, feedback_at=?
                   WHERE id=(SELECT id FROM qa_logs WHERE question=? AND activity_id IS NULL ORDER BY id DESC LIMIT 1)""",
                (body.action, now, body.question),
            )
        else:
            cur = conn.execute(
                """UPDATE qa_logs SET feedback=?, feedback_at=?
                   WHERE id=(SELECT id FROM qa_logs WHERE question=? AND activity_id=? ORDER BY id DESC LIMIT 1)""",
                (body.action, now, body.question, body.activity_id),
            )
        feedback_updated = cur.rowcount > 0
    if body.action == "dislike" and body.faq_id:
        conn.execute("UPDATE faqs SET status='draft',updated_at=? WHERE id=?", (now, body.faq_id))
        faq_downgraded = True
    conn.commit(); conn.close()
    return {"ok": True, "faq_downgraded": faq_downgraded, "feedback_updated": feedback_updated}


@router.get("/disliked")
def disliked(limit: int = 50, user: dict = Depends(require_role("ORGANIZER"))):
    """被踩的答疑记录 → 待改写/待沉淀列表（按问题归一化后聚合）。"""
    limit = min(max(limit, 1), 200)
    conn = get_conn()
    rows = conn.execute(
        """SELECT q.id, q.activity_id, q.question, q.answer, q.source, q.feedback, q.feedback_at, q.created_at,
                  (SELECT title FROM activities WHERE activities.id=q.activity_id) AS activity_title
           FROM qa_logs q
           WHERE q.feedback='dislike'
           ORDER BY q.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    groups = {}
    for r in rows:
        d = dict_row(r)
        key = (d.get("activity_id"), _norm(d.get("question", "")))
        g = groups.get(key)
        if g is None:
            g = {**d, "count": 0, "log_id": d["id"], "last_feedback_at": d.get("feedback_at")}
            groups[key] = g
        g["count"] += 1
    items = sorted(groups.values(), key=lambda x: (-x["count"], -x["log_id"]))
    conn.close()
    return {"items": items, "total": len(items)}


@router.post("/candidates/accept")
def accept(body: AcceptIn, user: dict = Depends(require_role("ORGANIZER"))):
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
