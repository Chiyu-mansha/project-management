"""AI 网关独立服务入口（各 POD 通过 HTTP 调用）。

网关作为独立服务运行，其它模块（backend 等）通过 HTTP 调 /api/ai/*，不直接 import。
启动：uvicorn main:app --reload --port 8100
"""
from typing import List, Optional, Dict, Any

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
    style: str = "简约"
    activity: dict = {}
    activity_id: Optional[int] = None


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


class ScoreReq(BaseModel):
    profile: Dict[str, Any]
    activity: Dict[str, Any]


# ---------- 接口路由 ----------

_STYLE_GUIDE = {
    "简约": "简洁清晰，少修饰，直说重点",
    "活泼": "轻松有趣，多用 emoji 和网络用语，有感染力",
    "正式": "正式得体，用词规范，适合官方通知",
}


@app.post("/api/ai/generate-article")
def generate_article(req: GenerateArticleReq):
    a = req.activity or {}
    guide = _STYLE_GUIDE.get(req.style, _STYLE_GUIDE["简约"])
    prompt = "\n".join([
        f"请为下面这个校园活动写一篇「{req.style}」风格的推广推文（{guide}）。",
        "",
        "活动信息：",
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



class PolishReq(BaseModel):
    content: str
    style: str = "简约"


@app.post("/api/ai/polish-article")
def polish_article(req: PolishReq):
    """润色：改写已有推文，保持信息不变，只优化表达和排版。"""
    guide = _STYLE_GUIDE.get(req.style, _STYLE_GUIDE["简约"])
    prompt = (
        f"请把下面这段校园推文改写得更「{req.style}」（{guide}），"
        f"保持信息不变，只优化表达、排版和吸引力，仍用 Markdown 格式：\n\n{req.content}"
    )
    return {"content": ai_gateway.generate_text(prompt=prompt)}

# ---------- 能力 1：智能答疑（对话） ----------

@app.post("/api/ai/chat")
def chat(req: ChatReq):
    result = ai_gateway.chat(req.question, activity_id=req.activity_id)
    return {"answer": result["answer"], "source": result["source"]}


@app.post("/api/ai/extract-faq")
def extract_faq(req: ExtractFaqReq):
    return {"items": ai_gateway.extract_faq(req.title, req.content, req.count)}


@app.post("/api/ai/similar-question")
def similar_question(req: SimilarReq):
    return {"index": ai_gateway.similar_question(req.question, req.candidates)}


@app.post("/api/ai/recommend")
def recommend(req: RecommendReq):
    mock_candidates = [
        {"id": 1, "tags": "编程"},
        {"id": 2, "tags": "篮球"},
        {"id": 3, "tags": "讲座"}
    ]
    return {"items": ai_gateway.recommend({"user_id": req.user_id}, mock_candidates)}


# ---------- 扩展：AI 打分 ----------
@app.post("/api/ai/score")
def score(req: ScoreReq):
    """POD-2 推荐页调用：对单个活动打分。返回纯数据，不包 code/data"""
    return ai_gateway.score_activity(req.profile, req.activity)
