"""调用「AI 网关服务」的 HTTP 客户端（方案 2：网关独立跑，本模块只发 HTTP 请求）。

网关服务默认地址：http://127.0.0.1:8100（见 网关/main.py）
- 未开启真实网关 / 请求失败 / 超时 → 自动降级本地 Mock，保证答疑与提取不中断
- 开启方式：backend/.env 里设 USE_REAL_LLM=1
"""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

GATEWAY_URL = os.getenv("AI_GATEWAY_URL", "http://127.0.0.1:8100").rstrip("/")
USE_REAL_LLM = os.getenv("USE_REAL_LLM") == "1"
TIMEOUT = 75


def _post(path: str, payload: dict) -> dict:
    r = requests.post(f"{GATEWAY_URL}{path}", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# ---------- 能力 1：智能答疑（对话） ----------

def chat(question: str, activity_id=None, history=None, activity_context=None) -> dict:
    """返回 {"answer": str, "source": "llm"|"mock"}。"""
    if USE_REAL_LLM:
        try:
            payload = {"question": question, "activity_id": activity_id}
            if history:
                payload["history"] = history
            if activity_context:
                payload["activity_context"] = activity_context
            d = _post("/api/ai/chat", payload)
            return {"answer": d.get("answer", ""), "source": d.get("source", "llm")}
        except Exception as e:
            print(f"[FAQ gateway error] {e}")
            return {"answer": "AI 服务暂时不可用，请稍后重试或联系活动负责人。", "source": "mock"}
    return {
        "answer": f"[Mock答疑] 关于「{question[:30]}」的问题，请查看活动详情页或联系活动负责人。",
        "source": "mock",
    }


def chat_stream(question, activity_id=None, history=None, activity_context=None, meta=None):
    """SSE 流式答疑：yield dict 事件 {"delta": str} / {"done": True, "source": ...}。"""
    if not USE_REAL_LLM:
        if meta is not None:
            meta["source"] = "mock"
        yield {"delta": f"[Mock答疑] 关于「{question[:30]}」的问题，请查看活动详情页或联系活动负责人。"}
        yield {"done": True, "source": "mock"}
        return
    payload = {"question": question, "activity_id": activity_id}
    if history:
        payload["history"] = history
    if activity_context:
        payload["activity_context"] = activity_context
    try:
        with requests.post(
            f"{GATEWAY_URL}/api/ai/chat-stream",
            json=payload,
            timeout=TIMEOUT,
            stream=True,
        ) as r:
            r.raise_for_status()
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw[5:].strip() if raw.startswith("data:") else raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                if event.get("delta"):
                    yield {"delta": event["delta"]}
                elif event.get("done"):
                    if meta is not None:
                        meta["source"] = event.get("source", "llm")
                    yield {"done": True, "source": event.get("source", "llm")}
                elif event.get("error"):
                    if meta is not None:
                        meta["source"] = "mock"
                    yield {"error": "AI 服务暂时不可用，请稍后重试"}
    except Exception as e:
        print(f"[FAQ gateway stream error] {e}")
        if meta is not None:
            meta["source"] = "mock"
        yield {"delta": "AI 服务暂时不可用，请稍后重试或联系活动负责人。"}
        yield {"done": True, "source": "mock"}


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
