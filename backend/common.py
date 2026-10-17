"""统一返回格式、异常与时间工具。"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException


def ok(data=None) -> dict:
    """成功返回：{code: 0, data}"""
    return {"code": 0, "data": data}


def fail(code: int, message: str):
    """失败：抛 HTTPException，body 为 {code, message}，HTTP 状态码与 code 一致。"""
    raise HTTPException(status_code=code, detail={"code": code, "message": message})


def to_iso(value) -> str | None:
    """DB 里的 'YYYY-MM-DD HH:MM:SS' 转成 ISO 8601 'YYYY-MM-DDTHH:MM:SS'。"""
    if value is None:
        return None
    return str(value).replace(" ", "T")


def deadline_passed(deadline) -> bool:
    """支持 ISO 8601 的时区与小数秒；坏日期不能绕过截止校验。"""
    if not deadline:
        return False
    try:
        parsed = datetime.fromisoformat(str(deadline).strip().replace("Z", "+00:00"))
    except ValueError:
        fail(400, "活动报名截止时间无效，请联系发布者")
    return datetime.now(parsed.tzinfo) >= parsed
