"""AI 网关独立服务入口（各 POD 通过 HTTP 调用）。

网关作为独立服务运行，其它模块（backend 等）通过 HTTP 调 /api/ai/*，不直接 import。

启动：
    cd 网关
    uvicorn main:app --reload --port 8100

默认走 Mock；在 网关/.env 设 USE_REAL_LLM=1 并填 Key 后走真实大模型。
"""
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ai_gateway

app = FastAPI(title="AI 网关服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/hello")
def hello():
    return {"message": "ai gateway ok"}


# ---------- 请求体 ----------

class GenerateArticleReq(BaseModel):
    style: str = "简约"                 # 简约 / 活泼 / 正式
    activity: dict = {}                 # 活动信息，由 backend 查表后传入
    activity_id: Optional[int] = None   # 保留 id 用于日志，可选


class ChatReq(BaseModel):
    question: str
    activity_id: Optional[int] = None


class ExtractFaqReq(BaseModel):
    title: str
    content: str
    count: int = 3


class SimilarReq(BaseModel):
    question: str
    candidates: List[str] = []


class RecommendReq(BaseModel):
    user_id: int


# ---------- 能力 2：推文关键问题提取 ----------

@app.post("/api/ai/generate-article")
def generate_article(req: GenerateArticleReq):
    # 网关不查库，只负责把 member-2 传过来的 activity 对象拼成 Prompt
    a = req.activity or {}
    prompt = "\n".join([
        f"请为下面这个活动写一篇「{req.style}」风格的校园推文，用 Markdown 格式：",
        f"- 标题：{a.get('title', '')}",
        f"- 主办方：{a.get('organizer', '')}",
        f"- 类型：{a.get('type', '')}",
        f"- 时间：{a.get('start_time', '')} ~ {a.get('end_time', '')}",
        f"- 地点：{a.get('location', '')}",
        f"- 报名截止：{a.get('signup_deadline', '')}",
        f"- 综测加分：{a.get('zongce_score', '')}",
        f"- 简介：{a.get('description', '')}",
    ])
    return {"content": ai_gateway.generate_text(prompt=prompt)}

# ---------- 能力 1：智能答疑（对话） ----------

@app.post("/api/ai/chat")
def chat(req: ChatReq):
    # 透传 activity_id
    result = ai_gateway.chat(req.question, activity_id=req.activity_id)
    return {"answer": result["answer"], "source": result["source"]}


# ---------- 能力 2：推文关键问题提取 ----------

@app.post("/api/ai/extract-faq")
def extract_faq(req: ExtractFaqReq):
    return {"items": ai_gateway.extract_faq(req.title, req.content, req.count)}


# ---------- 能力 3：同义词 / 相似问题匹配 ----------

@app.post("/api/ai/similar-question")
def similar_question(req: SimilarReq):
    return {"index": ai_gateway.similar_question(req.question, req.candidates)}


# ---------- 扩展：个性化推荐 ----------

@app.post("/api/ai/recommend")
def recommend(req: RecommendReq):
    # TODO(POD-2): 后续按 user_id 查画像 + 拉活动候选列表（查库后替换掉 mock_candidates）
    # 临时 Mock 几个候选活动，验证网关透传和推荐逻辑
    mock_candidates = [
        {"id": 1, "tags": "编程"},
        {"id": 2, "tags": "篮球"},
        {"id": 3, "tags": "讲座"}
    ]
    return {"items": ai_gateway.recommend({"user_id": req.user_id}, mock_candidates)}