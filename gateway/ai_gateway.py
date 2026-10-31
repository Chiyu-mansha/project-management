"""AI 网关（初版 v1）：统一封装大模型调用，内置 Mock 降级。

与 backend/llm_gateway.py 保持同一套约定：
- 默认走 Mock（演示/无 Key 不翻车）
- 设 USE_REAL_LLM=1 才真正调用大模型（百炼 qwen-plus）
- 调用失败自动降级到 Mock，绝不抛出未捕获异常

对外统一入口（各 POD 只调这里，不直连大模型）：
    gateway_chat(prompt)              -> str   文本生成 / 对话兜底（最常用）
    generate_text(prompt, system=None) -> str  推文/文案生成（可传 system 覆盖风格）

三大 AI 接入点对应的能力函数：
    # 1) 智能答疑
    chat(question, system=None)       -> dict  返回 {"answer", "source"}
    # 2) 推文关键问题提取
    extract_faq(title, content)       -> list  返回 [{"question", "answer"}]
    # 3) 高频问题同义词匹配
    similar_question(question, cands) -> int   返回候选下标，-1 表示都不相似

扩展：
    recommend(profile, candidates)    -> list  个性化推荐，返回 [{"activity_id", "reason"}]
    score_activity(profile, activity) -> dict  AI 打分，返回各项匹配分
"""
import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
MODEL = os.getenv("LLM_MODEL", "qwen-plus")

if os.getenv("AI_MOCK", "").lower() in ("1", "true", "yes"):
    USE_REAL_LLM = False
else:
    USE_REAL_LLM = os.getenv("USE_REAL_LLM") == "1"

SYSTEM_EDITOR = (
    "你是高校活动推文编辑。请严格按下面的 Markdown 结构输出（硬性要求）：\n"
    "# 主标题（一句话吸睛，可带 emoji）\n"
    "> 一句亮点宣传语\n\n"
    "## ✨ 活动亮点\n"
    "- 亮点一\n- 亮点二\n- 亮点三\n\n"
    "## 📅 时间地点\n"
    "- **时间**：…\n- **地点**：…\n\n"
    "---\n\n"
    "## 🔗 报名方式\n"
    "…\n\n"
    "规则：主标题用 #，分节标题用 ##，重点句用 > 引用，分节间用 --- 分隔，关键信息 **加粗**；"
    "语言贴近大学生，适度 emoji；只写活动信息里有的内容，不编造；300~500 字。"
)
SYSTEM_QA = "你是一名校园活动智能助手，只回答校园活动、竞赛、电子票、综测加分相关问题，无关问题礼貌拒绝。"


