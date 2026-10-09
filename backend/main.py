"""Formal POD-3 credential service."""

from __future__ import annotations

import json
import hashlib
import os
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is installed from requirements.txt
    def load_dotenv(*_: Any, **__: Any) -> bool:
        return False

from auth import create_access_token, get_current_user, require_roles
from database import Database
from integrations import ActivityClient, UserClient
from storage import CredentialPdfTemplate, HttpSealService, LocalFileStorage, LocalSealService, build_csv, build_student_bundle, build_xlsx


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
if os.getenv("APP_ENV", "development").lower() == "production" and os.getenv("JWT_SECRET", "dev-only-change-me") == "dev-only-change-me":
    raise RuntimeError("JWT_SECRET must be configured in production")
DB_PATH = os.getenv("POD3_DB_PATH", str(BASE_DIR / "pod3.db"))
STORAGE_ROOT = os.getenv("POD3_STORAGE_ROOT", str(BASE_DIR / "storage"))
database = Database(DB_PATH, BASE_DIR / "pod3_schema.sql")
activity_client = ActivityClient(database)
user_client = UserClient(database)
file_storage = LocalFileStorage(STORAGE_ROOT)
pdf_template = CredentialPdfTemplate()
seal_service = HttpSealService(os.environ["SEAL_SERVICE_URL"]) if os.getenv("SEAL_SERVICE_URL") else LocalSealService()

app = FastAPI(title="POD-3 Credential Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers or {})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()},
    )


class CheckInRequest(BaseModel):
    student_id: str
    channel: Literal["QR", "MANUAL", "IMPORT"] = "QR"
    checked_in_at: datetime | None = None
    title: str = Field(..., min_length=1, max_length=200)
    organizer_name: str | None = Field(default=None, max_length=200)
    comprehensive_score: float | None = Field(default=None, ge=0)


class ConfirmRequest(BaseModel):
    credential_ids: list[str] = Field(..., min_length=1, max_length=1000)
    confirmed_by: str | None = None
    note: str | None = Field(default=None, max_length=1000)


class SignRequest(BaseModel):
    seal_id: str
    signed_by: str | None = None


class DevTokenRequest(BaseModel):
    subject: str
    roles: list[str] = Field(default_factory=lambda: ["STUDENT"])
    organization_ids: list[str] = Field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def future_iso(minutes: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fail(code: str, message: str, http_status: int, **details: Any) -> None:
    raise HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message, "request_id": str(uuid.uuid4()), "details": details},
    )


def auth_token(request: Request) -> str | None:
    value = request.headers.get("Authorization", "")
    return value[7:].strip() if value.startswith("Bearer ") else None


def is_admin(user: dict[str, Any]) -> bool:
    return "ADMIN" in {str(role).upper() for role in user.get("roles", [])}


def require_uuid(value: str, field: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        fail("VALIDATION_ERROR", f"{field} must be a UUID", 400, field=field)
    raise AssertionError("unreachable")


def ensure_local_user(user_id: str, claims: dict[str, Any], token: str | None) -> dict[str, Any]:
    existing = user_client.get(user_id, token)
    if existing:
        return existing
    if os.getenv("USER_SERVICE_URL"):
        fail("RESOURCE_NOT_FOUND", "User was not found in the user service", 404, user_id=user_id)
    roles = [str(role).upper() for role in claims.get("roles", ["STUDENT"])]
    organization_ids = claims.get("organization_ids", [])
    with database.transaction() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO users (id, student_id, name, roles, organization_ids) VALUES (?, ?, ?, ?, ?)",
            (user_id, user_id, user_id, json.dumps(roles), json.dumps(organization_ids)),
        )
    return {"id": user_id, "student_id": user_id, "name": user_id, "roles": roles, "organization_ids": organization_ids}


