import heapq
import logging
import math
import re
import struct
from contextlib import closing

from database import get_conn
from . import llm_gateway


logger = logging.getLogger(__name__)
PUBLISHED = "(f.status = 'published' OR f.status IS NULL OR f.status = '')"
TOP_K = 5
_SIGNUP_AGAIN = re.compile(r"(?:重新|再次|二次|再)\s*(?:(?:进行|提交)\s*)?(?:报名|报一次名|申请报名)")


def _unit(vector):
    length = math.hypot(*vector)
    if not length or not math.isfinite(length):
        raise ValueError("无效的 FAQ 向量")
    return [value / length for value in vector]


def refresh_embeddings():
    """定时补齐已发布 FAQ 的向量，包括历史数据和编辑后的问题。"""
    try:
        model = llm_gateway.faq_embedding_model()
        with closing(get_conn()) as conn:
            pending = conn.execute(
                f"""SELECT f.id, f.question FROM faqs f
                    LEFT JOIN faq_embeddings e ON e.faq_id = f.id
                    WHERE {PUBLISHED} AND trim(f.question) <> ''
                      AND (e.faq_id IS NULL OR e.model <> ? OR e.question <> f.question)
                    ORDER BY f.id LIMIT 100""",
                (model,),
            ).fetchall()
            for start in range(0, len(pending), 10):
                batch = pending[start:start + 10]
                version, vectors = llm_gateway.faq_embeddings([row["question"][:2000] for row in batch])
                if version != model or len(vectors) != len(batch):
                    raise ValueError("FAQ 向量模型或数量不一致")
                records = []
                for row, vector in zip(batch, vectors):
                    unit = _unit(vector)
                    packed = struct.pack(f"<{len(unit)}f", *unit)
                    records.append((model, packed, row["id"], row["question"]))
                with conn:
                    conn.executemany(
                        f"""INSERT OR REPLACE INTO faq_embeddings(faq_id, question, model, vector)
                            SELECT f.id, f.question, ?, ? FROM faqs f
                            WHERE f.id = ? AND f.question = ? AND {PUBLISHED}""",
                        records,
                    )
    except Exception:
        logger.warning("FAQ 向量刷新失败", exc_info=True)


def find_faq(conn, activity_id, question, history, activity_context):
    scope = "(f.activity_id = ? OR f.activity_id IS NULL)" if activity_id is not None else "1=1"
    params = (activity_id,) if activity_id is not None else ()
    # 无历史上下文时，可直接使用当前活动或全局的同文 FAQ。
    if not history:
        exact = conn.execute(
            f"""SELECT f.* FROM faqs f WHERE {PUBLISHED}
                AND (f.activity_id = ? OR f.activity_id IS NULL)
                AND trim(f.question) = ?
                ORDER BY f.activity_id IS NULL, f.id DESC LIMIT 1""",
            (activity_id, question),
        ).fetchone()
        if exact:
            return exact
    if not llm_gateway.USE_REAL_LLM:
        return None
    has_vectors = conn.execute(
        f"""SELECT 1 FROM faq_embeddings e JOIN faqs f ON e.faq_id = f.id
            WHERE {PUBLISHED} AND {scope} AND e.question = f.question LIMIT 1""",
        params,
    ).fetchone()
    if not has_vectors:
        return None
    context = activity_context.splitlines()[0] if activity_context else ""
    prior_questions = "\n".join(turn["content"] for turn in history if turn["role"] == "user")
    query = "\n".join(part for part in (context, prior_questions[-500:], question[:1400]) if part)
    try:
        model, vectors = llm_gateway.faq_embeddings([query[:2000]])
        unit = _unit(vectors[0])
    except (ValueError, IndexError, KeyError, TypeError, OSError):
        return None
    vector_format = struct.Struct(f"<{len(unit)}f")
    rows = conn.execute(
        f"""SELECT f.id, f.question, f.answer, f.activity_id, a.title, e.vector
            FROM faq_embeddings e JOIN faqs f ON e.faq_id = f.id AND e.question = f.question
            LEFT JOIN activities a ON a.id = f.activity_id
            WHERE {PUBLISHED} AND {scope} AND e.model = ? AND length(e.vector) = ?""",
        (*params, model, vector_format.size),
    )
    candidates = heapq.nlargest(
        TOP_K,
        (row for row in rows if not _SIGNUP_AGAIN.search(question) or _SIGNUP_AGAIN.search(row["question"])),
        key=lambda row: (sum(a * b for a, b in zip(unit, vector_format.unpack(row["vector"]))), -row["id"]),
    )
    if not candidates:
        return None
    entries = [
        {
            "activity": str(row["title"] or row["activity_id"]) if row["activity_id"] is not None else "全局",
            "question": row["question"],
            "answer": row["answer"],
        }
        for row in candidates
    ]
    index = llm_gateway.confirm_faq(question, context, prior_questions[-500:], entries)
    return candidates[index] if index >= 0 else None
