"""POD-1 活动接口的【只读桩】——临时。

前端在「创建表单」和「学生报名」时会调 POD-1 的 GET /api/activities/{id}
读取人数/状态。单独跑本模块时缺这个接口会 404，故放一个只读桩兜底。
POD-1 联调后，本文件可整体删除。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

import db
from auth import get_current_user
from common import fail

router = APIRouter(prefix="/api/activities", tags=["activities-stub"])


@router.get("/{activity_id}")
def get_activity(activity_id: int, user: dict = Depends(get_current_user)):
    row = db.query_one("SELECT * FROM activities WHERE id = ?", (activity_id,))
    if row is None:
        fail(404, "活动不存在")
    return {"code": 0, "data": dict(row)}