def ensure_local_activity(activity_id: str, payload: CheckInRequest, organizer_id: str, token: str | None) -> dict[str, Any]:
    activity = activity_client.get(activity_id, token)
    if activity:
        return activity
    if os.getenv("ACTIVITY_SERVICE_URL"):
        fail("RESOURCE_NOT_FOUND", "Activity was not found in the activity service", 404, activity_id=activity_id)
    with database.transaction() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO activities (id, title, organizer_id, organizer_name, comprehensive_score) VALUES (?, ?, ?, ?, ?)",
            (activity_id, payload.title, organizer_id, payload.organizer_name, payload.comprehensive_score),
        )
    return {"id": activity_id, "title": payload.title, "organizer_id": organizer_id, "organizer_name": payload.organizer_name, "comprehensive_score": payload.comprehensive_score}


def role_access(user: dict[str, Any], activity: dict[str, Any]) -> bool:
    return is_admin(user) or activity.get("organizer_id") == user.get("sub")


def credential_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"revoked_at", "revoke_reason", "version"}}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pod3-credential", "version": "1.0.0"}


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "backend ok", "service": "pod3-credential"}


@app.post("/api/auth/dev-token")
def dev_token(payload: DevTokenRequest) -> dict[str, str]:
    if os.getenv("APP_ENV", "development").lower() == "production":
        fail("NOT_FOUND", "Development token endpoint is disabled", 404)
    return {"access_token": create_access_token(payload.subject, payload.roles, payload.organization_ids), "token_type": "bearer"}


