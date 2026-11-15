from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class Pod3MainIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="pod3-main-")
        db_path = Path(cls.temp_dir.name) / "campus.db"
        os.environ["POD3_STORAGE_ROOT"] = str(Path(cls.temp_dir.name) / "storage")
        import db

        db.DB_PATH = db_path
        db.init_db()
        import credentials

        credentials.init_pod3_tables()
        import main

        cls.app = main.app
        cls.db = db
        cls.credentials = credentials

        org_id = db.execute(
            "INSERT INTO organizers (account, password_hash, name) VALUES (?, ?, ?)",
            ("org-001", "hash", "发布者甲"),
        )
        student_id = db.execute(
            "INSERT INTO users (password_hash, name, student_id) VALUES (?, ?, ?)",
            ("hash", "学生甲", "20230001"),
        )
        outsider_id = db.execute(
            "INSERT INTO users (password_hash, name, student_id) VALUES (?, ?, ?)",
            ("hash", "学生乙", "20230002"),
        )
        activity_id = db.execute(
            "INSERT INTO activities (title, organizer_id, status, min_team_member, max_team_member, comprehensive_score) "
            "VALUES (?, ?, 'published', 1, 1, 1)",
            ("第5周联调活动", org_id),
        )
        form_id = db.execute(
            "INSERT INTO forms (activity_id, organizer_id, form_team_schema, form_member_schema) VALUES (?, ?, '[]', '[]')",
            (activity_id, org_id),
        )
        extra = json.dumps(
            {
                "team_extra": {},
                "members": [{"role": "captain", "member_extra": {"student_id": "20230001"}}],
            },
            ensure_ascii=False,
        )
        reg_id = db.execute(
            "INSERT INTO registrations (activity_id, user_id, form_id, extra_fields) VALUES (?, ?, ?, ?)",
            (activity_id, student_id, form_id, extra),
        )
        db.execute(
            "INSERT INTO registration_members (registration_id, user_id, role, activity_id) VALUES (?, ?, 'captain', ?)",
            (reg_id, student_id, activity_id),
        )
        cls.org_id = org_id
        cls.student_id = student_id
        cls.outsider_id = outsider_id
        cls.activity_id = activity_id
        cls.student_auth = {"Authorization": f"Bearer student:{student_id}"}
        cls.outsider_auth = {"Authorization": f"Bearer student:{outsider_id}"}
        cls.org_auth = {"Authorization": f"Bearer organizer:{org_id}"}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    @classmethod
    def request(cls, method: str, path: str, payload: dict | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict]:
        return asyncio.run(cls._request(method, path, payload, headers))

    @classmethod
    async def _request(cls, method: str, path: str, payload: dict | None, headers: dict[str, str] | None) -> tuple[int, dict]:
        body = b"" if payload is None else json.dumps(payload).encode()
        raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
        if payload is not None:
            raw_headers.append((b"content-type", b"application/json"))
        messages = [{"type": "http.request", "body": body, "more_body": False}]
        sent: list[dict] = []

        async def receive() -> dict:
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            sent.append(message)

        await cls.app(
            {
                "type": "http",
                "method": method,
                "path": path.split("?", 1)[0],
                "query_string": path.split("?", 1)[1].encode() if "?" in path else b"",
                "headers": raw_headers,
                "scheme": "http",
                "server": ("test", 80),
                "client": ("test", 1),
                "http_version": "1.1",
            },
            receive,
            send,
        )
        response_status = next(message["status"] for message in sent if message["type"] == "http.response.start")
        response_body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        return response_status, json.loads(response_body or b"{}")

    def test_shared_auth_and_registration_gate(self) -> None:
        status, body = self.request("GET", "/api/credentials")
        self.assertEqual(status, 401)

        status, body = self.request(
            "POST",
            f"/api/activities/{self.activity_id}/checkin",
            {"channel": "QR"},
            self.outsider_auth,
        )
        self.assertEqual(status, 403)
        self.assertIn("报名", body.get("message", ""))

        status, issued = self.request(
            "POST",
            f"/api/activities/{self.activity_id}/checkin",
            {"channel": "QR"},
            self.student_auth,
        )
        self.assertEqual(status, 201)
        self.assertEqual(issued["code"], 0)
        credential_id = issued["data"]["credential"]["id"]

        status, replay = self.request(
            "POST",
            f"/api/activities/{self.activity_id}/checkin",
            {"channel": "QR"},
            self.student_auth,
        )
        self.assertEqual(status, 201)
        self.assertTrue(replay["data"]["replayed"])

        status, denied = self.request(
            "GET",
            f"/api/activities/{self.activity_id}/checkin-list",
            headers=self.student_auth,
        )
        self.assertEqual(status, 403)

        status, listing = self.request(
            "GET",
            f"/api/activities/{self.activity_id}/checkin-list",
            headers=self.org_auth,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(listing["data"]["items"]), 1)

        status, confirmed = self.request(
            "POST",
            f"/api/activities/{self.activity_id}/confirm",
            {"credential_ids": [credential_id]},
            self.org_auth,
        )
        self.assertEqual(status, 200)
        self.assertEqual(confirmed["data"]["status"], "confirmed")

        status, signed = self.request(
            "POST",
            f"/api/credentials/{credential_id}/sign",
            {"seal_id": "week5"},
            self.org_auth,
        )
        self.assertEqual(status, 200)
        self.assertEqual(signed["data"]["credential"]["status"], "signed")

        status, warehouse = self.request("GET", "/api/credentials", headers=self.student_auth)
        self.assertEqual(status, 200)
        self.assertEqual(warehouse["data"]["items"][0]["status"], "signed")


if __name__ == "__main__":
    unittest.main()