def _chat_completion(prompt: str, system: str = "", history: list | None = None) -> str:
    """真实调用百炼（OpenAI 兼容 /chat/completions），失败抛异常由上层降级。"""
    if not API_KEY:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    for turn in history or []:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role", "")).strip()
        content = str(turn.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": MODEL, "messages": messages},
        timeout=60,
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


def generate_text(prompt: str = None, system: str = None, activity_id: int = None, style: str = None) -> str:
    """推文/文案生成，支持通过 activity_id 和 style 透传上下文，失败自动降级 Mock。"""
    if activity_id:
        prompt = f"为活动 id={activity_id} 写一篇"
        if style:
            prompt += f"「{style}」风格的"
        prompt += "校园推文。"
    elif not prompt:
        prompt = "写一篇校园推文。"
        
    if system:
        if USE_REAL_LLM:
            try:
                return _chat_completion(prompt, system=system)
            except Exception as e:
                return f"[真实网关失败，已降级Mock] {e} | 针对「{prompt[:50]}」的通用回答：请咨询活动主办方。"
        return f"[Mock回答] 针对「{prompt[:80]}」：活动时间地点以活动详情页为准，综测加分见活动说明，报名问题请联系主办方。"
    return gateway_chat(prompt)


# ---------- 能力 2：推文关键问题提取 ----------

def extract_faq(title: str, content: str, count: int = 3) -> list:
    """读推文标题+正文，提取常见问答，返回 [{"question": str, "answer": str}]。"""
    if USE_REAL_LLM:
        try:
            prompt = (
                f"以下是活动信息：\n{title}\n{content[:2000]}\n\n"
                f"请根据以上信息，提取 {count} 个同学最可能问的问题，并给出准确、具体的答案"
                f"（答案必须来自上面的活动信息，不要编造；信息里没有的就答“请咨询主办方”）。"
                "只返回 JSON 数组，格式：[{\"question\":\"...\",\"answer\":\"...\"}]"
            )
            raw = _chat_completion(prompt, system=SYSTEM_EDITOR)
            clean_raw = raw.replace("```json", "").replace("```", "").strip()
            s, e = clean_raw.find("["), clean_raw.rfind("]") + 1
            if s >= 0 and e > s:
                data = json.loads(clean_raw[s:e])
                return [
                    {"question": str(i.get("question", "")).strip(), "answer": str(i.get("answer", "")).strip()}
                    for i in data
                    if i.get("question")
                ][:count]
        except Exception:
            pass
    return [
        {"question": f"{title}什么时候开始？", "answer": "见推文中的时间安排，详情咨询主办方。"},
        {"question": f"{title}怎么报名？", "answer": "在活动详情页点击报名即可。"},
        {"question": f"{title}有综测加分吗？", "answer": "见推文中的综测说明。"},
    ]


# ---------- 能力 3：同义词 / 相似问题匹配 ----------

def similar_question(question: str, candidates: list) -> int:
    """判断 question 是否与 candidates 里的某个问题同义。"""
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
            if re.fullmatch(r"-?\d+", raw):
                idx = int(raw)
                return idx if 0 <= idx < len(candidates) else -1
            return -1
        except Exception:
            pass
    norm = lambda s: "".join(ch for ch in s if ch.isalnum())
    q = norm(question)
    for i, c in enumerate(candidates):
        n = norm(c)
        if n and (n in q or q in n):
            return i
    return -1


# ---------- 能力 1：智能答疑（对话） ----------

def chat(question: str, system: str = None, activity_id: int = None, history: list = None, activity_context: str = None) -> dict:
    """输入问题，返回 {"answer": str, "source": "llm"|"mock"}。"""
    if activity_id and not activity_context:
        question = f"【当前活动ID：{activity_id}】关于该活动的问题：{question}"

    sys_prompt = system or SYSTEM_QA
    if activity_context:
        sys_prompt = f"{sys_prompt}\n\n当前活动信息（优先据此回答，不要编造）：\n{activity_context}"

    if USE_REAL_LLM:
        try:
            return {"answer": _chat_completion(question, system=sys_prompt, history=history), "source": "llm"}
        except Exception as e:
            print(f"\n❌ 真实 API 调用失败，错误原因: {repr(e)}\n")
            return {"answer": f"[真实网关失败，已降级Mock] {e}", "source": "mock"}
            
    return {
        "answer": f"[Mock答疑] 关于「{question[:30]}」的问题，请查看活动详情页或联系活动负责人。",
        "source": "mock",
    }


# ---------- 扩展：个性化推荐 ----------

def recommend(profile: dict, candidates: list) -> list:
    """输入用户画像和候选活动，返回 [{"activity_id", "reason"}]。"""
    try:
        if USE_REAL_LLM:
            return _recommend_by_llm(profile, candidates)
        raise RuntimeError("USE_REAL_LLM 未开启，走 Mock")
    except Exception:
        return _mock_recommend(profile, candidates)


def _recommend_by_llm(profile: dict, candidates: list) -> list:
    return _mock_recommend(profile, candidates)


def _mock_recommend(profile: dict, candidates: list) -> list:
    result = []
    for c in candidates[:3]:
        result.append(
            {"activity_id": c.get("id"), "reason": "匹配你的兴趣/培养方案（Mock 推荐）"}
        )
    return result


# ---------- 扩展：AI 打分 ----------

def score_activity(profile: dict, activity: dict) -> dict:
    """输入用户画像和单个活动，返回各项匹配分及是否满足报名条件（纯数据）。"""
    if not USE_REAL_LLM:
        return _mock_score(profile, activity)

    sys_prompt = (
        "你是一个专业的校园活动匹配打分助手。你需要根据用户画像和活动信息，输出严格的 JSON 格式打分。"
        "打分规则：\n"
        "1. eligible: 是否满足报名条件(0 或 10)。如果活动有硬性专业/年级要求且不符，返回0；否则返回10。\n"
        "2. scores.major: 专业匹配度(0-10)。\n"
        "3. scores.interests: 兴趣匹配度(0-10)。根据 profile.interests 和 activity.tags 的交集判断。\n"
        "4. scores.skills: 技能匹配度(0-10)。\n"
        "5. scores.comprehensive/conduct/innovation: 积分命中(0 或 10)。如果用户需要该积分(值为1)且活动提供该积分(值>0)，则返回10，否则返回0。\n"
        "必须严格只返回 JSON 对象，不要包含 markdown 标记或多余文字。"
    )
    
    user_prompt = f"""
【用户画像】
专业: {profile.get('major', '未知')}
年级: {profile.get('grade', '未知')}
兴趣: {profile.get('interests', '无')}
技能: {profile.get('skills', '无')}
需要的积分: 综测={profile.get('need_comprehensive_score', 0)}, 品行={profile.get('need_conduct_score', 0)}, 创新={profile.get('need_innovation_score', 0)}

【活动信息】
标题: {activity.get('title', '')}
类型: {activity.get('type', '')}
标签: {activity.get('tags', '')}
描述: {activity.get('description', '')}
报名条件: {activity.get('requirements', '')}
提供的积分: 综测={activity.get('comprehensive_score', 0)}, 品行={activity.get('conduct_score', 0)}, 创新={activity.get('innovation_score', 0)}

请输出打分 JSON，格式示例：
{{
  "eligible": 10,
  "scores": {{
    "major": 9,
    "interests": 8,
    "skills": 8,
    "conduct": 0,
    "innovation": 10,
    "comprehensive": 10
  }}
}}
"""

    try:
        raw = _chat_completion(user_prompt, system=sys_prompt)
        clean_raw = raw.replace("```json", "").replace("```", "").strip()
        s, e = clean_raw.find("{"), clean_raw.rfind("}") + 1
        if s >= 0 and e > s:
            data = json.loads(clean_raw[s:e])
            data["source"] = "llm"
            return data
        raise ValueError("大模型未返回合法的 JSON 结构")
    except Exception as e:
        print(f"\n❌ AI 打分失败，降级 Mock: {e}\n")
        return _mock_score(profile, activity)


def _mock_score(profile: dict, activity: dict) -> dict:
    """大模型失败时的兜底打分逻辑（基于简单规则）"""
    interests = profile.get("interests", "").split(",")
    tags = activity.get("tags", "").split(",")
    has_common = any(i.strip() in tags for i in interests if i.strip())
    
    return {
        "eligible": 10,
        "scores": {
            "major": 8 if has_common else 5,
            "interests": 9 if has_common else 5,
            "skills": 5,
            "conduct": 10 if profile.get("need_conduct_score") and activity.get("conduct_score", 0) > 0 else 0,
            "innovation": 10 if profile.get("need_innovation_score") and activity.get("innovation_score", 0) > 0 else 0,
            "comprehensive": 10 if profile.get("need_comprehensive_score") and activity.get("comprehensive_score", 0) > 0 else 0
        },
        "source": "mock"
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("=== score_activity（默认 Mock）===")
    print(score_activity({"interests": "算法,竞赛"}, {"title": "软件创新大赛", "tags": "算法,Python"}))