@app.post("/api/activities/{activity_id}/checkin", status_code=201)
def checkin(
    activity_id: str,
    payload: CheckInRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: dict[str, Any] = Depends(get_current_user),
) -> JSONResponse:
    activity_id = require_uuid(activity_id, "activity_id")
    student_id = require_uuid(payload.student_id, "student_id")
    if not idempotency_key or not 8 <= len(idempotency_key) <= 128:
        fail("VALIDATION_ERROR", "Idempotency-Key must contain 8 to 128 characters", 400)
    if not is_admin(user) and user["sub"] != student_id:
        fail("FORBIDDEN", "Students can only check in themselves", 403)
    token = auth_token(request)
    ensure_local_user(student_id, user, token)
    activity = ensure_local_activity(activity_id, payload, user["sub"], token)
    with closing(database.connect()) as connection:
        row = connection.execute(
            "SELECT cr.id AS checkin_id, cr.activity_id, cr.student_id, cr.status AS checkin_status, cr.channel, cr.checkin_at, c.* FROM checkin_records cr JOIN credentials c ON c.checkin_id = cr.id WHERE cr.idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if row:
            checkin_result = {"id": row["checkin_id"], "activity_id": row["activity_id"], "student_id": row["student_id"], "status": row["checkin_status"], "channel": row["channel"], "checkin_at": row["checkin_at"]}
            credential_result = {key: row[key] for key in ["id", "credential_no", "checkin_id", "activity_id", "student_id", "title", "organizer_name", "comprehensive_score", "status", "issued_at", "confirmed_at", "sealed_at", "pdf_object_key", "pdf_sha256"]}
            return JSONResponse(status_code=200, content={"check_in": checkin_result, "credential": credential_dict(credential_result)})
        duplicate = connection.execute(
            "SELECT id FROM checkin_records WHERE activity_id = ? AND student_id = ? AND status = 'SUCCESS'",
            (activity_id, student_id),
        ).fetchone()
    if duplicate:
        fail("DUPLICATE_CHECKIN", "The student already has a successful check-in for this activity", 409, checkin_id=duplicate["id"])

    checkin_id = str(uuid.uuid4())
    credential_id = str(uuid.uuid4())
    issued_at = now_iso()
    checked_in_at = payload.checked_in_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if payload.checked_in_at else issued_at
    credential_no = f"ET-{datetime.now(timezone.utc):%Y%m%d}-{credential_id[:8].upper()}"
    try:
        with database.transaction() as connection:
            connection.execute("INSERT INTO checkin_records (id, activity_id, student_id, channel, idempotency_key, checkin_at) VALUES (?, ?, ?, ?, ?, ?)", (checkin_id, activity_id, student_id, payload.channel, idempotency_key, checked_in_at))
            connection.execute("INSERT INTO credentials (id, credential_no, checkin_id, activity_id, student_id, title, organizer_name, comprehensive_score, issued_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (credential_id, credential_no, checkin_id, activity_id, student_id, payload.title, payload.organizer_name or activity.get("organizer_name"), payload.comprehensive_score if payload.comprehensive_score is not None else activity.get("comprehensive_score"), issued_at))
    except Exception as exc:
        fail("DATABASE_ERROR", "Unable to save check-in", 500, reason=str(exc))
    score = payload.comprehensive_score if payload.comprehensive_score is not None else activity.get("comprehensive_score")
    credential_result = {"id": credential_id, "credential_no": credential_no, "checkin_id": checkin_id, "activity_id": activity_id, "student_id": student_id, "title": payload.title, "organizer_name": payload.organizer_name or activity.get("organizer_name"), "comprehensive_score": score, "status": "ISSUED", "issued_at": issued_at, "confirmed_at": None, "sealed_at": None, "pdf_object_key": None, "pdf_sha256": None}
    return JSONResponse(status_code=201, content={"check_in": {"id": checkin_id, "activity_id": activity_id, "student_id": student_id, "status": "SUCCESS", "channel": payload.channel, "checkin_at": checked_in_at}, "credential": credential_result})


@app.get("/api/activities/{activity_id}/checkin-list")
def checkin_list(activity_id: str, user: dict[str, Any] = Depends(require_roles("ORGANIZER", "ADMIN"))) -> dict[str, Any]:
    activity_id = require_uuid(activity_id, "activity_id")
    activity = activity_client.get(activity_id)
    if not activity:
        fail("RESOURCE_NOT_FOUND", "Activity not found", 404, activity_id=activity_id)
    if not role_access(user, activity):
        fail("FORBIDDEN", "You are not the organizer of this activity", 403)
    with closing(database.connect()) as connection:
        rows = connection.execute("SELECT id, activity_id, student_id, status, channel, checkin_at FROM checkin_records WHERE activity_id = ? ORDER BY checkin_at DESC", (activity_id,)).fetchall()
    return {"items": [dict(row) for row in rows], "next_page_token": None}


@app.post("/api/activities/{activity_id}/confirm", status_code=201)
def confirm(activity_id: str, payload: ConfirmRequest, user: dict[str, Any] = Depends(require_roles("ORGANIZER", "ADMIN"))) -> dict[str, Any]:
    activity_id = require_uuid(activity_id, "activity_id")
    activity = activity_client.get(activity_id)
    if not activity:
        fail("RESOURCE_NOT_FOUND", "Activity not found", 404, activity_id=activity_id)
    if not role_access(user, activity):
        fail("FORBIDDEN", "You are not the organizer of this activity", 403)
    credential_ids = [require_uuid(value, "credential_id") for value in payload.credential_ids]
    if len(set(credential_ids)) != len(credential_ids):
        fail("VALIDATION_ERROR", "credential_ids must be unique", 400)
    confirmed_at = now_iso()
    batch_id = str(uuid.uuid4())
    batch_no = f"CB-{datetime.now(timezone.utc):%Y%m%d}-{batch_id[:8].upper()}"
    with database.transaction() as connection:
        placeholders = ",".join("?" for _ in credential_ids)
        rows = connection.execute(f"SELECT * FROM credentials WHERE id IN ({placeholders})", credential_ids).fetchall()
        if len(rows) != len(credential_ids):
            fail("RESOURCE_NOT_FOUND", "Credential not found", 404)
        for row in rows:
            if row["activity_id"] != activity_id:
                fail("CREDENTIAL_ACTIVITY_MISMATCH", "Credential belongs to another activity", 409, credential_id=row["id"])
            if row["status"] != "ISSUED":
                fail("INVALID_STATE_TRANSITION", "Only ISSUED credentials can be confirmed", 409, credential_id=row["id"], current_status=row["status"])
        connection.execute("INSERT INTO confirmation_batches (id, activity_id, batch_no, status, created_by, confirmed_by, confirmed_at, note) VALUES (?, ?, ?, 'CONFIRMED', ?, ?, ?, ?)", (batch_id, activity_id, batch_no, user["sub"], payload.confirmed_by or user["sub"], confirmed_at, payload.note))
        for credential_id in credential_ids:
            connection.execute("INSERT INTO confirmation_items (batch_id, credential_id) VALUES (?, ?)", (batch_id, credential_id))
            connection.execute("UPDATE credentials SET status = 'CONFIRMED', confirmed_at = ? WHERE id = ?", (confirmed_at, credential_id))
    return {"id": batch_id, "activity_id": activity_id, "batch_no": batch_no, "status": "CONFIRMED", "credential_ids": credential_ids, "confirmed_by": payload.confirmed_by or user["sub"], "confirmed_at": confirmed_at, "sealed_at": None, "created_at": confirmed_at}


@app.post("/api/credentials/{credential_id}/sign")
def sign_credential(credential_id: str, payload: SignRequest, user: dict[str, Any] = Depends(require_roles("ORGANIZER", "ADMIN"))) -> dict[str, Any]:
    credential_id = require_uuid(credential_id, "credential_id")
    with closing(database.connect()) as connection:
        row = database.row(connection.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,)).fetchone())
    if not row:
        fail("RESOURCE_NOT_FOUND", "Credential not found", 404)
    activity = activity_client.get(row["activity_id"])
    if not activity or not role_access(user, activity):
        fail("FORBIDDEN", "You are not allowed to sign this credential", 403)
    if row["status"] != "CONFIRMED":
        fail("INVALID_STATE_TRANSITION", "Only a CONFIRMED credential can be signed", 409, current_status=row["status"])
    signed_by = payload.signed_by or user["sub"]
    pdf = pdf_template.render({**row, "status": "SEALED"})
    signed_pdf, digest = seal_service.seal(pdf, seal_id=payload.seal_id, signed_by=signed_by)
    object_key = f"credentials/{credential_id}.pdf"
    file_storage.put(object_key, signed_pdf)
    sealed_at = now_iso()
    with database.transaction() as connection:
        connection.execute("UPDATE credentials SET status = 'SEALED', sealed_at = ?, pdf_object_key = ?, pdf_sha256 = ? WHERE id = ?", (sealed_at, object_key, digest, credential_id))
        connection.execute("INSERT INTO seal_records (id, credential_id, seal_id, signed_by, provider, signed_file_object_key, signed_file_sha256, signed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), credential_id, payload.seal_id, signed_by, seal_service.provider, object_key, digest, sealed_at))
    row.update({"status": "SEALED", "sealed_at": sealed_at, "pdf_object_key": object_key, "pdf_sha256": digest})
    return {"credential": credential_dict(row), "signed_file": {"download_url": file_storage.url(object_key), "expires_at": future_iso(), "sha256": digest}}


@app.get("/api/credentials")
def my_credentials(status_filter: str | None = Query(default=None, alias="status"), user: dict[str, Any] = Depends(require_roles("STUDENT", "ORGANIZER", "ADMIN"))) -> dict[str, Any]:
    with closing(database.connect()) as connection:
        if status_filter:
            rows = connection.execute("SELECT * FROM credentials WHERE student_id = ? AND status = ? ORDER BY issued_at DESC", (user["sub"], status_filter.upper())).fetchall()
        else:
            rows = connection.execute("SELECT * FROM credentials WHERE student_id = ? ORDER BY issued_at DESC", (user["sub"],)).fetchall()
    return {"items": [credential_dict(dict(row)) for row in rows], "next_page_token": None}


@app.get("/api/credentials/{credential_id}/pdf")
def credential_pdf(credential_id: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    credential_id = require_uuid(credential_id, "credential_id")
    with closing(database.connect()) as connection:
        row = database.row(connection.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,)).fetchone())
    if not row:
        fail("RESOURCE_NOT_FOUND", "Credential not found", 404)
    if row["student_id"] != user["sub"] and not is_admin(user):
        fail("FORBIDDEN", "You can only download your own credential", 403)
    if row["status"] != "SEALED" or not row["pdf_object_key"]:
        fail("INVALID_STATE_TRANSITION", "Only a SEALED credential can be downloaded", 409, current_status=row["status"])
    return {"download_url": file_storage.url(row["pdf_object_key"]), "expires_at": future_iso(), "sha256": row["pdf_sha256"]}


