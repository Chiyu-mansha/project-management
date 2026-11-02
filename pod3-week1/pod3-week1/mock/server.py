#!/usr/bin/env python3
"""Dependency-free mock server for the POD-3 API contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def future_time(minutes: int = 15) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(minutes=minutes)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return str(uuid.uuid4())


class CredentialHandler(BaseHTTPRequestHandler):
    """In-memory API that follows api/pod3-openapi.yaml for parallel development."""

    checkins: dict[str, dict[str, Any]] = {}
    credentials: dict[str, dict[str, Any]] = {}
    batches: dict[str, dict[str, Any]] = {}
    exports: dict[str, dict[str, Any]] = {}
    idempotent_results: dict[str, tuple[int, dict[str, Any]]] = {}

    server_version = "Pod3Mock/1.0"

    @classmethod
    def reset_state(cls) -> None:
        cls.checkins = {}
        cls.credentials = {}
        cls.batches = {}
        cls.exports = {}
        cls.idempotent_results = {}

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, code: str, message: str, **details: Any) -> None:
        self._send(
            status,
            {
                "code": code,
                "message": message,
                "request_id": self.headers.get("X-Request-Id", new_id()),
                "details": details,
            },
        )

    def _json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("body must be a JSON object")
            return value
        except (ValueError, json.JSONDecodeError) as exc:
            self._error(400, "VALIDATION_ERROR", f"Invalid JSON body: {exc}")
            return None

    def _idempotency_key(self) -> str | None:
        key = self.headers.get("Idempotency-Key", "").strip()
        if len(key) < 8 or len(key) > 128:
            self._error(
                400,
                "VALIDATION_ERROR",
                "Idempotency-Key must contain 8 to 128 characters",
            )
            return None
        return key

    def _validate_uuid(self, value: Any, field: str) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except (ValueError, TypeError, AttributeError):
            self._error(400, "VALIDATION_ERROR", f"{field} must be a UUID", field=field)
            return False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._send(200, {"status": "ok", "service": "pod3-credential-mock", "version": "1.0.0"})
            return

        match = re.fullmatch(r"/api/v1/students/([^/]+)/credentials", path)
        if match:
            self._list_credentials(match.group(1), parse_qs(parsed.query))
            return

        match = re.fullmatch(r"/api/v1/credentials/([^/]+)/pdf", path)
        if match:
            self._credential_pdf(match.group(1))
            return

        match = re.fullmatch(r"/api/v1/credentials/([^/]+)", path)
        if match:
            credential = type(self).credentials.get(match.group(1))
            if credential is None:
                self._error(404, "RESOURCE_NOT_FOUND", "Credential not found")
                return
            self._send(200, credential)
            return

        match = re.fullmatch(r"/api/v1/export-jobs/([^/]+)", path)
        if match:
            job = type(self).exports.get(match.group(1))
            if job is None:
                self._error(404, "RESOURCE_NOT_FOUND", "Export job not found")
                return
            self._send(200, job)
            return

        self._error(404, "RESOURCE_NOT_FOUND", "Route not found", path=path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        match = re.fullmatch(r"/api/v1/activities/([^/]+)/check-ins", path)
        if match:
            self._create_checkin(match.group(1))
            return

        match = re.fullmatch(r"/api/v1/activities/([^/]+)/confirmation-batches", path)
        if match:
            self._create_confirmation_batch(match.group(1))
            return

        match = re.fullmatch(r"/api/v1/confirmation-batches/([^/]+)/seal", path)
        if match:
            self._seal_batch(match.group(1))
            return

        match = re.fullmatch(r"/api/v1/students/([^/]+)/exports", path)
        if match:
            self._create_export("STUDENT_CREDENTIAL_BUNDLE", student_id=match.group(1))
            return

        match = re.fullmatch(r"/api/v1/activities/([^/]+)/bonus-list-exports", path)
        if match:
            self._create_export("ORGANIZER_BONUS_LIST", activity_id=match.group(1))
            return

        self._error(404, "RESOURCE_NOT_FOUND", "Route not found", path=path)

    def _create_checkin(self, activity_id: str) -> None:
        if not self._validate_uuid(activity_id, "activity_id"):
            return
        key = self._idempotency_key()
        if key is None:
            return
        replay_key = f"checkin:{key}"
        if replay_key in type(self).idempotent_results:
            _, payload = type(self).idempotent_results[replay_key]
            self._send(200, payload)
            return

        body = self._json_body()
        if body is None:
            return
        required = ["student_id", "channel", "title"]
        missing = [field for field in required if not body.get(field)]
        if missing:
            self._error(400, "VALIDATION_ERROR", "Missing required fields", fields=missing)
            return
        if not self._validate_uuid(body["student_id"], "student_id"):
            return
        if body["channel"] not in {"QR", "MANUAL", "IMPORT"}:
            self._error(400, "VALIDATION_ERROR", "Unsupported check-in channel")
            return

        for existing in type(self).checkins.values():
            if (
                existing["activity_id"] == activity_id
                and existing["student_id"] == body["student_id"]
                and existing["status"] == "SUCCESS"
            ):
                self._error(
                    409,
                    "DUPLICATE_CHECKIN",
                    "The student already has a successful check-in for this activity",
                    checkin_id=existing["id"],
                )
                return

        timestamp = body.get("checked_in_at") or utc_now()
        checkin_id = new_id()
        credential_id = new_id()
        checkin = {
            "id": checkin_id,
            "activity_id": activity_id,
            "student_id": body["student_id"],
            "status": "SUCCESS",
            "channel": body["channel"],
            "checkin_at": timestamp,
        }
        credential = {
            "id": credential_id,
            "credential_no": f"ET-{datetime.now(timezone.utc):%Y%m%d}-{credential_id[:8].upper()}",
            "checkin_id": checkin_id,
            "activity_id": activity_id,
            "student_id": body["student_id"],
            "title": str(body["title"])[:200],
            "organizer_name": body.get("organizer_name"),
            "comprehensive_score": body.get("comprehensive_score"),
            "status": "ISSUED",
            "issued_at": utc_now(),
            "confirmed_at": None,
            "sealed_at": None,
            "pdf_sha256": None,
        }
        type(self).checkins[checkin_id] = checkin
        type(self).credentials[credential_id] = credential
        payload = {"check_in": checkin, "credential": credential}
        type(self).idempotent_results[replay_key] = (201, payload)
        self._send(201, payload)

    def _create_confirmation_batch(self, activity_id: str) -> None:
        body = self._json_body()
        if body is None:
            return
        credential_ids = body.get("credential_ids")
        confirmed_by = body.get("confirmed_by")
        if not isinstance(credential_ids, list) or not credential_ids or not confirmed_by:
            self._error(
                400,
                "VALIDATION_ERROR",
                "credential_ids and confirmed_by are required",
            )
            return
        if len(set(credential_ids)) != len(credential_ids):
            self._error(400, "VALIDATION_ERROR", "credential_ids must be unique")
            return

        selected: list[dict[str, Any]] = []
        for credential_id in credential_ids:
            credential = type(self).credentials.get(str(credential_id))
            if credential is None:
                self._error(404, "RESOURCE_NOT_FOUND", "Credential not found", credential_id=credential_id)
                return
            if credential["activity_id"] != activity_id:
                self._error(
                    409,
                    "CREDENTIAL_ACTIVITY_MISMATCH",
                    "All credentials must belong to the target activity",
                    credential_id=credential_id,
                )
                return
            if credential["status"] != "ISSUED":
                self._error(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Only ISSUED credentials can be confirmed",
                    credential_id=credential_id,
                    current_status=credential["status"],
                )
                return
            selected.append(credential)

        batch_id = new_id()
        confirmed_at = utc_now()
        for credential in selected:
            credential["status"] = "CONFIRMED"
            credential["confirmed_at"] = confirmed_at
        batch = {
            "id": batch_id,
            "activity_id": activity_id,
            "batch_no": f"CB-{datetime.now(timezone.utc):%Y%m%d}-{batch_id[:8].upper()}",
            "status": "CONFIRMED",
            "credential_ids": credential_ids,
            "confirmed_by": confirmed_by,
            "confirmed_at": confirmed_at,
            "sealed_at": None,
            "created_at": confirmed_at,
        }
        type(self).batches[batch_id] = batch
        self._send(201, batch)

    def _seal_batch(self, batch_id: str) -> None:
        batch = type(self).batches.get(batch_id)
        if batch is None:
            self._error(404, "RESOURCE_NOT_FOUND", "Confirmation batch not found")
            return
        if batch["status"] != "CONFIRMED":
            self._error(
                409,
                "INVALID_STATE_TRANSITION",
                "Only a CONFIRMED batch can be sealed",
                current_status=batch["status"],
            )
            return
        body = self._json_body()
        if body is None:
            return
        if not body.get("seal_id") or not body.get("signed_by"):
            self._error(400, "VALIDATION_ERROR", "seal_id and signed_by are required")
            return

        sealed_at = utc_now()
        digest = hashlib.sha256(f"pod3:{batch_id}:{sealed_at}".encode()).hexdigest()
        batch["status"] = "SEALED"
        batch["sealed_at"] = sealed_at
        credentials: list[dict[str, Any]] = []
        for credential_id in batch["credential_ids"]:
            credential = type(self).credentials[credential_id]
            credential["status"] = "SEALED"
            credential["sealed_at"] = sealed_at
            credential["pdf_sha256"] = digest
            credentials.append(credential)
        download = {
            "download_url": f"https://files.example.invalid/pod3/batches/{batch_id}.pdf",
            "expires_at": future_time(),
            "sha256": digest,
        }
        self._send(200, {"batch": batch, "credentials": credentials, "signed_file": download})

    def _list_credentials(self, student_id: str, query: dict[str, list[str]]) -> None:
        status = query.get("status", [None])[0]
        items = [
            credential
            for credential in type(self).credentials.values()
            if credential["student_id"] == student_id
            and (status is None or credential["status"] == status)
        ]
        items.sort(key=lambda value: value["issued_at"], reverse=True)
        self._send(200, {"items": items, "next_page_token": None})

    def _credential_pdf(self, credential_id: str) -> None:
        credential = type(self).credentials.get(credential_id)
        if credential is None:
            self._error(404, "RESOURCE_NOT_FOUND", "Credential not found")
            return
        if credential["status"] != "SEALED":
            self._error(
                409,
                "INVALID_STATE_TRANSITION",
                "Only a SEALED credential can be downloaded",
                current_status=credential["status"],
            )
            return
        self._send(
            200,
            {
                "download_url": f"https://files.example.invalid/pod3/credentials/{credential_id}.pdf",
                "expires_at": future_time(),
                "sha256": credential["pdf_sha256"],
            },
        )

    def _create_export(
        self,
        export_type: str,
        *,
        student_id: str | None = None,
        activity_id: str | None = None,
    ) -> None:
        key = self._idempotency_key()
        if key is None:
            return
        body = self._json_body()
        if body is None:
            return
        requester_id = self.headers.get("X-Demo-User-Id") or student_id or new_id()
        replay_key = f"export:{requester_id}:{key}"
        if replay_key in type(self).idempotent_results:
            _, payload = type(self).idempotent_results[replay_key]
            self._send(202, payload)
            return

        if export_type == "STUDENT_CREDENTIAL_BUNDLE":
            row_count = sum(
                1
                for item in type(self).credentials.values()
                if item["student_id"] == student_id and item["status"] == "SEALED"
            )
            extension = "zip"
        else:
            row_count = sum(
                1
                for item in type(self).credentials.values()
                if item["activity_id"] == activity_id and item["status"] == "SEALED"
            )
            extension = str(body.get("format", "XLSX")).lower()

        job_id = new_id()
        digest = hashlib.sha256(f"pod3-export:{job_id}".encode()).hexdigest()
        job = {
            "id": job_id,
            "export_type": export_type,
            "requester_id": requester_id,
            "student_id": student_id,
            "activity_id": activity_id,
            "status": "SUCCEEDED",
            "download": {
                "download_url": f"https://files.example.invalid/pod3/exports/{job_id}.{extension}",
                "expires_at": future_time(30),
                "sha256": digest,
            },
            "row_count": row_count,
            "created_at": utc_now(),
            "error_code": None,
        }
        type(self).exports[job_id] = job
        type(self).idempotent_results[replay_key] = (202, job)
        self._send(202, job)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the POD-3 credential mock API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), CredentialHandler)
    print(f"POD-3 mock API listening on http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

