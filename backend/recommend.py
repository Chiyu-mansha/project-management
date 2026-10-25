"""推荐接口：接口 a(POST /api/recommend/score 打分入库) + 接口 b(GET /api/recommend/list 推荐列表)。

打分与推荐算法见「登录画像推荐-接口文档.md」：
打分项 ①报名条件(0/10) ②专业匹配 ③兴趣 ④技能锻炼(②③④ 按程度 0~10) ⑤操行分 ⑥创新分 ⑦综合素养评定积分(⑤⑥⑦ 0/10)
推荐：先筛截止时间 → 567 硬筛 → 综合分(专业0.4/兴趣0.3/技能0.3) → 前50%阈值。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

import db
from auth import require_role
from common import deadline_passed, fail, ok
from scoring import ScoringError, score_via_gateway

router = APIRouter(prefix="/api/recommend", tags=["recommend"])

WEIGHTS = {"major": 0.4, "interests": 0.3, "skills": 0.3}
NEED_KEYS = ("need_comprehensive_score", "need_conduct_score", "need_innovation_score")


def _profile_of(row) -> dict:
    return {
        "major": row["major"],
        "grade": row["grade"],
        "interests": row["interests"],
        "skills": row["skills"],
        "need_comprehensive_score": row["need_comprehensive_score"] or 0,
        "need_conduct_score": row["need_conduct_score"] or 0,
        "need_innovation_score": row["need_innovation_score"] or 0,
    }


def _activity_dto(a: dict) -> dict:
    return {
        "id": a["id"],
        "title": a["title"],
        "type": a["type"],
        "tags": a["tags"],
        "description": a["description"],
        "requirements": a["requirements"],
        "comprehensive_score": a["comprehensive_score"],
        "conduct_score": a["conduct_score"],
        "innovation_score": a["innovation_score"],
    }


@router.post("/score")
def score(user: dict = Depends(require_role("STUDENT"))):
    """接口 a：读画像 → 拉未截止的 published 活动 → 逐活动调网关打分 → 全量 upsert 入库。"""
    urow = db.query_one("SELECT * FROM users WHERE id = ?", (user["id"],))
    if urow is None:
        fail(404, "用户不存在")
    profile = _profile_of(urow)
    if not (profile["major"] or profile["interests"] or profile["skills"]) and not any(
        profile[k] for k in NEED_KEYS
    ):
        fail(400, "请先完善画像后再查看推荐")

    activities = [
        dict(r)
        for r in db.query_all("SELECT * FROM activities WHERE status = 'published'")
        if not deadline_passed(r["signup_deadline"])
    ]

    results = []  # (activity_id, signup_deadline, {eligible, scores, source})
    for act in activities:
        try:
            result = score_via_gateway(profile, _activity_dto(act))
        except ScoringError as e:
            fail(502, str(e))
        if result["eligible"] != 10:
            continue  # 报名条件不符，不计入打分表
        results.append((act["id"], act["signup_deadline"], result))

    with db.transaction() as conn:
        for act_id, deadline, result in results:
            s = result["scores"]
            conn.execute(
                """INSERT INTO activity_scores
                   (user_id, activity_id, signup_deadline, eligible, major_score, interests_score,
                    skills_score, conduct_score, innovation_score, comprehensive_score, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(user_id, activity_id) DO UPDATE SET
                     signup_deadline = excluded.signup_deadline,
                     eligible = excluded.eligible,
                     major_score = excluded.major_score,
                     interests_score = excluded.interests_score,
                     skills_score = excluded.skills_score,
                     conduct_score = excluded.conduct_score,
                     innovation_score = excluded.innovation_score,
                     comprehensive_score = excluded.comprehensive_score,
                     source = excluded.source,
                     updated_at = excluded.updated_at""",
                (
                    user["id"], act_id, deadline, result["eligible"],
                    s["major"], s["interests"], s["skills"],
                    s["conduct"], s["innovation"], s["comprehensive"], result["source"],
                ),
            )
    return ok({"scored": len(results), "total": len(activities)})


@router.get("/list")
def recommend_list(
    match_major: int = 0,
    match_interests: int = 0,
    match_skills: int = 0,
    need_conduct_score: int = 0,
    need_innovation_score: int = 0,
    need_comprehensive_score: int = 0,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(require_role("STUDENT")),
):
    """接口 b：只读 activity_scores 一张表，按算法筛排返回推荐。"""
    for value in (match_major, match_interests, match_skills,
                  need_conduct_score, need_innovation_score, need_comprehensive_score):
        if value not in (0, 1):
            fail(400, "偏好参数仅允许 0 或 1")

    selected_match = match_major or match_interests or match_skills
    selected_need = need_conduct_score or need_innovation_score or need_comprehensive_score
    if not selected_match and not selected_need:
        return ok({"items": [], "total": 0})

    rows = db.query_all("SELECT * FROM activity_scores WHERE user_id = ?", (user["id"],))

    items = []
    for r in rows:
        # ① 截止时间（读表内快照）
        if deadline_passed(r["signup_deadline"]):
            continue
        # ② 567 硬筛：被选中的积分项必须为 10
        if need_conduct_score and r["conduct_score"] != 10:
            continue
        if need_innovation_score and r["innovation_score"] != 10:
            continue
        if need_comprehensive_score and r["comprehensive_score"] != 10:
            continue

        # ③ 综合分（未勾选项系数为 0）
        total_weight = (
            (WEIGHTS["major"] if match_major else 0)
            + (WEIGHTS["interests"] if match_interests else 0)
            + (WEIGHTS["skills"] if match_skills else 0)
        )
        composite = round(
            (r["major_score"] or 0) * (WEIGHTS["major"] if match_major else 0)
            + (r["interests_score"] or 0) * (WEIGHTS["interests"] if match_interests else 0)
            + (r["skills_score"] or 0) * (WEIGHTS["skills"] if match_skills else 0),
            1,
        )
        # ④ 前 50% 阈值：综合分 ≥ 勾选权重总分 × 50%
        if total_weight > 0 and composite < total_weight * 10 * 0.5:
            continue

        items.append({
            "activity_id": r["activity_id"],
            "score": composite,
            "scores": {
                "major": r["major_score"],
                "interests": r["interests_score"],
                "skills": r["skills_score"],
            },
            "reasons": _reasons(r, match_major, match_interests, match_skills),
        })

    items.sort(key=lambda x: (x["score"], x["activity_id"]), reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return ok({"items": items[start:start + page_size], "total": total})


def _fmt_score(value) -> str:
    """把 0~10 分值格式化成整数或一位小数（去掉无意义的 .0）。"""
    try:
        f = float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        f = 0.0
    return str(int(f)) if f == int(f) else str(round(f, 1))


def _reasons(r, match_major, match_interests, match_skills):
    """勾了匹配维度才给理由、内容带分数（如「专业匹配得分6/10」）；只勾积分需求不给理由。"""
    reasons = []
    if match_major:
        reasons.append(f"专业匹配得分{_fmt_score(r['major_score'])}/10")
    if match_interests:
        reasons.append(f"兴趣得分{_fmt_score(r['interests_score'])}/10")
    if match_skills:
        reasons.append(f"技能锻炼得分{_fmt_score(r['skills_score'])}/10")
    return reasons