@app.get("/api/credentials/export", status_code=202)
def export_credentials(request: Request, activity_id: str | None = Query(default=None), format: Literal["XLSX", "CSV"] = Query(default="XLSX"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if activity_id:
        activity_id = require_uuid(activity_id, "activity_id")
        if not (is_admin(user) or "ORGANIZER" in {str(role).upper() for role in user.get("roles", [])}):
            fail("FORBIDDEN", "Only organizers can export an activity roster", 403)
        activity = activity_client.get(activity_id)
        if not activity or not role_access(user, activity):
            fail("FORBIDDEN", "You are not allowed to export this activity", 403)
        export_type = "ORGANIZER_BONUS_LIST"
        student_id = None
        requester_scope = activity_id
    else:
        export_type = "STUDENT_CREDENTIAL_BUNDLE"
        student_id = user["sub"]
        requester_scope = student_id
    key = idempotency_key or f"GET:{requester_scope}:{format}"
    with closing(database.connect()) as connection:
        existing = database.row(connection.execute("SELECT * FROM export_jobs WHERE requester_id = ? AND idempotency_key = ?", (user["sub"], key)).fetchone())
    if existing:
        return export_job_dict(existing)
    with closing(database.connect()) as connection:
        if activity_id:
            rows = [dict(row) for row in connection.execute("SELECT * FROM credentials WHERE activity_id = ? AND status = 'SEALED' ORDER BY issued_at", (activity_id,)).fetchall()]
        else:
            rows = [dict(row) for row in connection.execute("SELECT * FROM credentials WHERE student_id = ? AND status = 'SEALED' ORDER BY issued_at", (student_id,)).fetchall()]
    job_id = str(uuid.uuid4())
    if export_type == "STUDENT_CREDENTIAL_BUNDLE":
        content = build_student_bundle((f"{row['credential_no']}.pdf", file_storage.get(row["pdf_object_key"])) for row in rows)
        extension = "zip"
    else:
        content = build_xlsx(rows) if format == "XLSX" else build_csv(rows)
        extension = "xlsx" if format == "XLSX" else "csv"
    object_key = f"exports/{job_id}.{extension}"
    file_storage.put(object_key, content)
    digest = hashlib.sha256(content).hexdigest()
    created_at = now_iso()
    expires_at = future_iso(30)
    with database.transaction() as connection:
        connection.execute("INSERT INTO export_jobs (id, export_type, requester_id, student_id, activity_id, status, idempotency_key, file_object_key, file_sha256, row_count, expires_at, created_at) VALUES (?, ?, ?, ?, ?, 'SUCCEEDED', ?, ?, ?, ?, ?, ?)", (job_id, export_type, user["sub"], student_id, activity_id, key, object_key, digest, len(rows), expires_at, created_at))
    return {"id": job_id, "export_type": export_type, "requester_id": user["sub"], "student_id": student_id, "activity_id": activity_id, "status": "SUCCEEDED", "download": {"download_url": file_storage.url(object_key), "expires_at": expires_at, "sha256": digest}, "row_count": len(rows), "created_at": created_at, "error_code": None}


def export_job_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": row["id"], "export_type": row["export_type"], "requester_id": row["requester_id"], "student_id": row["student_id"], "activity_id": row["activity_id"], "status": row["status"], "download": {"download_url": file_storage.url(row["file_object_key"]), "expires_at": row["expires_at"], "sha256": row["file_sha256"]}, "row_count": row["row_count"], "created_at": row["created_at"], "error_code": row["error_code"]}


@app.get("/api/storage/{object_key:path}")
def storage_file(object_key: str, _: dict[str, Any] = Depends(get_current_user)) -> FileResponse:
    path = file_storage.root / object_key
    if not path.is_file() or file_storage.root.resolve() not in path.resolve().parents:
        fail("RESOURCE_NOT_FOUND", "Stored file not found", 404)
    media_type = "application/pdf" if path.suffix == ".pdf" else "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)
