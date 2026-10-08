"""调用「AI 网关服务」的 HTTP 客户端（方案 2：网关独立跑，本模块只发 HTTP 请求）。

网关服务默认地址：http://127.0.0.1:8100（见 网关/main.py）
- 未开启真实网关 / 请求失败 / 超时 → 自动降级本地 Mock，保证答疑与提取不中断
- 开启方式：backend/.env 里设 USE_REAL_LLM=1
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

GATEWAY_URL = os.getenv("AI_GATEWAY_URL", "http://127.0.0.1:8100").rstrip("/")
USE_REAL_LLM = os.getenv("USE_REAL_LLM") == "1"
TIMEOUT = 20


def _post(path: str, payload: dict) -> dict:
    r = requests.post(f"{GATEWAY_URL}{path}", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# ---------- 能力 1：智能答疑（对话） ----------

def chat(question: str, activity_id=None) -> dict:
    """返回 {"answer": str, "source": "llm"|"mock"}。"""
    if USE_REAL_LLM:
        try:
            d = _post("/api/ai/chat", {"question": question, "activity_id": activity_id})
            return {"answer": d.get("answer", ""), "source": d.get("source", "llm")}
        except Exception as e:
            return {"answer": f"[网关不可用，已降级Mock] {e} | 请查看活动详情页或联系主办方。", "source": "mock"}
    return {
        "answer": f"[Mock答疑] 关于「{question[:30]}」的问题，请查看活动详情页或联系活动负责人。",
        "source": "mock",
    }


# ---------- 能力 2：推文关键问题提取 ----------

def extract_faq(title: str, content: str, count: int = 3) -> list:
    """返回 [{"question": str, "answer": str}]。"""
    if USE_REAL_LLM:
        try:
            d = _post("/api/ai/extract-faq", {"title": title, "content": content, "count": count})
            items = d.get("items", [])
            if items:
                return items
        except Exception:
            pass
    # Mock / 失败兜底：模板问答，保证流程不断
    return [
        {"question": f"{title}什么时候开始？", "answer": "见推文中的时间安排，详情咨询主办方。"},
        {"question": f"{title}怎么报名？", "answer": "在活动详情页点击报名即可。"},
        {"question": f"{title}有综测加分吗？", "answer": "见推文中的综测说明。"},
    ]


# ---------- 能力 3：同义词 / 相似问题匹配 ----------

def similar_question(question: str, candidates: list) -> int:
    """返回最相似候选的下标，-1 表示都不相似。"""
    if not candidates:
        return -1
    if USE_REAL_LLM:
        try:
            d = _post("/api/ai/similar-question", {"question": question, "candidates": candidates})
            idx = int(d.get("index", -1))
            return idx if 0 <= idx < len(candidates) else -1
        except Exception:
            pass
    # Mock：退化为包含匹配
    norm = lambda s: "".join(ch for ch in s if ch.isalnum())
    q = norm(question)
    for i, c in enumerate(candidates):
        n = norm(c)
        if n and (n in q or q in n):
            return i
    return -1


# ---------- 兼容旧接口：通用文本生成 ----------

def gateway_chat(prompt: str) -> str:
    """通用文本生成入口（兼容旧调用），返回字符串。"""
    if USE_REAL_LLM:
        try:
            d = _post("/api/ai/chat", {"question": prompt})
            return d.get("answer", "")
        except Exception as e:
            return f"[网关不可用，已降级Mock] {e} | 通用回答：请咨询活动主办方。"
    return f"[Mock回答] 针对「{prompt[:80]}」：活动时间地点以活动详情页为准，综测加分见活动说明，报名问题请联系主办方。"
