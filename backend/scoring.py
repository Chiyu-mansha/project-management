"""AI 打分网关客户端：调用 POD-1 网关 /api/ai/score。

契约（见「登录画像推荐-接口文档.md」第 7 节）：
请求 {profile, activity}；响应 {eligible(0/10), scores{major,interests,skills,conduct,innovation,comprehensive}, source}。
路径 /api/ai/score 为临时占位，联调时以 POD-1 实际确认为准（需在原位替换）。
"""
from __future__ import annotations

import os

import requests

GATEWAY_URL = os.getenv("AI_GATEWAY_URL", "http://127.0.0.1:8100").rstrip("/")
TIMEOUT = 10

SCORE_KEYS = ("major", "interests", "skills", "conduct", "innovation", "comprehensive")


class ScoringError(Exception):
    """网关不可用 / 响应不合法。不做兜底打分，由上层提示重试。"""


def score_via_gateway(profile: dict, activity: dict) -> dict:
    """调用网关打分，返回 {eligible, scores, source}；失败抛 ScoringError。"""
    try:
        r = requests.post(
            f"{GATEWAY_URL}/api/ai/score",
            json={"profile": profile, "activity": activity},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # 连接失败 / 超时 / 非 2xx / 非法 JSON
        raise ScoringError("AI 打分服务不可用，请稍后重试") from e

    scores = data.get("scores") or {}
    for key in SCORE_KEYS:
        value = scores.get(key)
        if value is None or isinstance(value, bool):
            raise ScoringError("AI 打分响应缺少字段或分值非法")
        try:
            fv = float(value)
        except (TypeError, ValueError):
            raise ScoringError("AI 打分响应缺少字段或分值非法")
        if not 0 <= fv <= 10:
            raise ScoringError("AI 打分分值越界")

    eligible = data.get("eligible")
    if eligible not in (0, 10, False, True):
        raise ScoringError("AI 打分 eligible 非法")

    return {
        "eligible": 10 if eligible in (10, True) else 0,
        "scores": {k: float(scores[k]) for k in SCORE_KEYS},
        "source": data.get("source", "llm"),
    }
