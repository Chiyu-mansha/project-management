"""Real HTTP/SQLite regression tests; only a temporary database is used.

Run from repo root: python -m unittest discover -s backend/tests -v
Install backend/requirements.txt and httpx first.
"""
from __future__ import annotations

import importlib
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db
import database
from fastapi.testclient import TestClient


class RegistrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        cls.old_db, cls.old_pod1_db = db.DB_PATH, database.DB_PATH
        db.DB_PATH = database.DB_PATH = Path(cls.temp.name) / "test.db"
        cls.app = importlib.import_module("main").app

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH, database.DB_PATH = cls.old_db, cls.old_pod1_db
        cls.temp.cleanup()

    def setUp(self):
        self.client = TestClient(self.app)
        with db.transaction() as conn:
            for table in ("credentials", "registration_members", "registrations", "forms", "activities", "organizers", "users"):
                conn.execute(f"DELETE FROM {table}")
            for uid in range(1, 5):
                conn.execute("INSERT INTO users(id,password_hash,name,student_id) VALUES (?, 'unused', ?, ?)",
                             (uid, f"学生{uid}", f"S{uid}"))
            conn.execute("INSERT INTO organizers(id,account,password_hash,name) VALUES(1,'O1','unused','发布者')")
            conn.execute("INSERT INTO activities(id,title,organizer_id,status,min_team_member,max_team_member) "
                         "VALUES(1,'测试活动',1,'published',1,4)")
        self.form = {
            "form_team_schema": [{"field_key": "project", "label": "项目", "type": "text", "required": True}],
            "form_member_schema": [
                {"field_key": "student_id", "label": "学号", "type": "text", "required": True},
                {"field_key": "name", "label": "姓名", "type": "text", "required": True},
            ],
        }
        self.assertEqual(self.client.post("/api/activities/1/forms", json=self.form, headers=self.auth("organizer", 1)).status_code, 200)

    def tearDown(self):
        self.client.close()

    @staticmethod
    def auth(role="student", uid=1):
        return {"Authorization": f"Bearer {role}:{uid}"}

    @staticmethod
    def payload(*users):
        return {"extra_fields": {"team_extra": {"project": "测试项目"}, "members": [
            {"role": "captain" if i == 0 else "member", "member_extra": {"student_id": f"S{uid}", "name": f"学生{uid}"}}
            for i, uid in enumerate(users)
        ]}}

    def register(self, *users):
        return self.client.post("/api/activities/1/registrations", json=self.payload(*users), headers=self.auth(uid=users[0]))

    def test_full_flow_covers_eight_routes_and_cascade(self):
        self.assertEqual(self.client.put("/api/activities/1/forms", json=self.form, headers=self.auth("organizer", 1)).status_code, 200)
        form = self.client.get("/api/activities/1/forms", headers=self.auth()).json()["data"]
        self.assertEqual(form["form_member_schema"], self.form["form_member_schema"])
        created = self.register(1, 2)
        self.assertEqual(created.status_code, 200, created.text)
        reg_id = created.json()["data"]["registration_id"]
        listing = self.client.get("/api/activities/1/registrations", headers=self.auth("organizer", 1)).json()["data"]
        self.assertEqual(listing["total"], 1)
        mine = self.client.get("/api/users/2/registrations", headers=self.auth(uid=2)).json()["data"]
        self.assertEqual(mine["items"][0]["my_role"], "member")
        detail = self.client.get(f"/api/registrations/{reg_id}", headers=self.auth(uid=2)).json()["data"]
        self.assertEqual(detail["extra_fields"], self.payload(1, 2)["extra_fields"])
        self.assertEqual(self.client.put("/api/activities/1/forms", json=self.form, headers=self.auth("organizer", 1)).status_code, 400)
        self.assertEqual(self.client.delete(f"/api/registrations/{reg_id}", headers=self.auth(uid=2)).status_code, 403)
        deleted = self.client.delete(f"/api/registrations/{reg_id}", headers=self.auth())
        self.assertEqual(deleted.json(), {"code": 0, "data": None})
        self.assertEqual(db.query_one("SELECT COUNT(*) AS n FROM registration_members")["n"], 0)

    def test_member_credential_blocks_cancellation(self):
        reg_id = self.register(1, 2).json()["data"]["registration_id"]
        for status, checkin in (("issued", None), ("confirmed", None), ("signed", None), ("pending", "2026-10-17T10:00:00")):
            with self.subTest(status=status, checkin=checkin):
                db.execute("INSERT INTO credentials(activity_id,user_id,status,checkin_time) VALUES(1,2,?,?)", (status, checkin))
                response = self.client.delete(f"/api/registrations/{reg_id}", headers=self.auth())
                self.assertEqual(response.status_code, 409)
                self.assertIn("线下处理", response.json()["message"])
                self.assertEqual(db.query_one("SELECT COUNT(*) AS n FROM registration_members")["n"], 2)
                db.execute("DELETE FROM credentials")

    def test_cancelled_activity_preserves_history_and_rejects_new_signup(self):
        self.register(1, 2)
        db.execute("UPDATE activities SET status='cancelled' WHERE id=1")
        self.assertEqual(self.register(3).status_code, 400)
        listing = self.client.get("/api/users/2/registrations", headers=self.auth(uid=2)).json()["data"]
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["items"][0]["activity_status"], "cancelled")

    def test_timezone_and_fractional_deadlines(self):
        for deadline in ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "2000-01-01T00:00:00.123Z", "not-a-date"):
            with self.subTest(deadline=deadline):
                db.execute("UPDATE activities SET signup_deadline=? WHERE id=1", (deadline,))
                self.assertEqual(self.register(1).status_code, 400)
        db.execute("UPDATE activities SET signup_deadline=? WHERE id=1", ((datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),))
        self.assertEqual(self.register(1).status_code, 200)

    def test_invalid_pagination_has_existing_error_envelope(self):
        for path, headers in (("/api/users/1/registrations", self.auth()), ("/api/activities/1/registrations", self.auth("organizer", 1))):
            for query in ("page=0", "page=-1", "page_size=0", "page_size=101", "page_size=-1"):
                with self.subTest(path=path, query=query):
                    response = self.client.get(f"{path}?{query}", headers=headers)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json(), {"code": 400, "message": "参数错误"})

    def test_answers_are_text_and_fixed_labels_cannot_break_frontend(self):
        body = self.payload(1)
        body["extra_fields"]["team_extra"]["project"] = {"not": "text"}
        self.assertEqual(self.client.post("/api/activities/1/registrations", json=body, headers=self.auth()).status_code, 400)
        self.form["form_member_schema"][0]["label"] = "邮箱"
        response = self.client.put("/api/activities/1/forms", json=self.form, headers=self.auth("organizer", 1))
        self.assertEqual(response.status_code, 400)

    def test_capacity_is_teams_and_is_atomic_under_concurrent_signup(self):
        db.execute("UPDATE activities SET max_participants=1 WHERE id=1")
        gate = threading.Barrier(2)

        def signup(users):
            gate.wait(timeout=5)
            return self.register(*users).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(signup, [(1, 2), (3, 4)]))
        self.assertEqual(sorted(statuses), [200, 400])
        self.assertEqual(db.query_one("SELECT COUNT(*) AS n FROM registrations")["n"], 1)
        self.assertEqual(db.query_one("SELECT COUNT(*) AS n FROM registration_members")["n"], 2)

    def test_duplicate_member_and_other_user_access_are_rejected(self):
        self.register(1, 2)
        self.assertEqual(self.register(3, 2).status_code, 409)
        self.assertEqual(db.query_one("SELECT COUNT(*) AS n FROM registrations")["n"], 1)
        self.assertEqual(self.client.get("/api/users/1/registrations", headers=self.auth(uid=3)).status_code, 403)


if __name__ == "__main__":
    unittest.main()
