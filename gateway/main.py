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
    activity_id: int
    style: str = "简约"  # 简约 / 活泼 / 正式


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
    # TODO(成员2): 按 activity_id 查 activities 表，拼入活动信息，再调网关
    prompt = f"为活动 id={req.activity_id} 写一篇「{req.style}」风格的校园推文。"
    return {"content": ai_gateway.generate_text(prompt)}


# ---------- 能力 1：智能答疑（对话） ----------

@app.post("/api/ai/chat")
def chat(req: ChatReq):
    # TODO(成员3): 先查 faqs 表，命中直接返回 source="faq"，未命中再调本接口兜底
    result = ai_gateway.chat(req.question)
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
    # TODO(POD-2): 按 user_id 查画像 + 拉活动候选列表，再调网关
    return {"items": ai_gateway.recommend({"user_id": req.user_id}, [])}
