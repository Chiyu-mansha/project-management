"""报名管理后端入口。

启动：uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import os
import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db
from common import ok
from activities_stub import router as activities_stub_router
from forms import router as forms_router
from registrations import router as registrations_router

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

app = FastAPI(title="校园活动智能通知&报名助理 - 报名管理")

# 开发阶段全放开，部署时收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forms_router)
app.include_router(registrations_router)
app.include_router(activities_stub_router)


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


class DevTokenBody(BaseModel):
    role: str
    id: int


@app.post("/api/dev/token")
def dev_token(body: DevTokenBody):
    """开发环境专用：按 role+id 生成临时 token（production 禁用）。"""
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise HTTPException(404, detail={"code": 404, "message": "资源不存在"})
    role = body.role.lower()
    if role == "student":
        if db.query_one("SELECT id FROM users WHERE id = ?", (body.id,)) is None:
            raise HTTPException(404, detail={"code": 404, "message": "用户不存在"})
    elif role == "organizer":
        if db.query_one("SELECT id FROM organizers WHERE id = ?", (body.id,)) is None:
            raise HTTPException(404, detail={"code": 404, "message": "发布者不存在"})
    else:
        raise HTTPException(400, detail={"code": 400, "message": "role 仅支持 student / organizer"})
    return ok({"token": f"{role}:{body.id}"})
