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
    """报名截止时间是否已过；空值或无法解析视为未截止。"""
    if not deadline:
        return False
    s = str(deadline).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.now() >= datetime.strptime(s, fmt)
        except ValueError:
            continue
    return False
