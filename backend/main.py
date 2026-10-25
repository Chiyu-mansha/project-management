"""校园活动智能通知&报名助理 后端入口。

POD-1 活动/FAQ/答疑 + POD-2 报名管理(PM 合并仪式集成)。
启动:uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db as init_db_pod1
from activity import activity_router
from faq import faqs_router, faqs_auto_router, qa_router
from notification import notifications_router

import db
from auth_routes import router as auth_router
from profile import router as profile_router
from recommend import router as recommend_router
from forms import router as forms_router
from registrations import router as registrations_router

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

app = FastAPI(title="校园活动智能通知&报名助理")

# 开发阶段全放开，部署时收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- POD-1:活动域 + FAQ/答疑 ----
init_db_pod1()
app.include_router(activity_router)
app.include_router(faqs_router)
app.include_router(faqs_auto_router)
app.include_router(qa_router)
app.include_router(notifications_router)

# ---- POD-2:认证/画像/推荐 + 报名域(POD-1 正式活动接口已合入) ----
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(recommend_router)
app.include_router(forms_router)
app.include_router(registrations_router)


@app.get("/api/hello")
def hello():
    return {"message": "backend ok"}


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    # 把 detail 直接作为 body，统一成 {code, message}，不做 FastAPI 默认的 {"detail": ...} 包装
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": exc.status_code, "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers or {})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"code": 400, "message": "参数错误"})


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error_handler(request: Request, exc: sqlite3.IntegrityError):
    return JSONResponse(status_code=409, content={"code": 409, "message": "资源冲突"})
