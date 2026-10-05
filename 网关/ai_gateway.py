"""AI 网关（初版 v1）：统一封装大模型调用，内置 Mock 降级。

与 backend/llm_gateway.py 保持同一套约定：
- 默认走 Mock（演示/无 Key 不翻车）
- 设 USE_REAL_LLM=1 才真正调用大模型（百炼 qwen-plus）
- 调用失败自动降级到 Mock，绝不抛出未捕获异常

对外统一入口（各 POD 只调这里，不直连大模型）：
    gateway_chat(prompt)            -> str   文本生成 / 对话兜底（最常用）
    generate_text(prompt)           -> str   推文/文案生成（= gateway_chat 的语义化别名）

三大 AI 接入点对应的能力函数：
    # 1) 智能答疑
    chat(question)                  -> dict  返回 {"answer", "source"}
    # 2) 推文关键问题提取
    extract_faq(title, content)     -> list  返回 [{"question", "answer"}]
    # 3) 高频问题同义词匹配
    similar_question(question, cands) -> int 返回候选下标，-1 表示都不相似

扩展：
    recommend(profile, candidates)  -> list  个性化推荐，返回 [{"activity_id", "reason"}]
"""
import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL = os.getenv("LLM_MODEL", "qwen-plus")
# 与 backend/llm_gateway.py 一致：默认 Mock，显式开关才走真实网关
USE_REAL_LLM = os.getenv("USE_REAL_LLM") == "1"

SYSTEM_EDITOR = "你是一名高校活动推文编辑，擅长写校园公众号/社群推文。"
SYSTEM_QA = "你是一名校园活动智能助手，只回答校园活动、竞赛、电子票、综测加分相关问题，无关问题礼貌拒绝。"


def _chat_completion(prompt: str, system: str = "") -> str:
    """真实调用百炼（OpenAI 兼容 /chat/completions），失败抛异常由上层降级。"""
    if not API_KEY:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": MODEL, "messages": messages},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ---------- 统一入口：文本生成 / 兜底 ----------

def gateway_chat(prompt: str) -> str:
    """最常用的统一入口，输入提示词返回文本；失败自动降级 Mock。"""
    if USE_REAL_LLM:
        try:
            return _chat_completion(prompt, system=SYSTEM_EDITOR)
        except Exception as e:
            return f"[真实网关失败，已降级Mock] {e} | 针对「{prompt[:50]}」的通用回答：请咨询活动主办方。"
    return (
        f"[Mock回答] 针对「{prompt[:80]}」：活动时间地点以活动详情页为准，"
        "综测加分见活动说明，报名问题请联系主办方。"
    )


def generate_text(prompt: str) -> str:
    """推文/文案生成，语义化别名，等价于 gateway_chat。"""
    return gateway_chat(prompt)


# ---------- 能力 2：推文关键问题提取 ----------

def extract_faq(title: str, content: str, count: int = 3) -> list:
    """读推文标题+正文，提取常见问答，返回 [{"question": str, "answer": str}]。

    用法：推文发布后由 member-2 触发，结果存为待审核 FAQ。
    """
    if USE_REAL_LLM:
        try:
            prompt = (
                f"活动标题：{title}\n推文内容：{content[:2000]}\n"
                f"请提取 {count} 个同学最可能问的问题，只返回 JSON 数组，"
                '格式：[{"question":"...","answer":"..."}]'
            )
            raw = _chat_completion(prompt, system=SYSTEM_EDITOR)
            s, e = raw.find("["), raw.rfind("]") + 1
            if s >= 0 and e > s:
                data = json.loads(raw[s:e])
                return [
                    {"question": str(i.get("question", "")).strip(), "answer": str(i.get("answer", "")).strip()}
                    for i in data
                    if i.get("question")
                ][:count]
        except Exception:
            pass
    # Mock / 解析失败兜底：模板问答，保证流程不断
    return [
        {"question": f"{title}什么时候开始？", "answer": "见推文中的时间安排，详情咨询主办方。"},
        {"question": f"{title}怎么报名？", "answer": "在活动详情页点击报名即可。"},
        {"question": f"{title}有综测加分吗？", "answer": "见推文中的综测说明。"},
    ]


# ---------- 能力 3：同义词 / 相似问题匹配 ----------

def similar_question(question: str, candidates: list) -> int:
    """判断 question 是否与 candidates 里的某个问题同义。

    candidates 为问题字符串列表。
    返回最相似候选的下标；都不相似返回 -1。
    用于「高频问题沉淀」：把不同问法归为同一类。
    """
    if not candidates:
        return -1
    if USE_REAL_LLM:
        try:
            listing = "\n".join(f"{i}. {c}" for i, c in enumerate(candidates))
            prompt = (
                f"下面哪些问题和「{question}」是同一个意思（只是问法不同）？"
                f"只返回最匹配的编号数字，没有则返回 -1。\n{listing}"
            )
            raw = _chat_completion(prompt, system="你是中文语义匹配助手。").strip()
            m = re.search(r"-?\d+", raw)
            if m:
                idx = int(m.group())
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


# ---------- 能力 1：智能答疑（对话） ----------

def chat(question: str) -> dict:
    """输入问题，返回 {"answer": str, "source": "llm"|"mock"}。"""
    if USE_REAL_LLM:
        try:
            return {"answer": _chat_completion(question, system=SYSTEM_QA), "source": "llm"}
        except Exception as e:
            return {"answer": f"[真实网关失败，已降级Mock] {e}", "source": "mock"}
    return {
        "answer": f"[Mock答疑] 关于「{question[:30]}」的问题，请查看活动详情页或联系活动负责人。",
        "source": "mock",
    }


# ---------- 个性化推荐 ----------

def recommend(profile: dict, candidates: list) -> list:
    """输入用户画像和候选活动，返回 [{"activity_id", "reason"}]。MVP 先走规则。"""
    result = []
    for c in candidates[:3]:
        result.append(
            {"activity_id": c.get("id"), "reason": "匹配你的兴趣/培养方案（Mock 推荐）"}
        )
    return result


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台也能打印
    print("=== gateway_chat（默认 Mock）===")
    print(gateway_chat("测试活动：篮球赛"))
    print("\n=== chat 智能答疑（默认 Mock）===")
    print(chat("活动什么时候开始？"))
    print("\n=== extract_faq 推文提取（默认 Mock）===")
    print(extract_faq("编程马拉松报名启动", "10月20日截止，3-5人组队，有综测加分。"))
    print("\n=== similar_question 同义匹配（默认 Mock）===")
    cands = ["报名截止什么时候", "在哪里举办"]
    print(similar_question("什么时候不能报名了", cands))
    print("\n=== recommend（默认 Mock）===")
    print(recommend({"interests": "篮球"}, [{"id": 1, "tags": "篮球"}, {"id": 2, "tags": "讲座"}]))
