"""POD-3 凭证域：签到核销、名单确认、电子签章、凭证仓库。

写入共享 schema v1.5 的 credentials 表。身份使用全组简单 token
（``student:<id>`` / ``organizer:<id>``）。学生必须先出现在
registration_members 中才能签到。
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import db
from auth import get_current_user, require_role
from common import fail, ok
from storage import (
    CredentialPdfTemplate,
    HttpSealService,
    LocalFileStorage,
    LocalSealService,
    build_csv,
    build_xlsx,
)


BASE_DIR = Path(__file__).resolve().parent
STORAGE_ROOT = os.getenv("POD3_STORAGE_ROOT", str(BASE_DIR / "storage"))
file_storage = LocalFileStorage(STORAGE_ROOT)
pdf_template = CredentialPdfTemplate()
seal_service = (
    HttpSealService(os.environ["SEAL_SERVICE_URL"])
    if os.getenv("SEAL_SERVICE_URL")
    else LocalSealService()
)

router = APIRouter(prefix="/api", tags=["pod3-credentials"])


class CheckInRequest(BaseModel):
    channel: Literal["QR", "MANUAL", "IMPORT"] = "QR"


class ConfirmRequest(BaseModel):
    credential_ids: list[int] = Field(..., min_length=1, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)


class SignRequest(BaseModel):
    seal_id: str = "campus-default"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def init_pod3_tables() -> None:
    """补共享库上 POD-3 需要的索引；不创建 users/activities。"""
    with db.transaction() as conn:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_credentials_activity_user "
            "ON credentials (activity_id, user_id)"
        )


def _activity_or_404(activity_id: int) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM activities WHERE id = ?", (activity_id,))
    if row is None:
        fail(404, "活动不存在")
    return dict(row)


def _require_organizer(user: dict[str, Any], activity: dict[str, Any]) -> None:
    if user["role"] != "ORGANIZER" or int(activity.get("organizer_id") or 0) != int(user["id"]):
        fail(403, "只有该活动的发布者可以操作签到名单")


def _registered_member(activity_id: int, user_id: int) -> bool:
    return db.query_one(
        "SELECT id FROM registration_members WHERE activity_id = ? AND user_id = ?",
        (activity_id, user_id),
    ) is not None


def _credential_dict(row: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "activity_id": row["activity_id"],
        "user_id": row["user_id"],
        "status": row["status"],
        "checkin_time": row["checkin_time"],
        "confirmed_at": row.get("confirmed_at"),
        "signed_at": row.get("signed_at"),
        "pdf_path": row.get("pdf_path"),
        "comprehensive_score": row.get("comprehensive_score"),
        "created_at": row.get("created_at"),
        "title": row.get("title"),
        "student_id": row.get("student_id"),
        "student_name": row.get("name"),
    }
    if extra:
        payload.update(extra)
    return payload


@router.post("/activities/{activity_id}/checkin", status_code=201)
def checkin(
    activity_id: int,
    payload: CheckInRequest,
    user: dict[str, Any] = Depends(require_role("STUDENT")),
):
    activity = _activity_or_404(activity_id)
    if not _registered_member(activity_id, user["id"]):
        fail(403, "请先报名该活动后再签到")

    existing = db.query_one(
        "SELECT * FROM credentials WHERE activity_id = ? AND user_id = ?",
        (activity_id, user["id"]),
    )
    if existing:
        return ok({"check_in": _credential_dict(dict(existing)), "replayed": True})

    checked_in_at = now_iso()
    score = activity.get("comprehensive_score")
    credential_id = db.execute(
        "INSERT INTO credentials (activity_id, user_id, status, checkin_time, comprehensive_score) "
        "VALUES (?, ?, 'issued', ?, ?)",
        (activity_id, user["id"], checked_in_at, score),
    )
    row = db.query_one("SELECT * FROM credentials WHERE id = ?", (credential_id,))
    return ok(
        {
            "check_in": {
                "id": credential_id,
                "activity_id": activity_id,
                "user_id": user["id"],
                "channel": payload.channel,
                "status": "SUCCESS",
                "checkin_at": checked_in_at,
            },
            "credential": _credential_dict(dict(row), {"title": activity.get("title")}),
            "replayed": False,
        }
    )


@router.get("/activities/{activity_id}/checkin-status")
def checkin_status(
    activity_id: int,
    user: dict[str, Any] = Depends(require_role("STUDENT")),
):
    _activity_or_404(activity_id)
    registered = _registered_member(activity_id, user["id"])
    credential = db.query_one(
        "SELECT * FROM credentials WHERE activity_id = ? AND user_id = ?",
        (activity_id, user["id"]),
    )
    return ok(
        {
            "registered": bool(registered),
            "checked_in": credential is not None,
            "credential": _credential_dict(dict(credential)) if credential else None,
        }
    )


@router.get("/activities/{activity_id}/checkin-list")
def checkin_list(
    activity_id: int,
    user: dict[str, Any] = Depends(require_role("ORGANIZER")),
):
    activity = _activity_or_404(activity_id)
    _require_organizer(user, activity)
    rows = db.query_all(
        """
        SELECT c.*, u.student_id, u.name, a.title
        FROM credentials c
        JOIN users u ON u.id = c.user_id
        JOIN activities a ON a.id = c.activity_id
        WHERE c.activity_id = ?
        ORDER BY c.checkin_time DESC
        """,
        (activity_id,),
    )
    return ok({"items": [_credential_dict(dict(row)) for row in rows]})


@router.post("/activities/{activity_id}/confirm")
def confirm(
    activity_id: int,
    payload: ConfirmRequest,
    user: dict[str, Any] = Depends(require_role("ORGANIZER")),
):
    activity = _activity_or_404(activity_id)
    _require_organizer(user, activity)
    ids = payload.credential_ids
    if len(set(ids)) != len(ids):
        fail(400, "凭证 ID 不能重复")
    confirmed_at = now_iso()
    with db.transaction() as conn:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT * FROM credentials WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        if len(rows) != len(ids):
            fail(404, "凭证不存在")
        for row in rows:
            if int(row["activity_id"]) != activity_id:
                fail(409, "凭证不属于该活动")
            if row["status"] != "issued":
                fail(409, "只有已发放的凭证可以确认")
        for credential_id in ids:
            conn.execute(
                "UPDATE credentials SET status = 'confirmed', confirmed_at = ? WHERE id = ?",
                (confirmed_at, credential_id),
            )
    return ok(
        {
            "activity_id": activity_id,
            "credential_ids": ids,
            "status": "confirmed",
            "confirmed_at": confirmed_at,
            "note": payload.note,
        }
    )


@router.post("/credentials/{credential_id}/sign")
def sign_credential(
    credential_id: int,
    payload: SignRequest,
    user: dict[str, Any] = Depends(require_role("ORGANIZER")),
):
    row = db.query_one(
        """
        SELECT c.*, u.student_id, u.name, a.title, a.organizer_id
        FROM credentials c
        JOIN users u ON u.id = c.user_id
        JOIN activities a ON a.id = c.activity_id
        WHERE c.id = ?
        """,
        (credential_id,),
    )
    if row is None:
        fail(404, "凭证不存在")
    _require_organizer(user, dict(row))
    if row["status"] != "confirmed":
        fail(409, "只有已确认的凭证可以签章")

    pdf = pdf_template.render(
        {
            "credential_no": f"ET-{credential_id:06d}",
            "title": row["title"],
            "student_id": row["student_id"],
            "organizer_name": user["id"],
            "comprehensive_score": row["comprehensive_score"],
            "status": "signed",
        }
    )
    signed_pdf, digest = seal_service.seal(pdf, seal_id=payload.seal_id, signed_by=str(user["id"]))
    object_key = f"credentials/{credential_id}.pdf"
    file_storage.put(object_key, signed_pdf)
    signed_at = now_iso()
    db.execute(
        "UPDATE credentials SET status = 'signed', signed_at = ?, pdf_path = ? WHERE id = ?",
        (signed_at, object_key, credential_id),
    )
    updated = dict(row)
    updated.update({"status": "signed", "signed_at": signed_at, "pdf_path": object_key})
    return ok(
        {
            "credential": _credential_dict(updated),
            "signed_file": {
                "download_url": f"/api/credentials/{credential_id}/pdf",
                "sha256": digest,
            },
        }
    )


@router.get("/credentials")
def my_credentials(
    status: str | None = Query(default=None),
    user: dict[str, Any] = Depends(require_role("STUDENT")),
):
    params: list[Any] = [user["id"]]
    sql = """
        SELECT c.*, u.student_id, u.name, a.title
        FROM credentials c
        JOIN users u ON u.id = c.user_id
        JOIN activities a ON a.id = c.activity_id
        WHERE c.user_id = ?
    """
    if status:
        sql += " AND c.status = ?"
        params.append(status.lower())
    sql += " ORDER BY c.checkin_time DESC"
    rows = db.query_all(sql, tuple(params))
    return ok({"items": [_credential_dict(dict(row)) for row in rows]})


@router.get("/credentials/export")
def export_credentials(
    activity_id: int | None = Query(default=None),
    format: Literal["XLSX", "CSV"] = Query(default="XLSX"),
    user: dict[str, Any] = Depends(get_current_user),
):
    if activity_id is not None:
        activity = _activity_or_404(activity_id)
        _require_organizer(user, activity)
        rows = [
            dict(row)
            for row in db.query_all(
                """
                SELECT c.*, u.student_id, u.name, a.title
                FROM credentials c
                JOIN users u ON u.id = c.user_id
                JOIN activities a ON a.id = c.activity_id
                WHERE c.activity_id = ? AND c.status = 'signed'
                ORDER BY c.checkin_time
                """,
                (activity_id,),
            )
        ]
    else:
        if user["role"] != "STUDENT":
            fail(403, "学生只能导出本人凭证")
        rows = [
            dict(row)
            for row in db.query_all(
                """
                SELECT c.*, u.student_id, u.name, a.title
                FROM credentials c
                JOIN users u ON u.id = c.user_id
                JOIN activities a ON a.id = c.activity_id
                WHERE c.user_id = ? AND c.status = 'signed'
                ORDER BY c.checkin_time
                """,
                (user["id"],),
            )
        ]
    content = build_xlsx(rows) if format == "XLSX" else build_csv(rows)
    digest = hashlib.sha256(content).hexdigest()
    object_key = f"exports/{user['role'].lower()}-{user['id']}-{int(datetime.now().timestamp())}.{format.lower()}"
    file_storage.put(object_key, content)
    return ok(
        {
            "row_count": len(rows),
            "sha256": digest,
            "download_url": f"/api/storage/{object_key}",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
    )


@router.get("/credentials/{credential_id}/pdf")
def credential_pdf(credential_id: int, user: dict[str, Any] = Depends(get_current_user)):
    row = db.query_one("SELECT * FROM credentials WHERE id = ?", (credential_id,))
    if row is None:
        fail(404, "凭证不存在")
    if user["role"] == "STUDENT" and int(row["user_id"]) != int(user["id"]):
        fail(403, "只能下载自己的凭证")
    if user["role"] == "ORGANIZER":
        activity = _activity_or_404(int(row["activity_id"]))
        _require_organizer(user, activity)
    if row["status"] != "signed" or not row["pdf_path"]:
        fail(409, "只有已签章凭证可以下载")
    path = file_storage.root / row["pdf_path"]
    if not path.is_file():
        fail(404, "凭证文件不存在")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/storage/{object_key:path}")
def storage_file(object_key: str, _: dict[str, Any] = Depends(get_current_user)):
    path = file_storage.root / object_key
    if not path.is_file() or file_storage.root.resolve() not in path.resolve().parents:
        fail(404, "文件不存在")
    media_type = "application/pdf" if path.suffix == ".pdf" else "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)
