from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
import uuid


class Pod3FormalApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="pod3-api-test-")
        os.environ["POD3_DB_PATH"] = os.path.join(cls.temp_dir.name, "pod3.db")
        os.environ["POD3_STORAGE_ROOT"] = os.path.join(cls.temp_dir.name, "storage")
        os.environ["AUTH_SERVICE_URL"] = ""
        os.environ["ACTIVITY_SERVICE_URL"] = ""
        os.environ["USER_SERVICE_URL"] = ""
        import main

        cls.app = main.app
        cls.database = main.database
        connection = cls.database.connect()
        try:
            existing_tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        finally:
            connection.close()
        if existing_tables.intersection({"users", "activities"}):
            raise AssertionError("POD-3 schema must not create shared users/activities tables")
        with cls.database.transaction() as connection:
            # This table is owned and populated by POD-1 in the integrated
            # database. The POD-3 schema must not create it.
            connection.execute(
                """
                CREATE TABLE activities (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    organizer_id TEXT NOT NULL,
                    organizer_name TEXT,
                    comprehensive_score REAL,
                    status TEXT NOT NULL DEFAULT 'published'
                )
                """
            )

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
        return response_status, json.loads(response_body)

    def test_required_pod3_flow(self) -> None:
        user_id = str(uuid.uuid4())
        activity_id = str(uuid.uuid4())
        os.environ["POD3_TEST_TOKENS"] = json.dumps(
            {"organizer-token": {"sub": user_id, "roles": ["STUDENT", "ORGANIZER"]}}
        )
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO activities (id, title, organizer_id, organizer_name, comprehensive_score) VALUES (?, ?, ?, ?, ?)",
                (activity_id, "POD-3 联调活动", user_id, "POD-3 组织方", 2.0),
            )
        auth = {"Authorization": "Bearer organizer-token"}

        status, issued = self.request(
            "POST",
            f"/api/activities/{activity_id}/checkin",
            {"student_id": user_id, "channel": "QR", "title": "POD-3 联调活动"},
            {**auth, "Idempotency-Key": "formal-checkin-001"},
        )
        self.assertEqual(status, 201)
        credential_id = issued["credential"]["id"]

        status, checkins = self.request("GET", f"/api/activities/{activity_id}/checkin-list", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual(len(checkins["items"]), 1)

        status, _ = self.request("POST", f"/api/activities/{activity_id}/confirm", {"credential_ids": [credential_id]}, auth)
        self.assertEqual(status, 201)
        status, signed = self.request("POST", f"/api/credentials/{credential_id}/sign", {"seal_id": str(uuid.uuid4())}, auth)
        self.assertEqual(status, 200)
        self.assertEqual(signed["credential"]["status"], "SEALED")

        status, warehouse = self.request("GET", "/api/credentials", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual(warehouse["items"][0]["status"], "SEALED")
        status, pdf = self.request("GET", f"/api/credentials/{credential_id}/pdf", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual(len(pdf["sha256"]), 64)
        status, export = self.request("GET", "/api/credentials/export", headers=auth)
        self.assertEqual(status, 202)
        self.assertEqual(export["row_count"], 1)
        status, organizer_export = self.request("GET", f"/api/credentials/export?activity_id={activity_id}&format=XLSX", headers=auth)
        self.assertEqual(status, 202)
        self.assertEqual(organizer_export["export_type"], "ORGANIZER_BONUS_LIST")
        self.assertTrue(organizer_export["download"]["download_url"].endswith(".xlsx"))

    def test_simple_token_and_role_guards(self) -> None:
        user_id = str(uuid.uuid4())
        os.environ["POD3_TEST_TOKENS"] = json.dumps({"student-token": {"sub": user_id, "roles": ["STUDENT"]}})
        auth = {"Authorization": "Bearer student-token"}
        status, _ = self.request("GET", f"/api/activities/{uuid.uuid4()}/checkin-list", headers=auth)
        self.assertEqual(status, 403)
        status, _ = self.request("GET", "/api/credentials")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
