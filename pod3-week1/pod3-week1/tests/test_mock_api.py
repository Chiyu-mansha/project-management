from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from mock.server import CredentialHandler  # noqa: E402


class Pod3MockApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        CredentialHandler.reset_state()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), CredentialHandler)
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            status = error.code
            payload = json.loads(error.read().decode("utf-8"))
            error.close()
            return status, payload

    def issue_credential(self) -> tuple[str, str, str]:
        activity_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        status, payload = self.request(
            "POST",
            f"/api/v1/activities/{activity_id}/check-ins",
            {
                "student_id": student_id,
                "channel": "QR",
                "title": "软件项目管理实践活动",
                "organizer_name": "课程组",
                "comprehensive_score": 1.0,
            },
            {"Idempotency-Key": f"checkin-{uuid.uuid4()}"},
        )
        self.assertEqual(status, 201)
        return activity_id, student_id, payload["credential"]["id"]

    def test_01_health(self) -> None:
        status, payload = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")

    def test_02_checkin_is_idempotent_and_issues_ticket(self) -> None:
        activity_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        key = f"checkin-{uuid.uuid4()}"
        body = {
            "student_id": student_id,
            "channel": "QR",
            "title": "校园活动",
        }
        first_status, first = self.request(
            "POST",
            f"/api/v1/activities/{activity_id}/check-ins",
            body,
            {"Idempotency-Key": key},
        )
        replay_status, replay = self.request(
            "POST",
            f"/api/v1/activities/{activity_id}/check-ins",
            body,
            {"Idempotency-Key": key},
        )

        self.assertEqual(first_status, 201)
        self.assertEqual(replay_status, 200)
        self.assertEqual(first["check_in"]["id"], replay["check_in"]["id"])
        self.assertEqual(first["credential"]["id"], replay["credential"]["id"])
        self.assertEqual(first["credential"]["status"], "ISSUED")

        list_status, warehouse = self.request(
            "GET", f"/api/v1/students/{student_id}/credentials"
        )
        self.assertEqual(list_status, 200)
        self.assertEqual(len(warehouse["items"]), 1)

    def test_03_confirmation_seal_and_pdf_download(self) -> None:
        activity_id, student_id, credential_id = self.issue_credential()
        organizer_id = str(uuid.uuid4())
        batch_status, batch = self.request(
            "POST",
            f"/api/v1/activities/{activity_id}/confirmation-batches",
            {"credential_ids": [credential_id], "confirmed_by": organizer_id},
        )
        self.assertEqual(batch_status, 201)
        self.assertEqual(batch["status"], "CONFIRMED")

        seal_status, sealed = self.request(
            "POST",
            f"/api/v1/confirmation-batches/{batch['id']}/seal",
            {"seal_id": str(uuid.uuid4()), "signed_by": organizer_id},
        )
        self.assertEqual(seal_status, 200)
        self.assertEqual(sealed["batch"]["status"], "SEALED")
        self.assertEqual(sealed["credentials"][0]["status"], "SEALED")

        pdf_status, download = self.request(
            "GET", f"/api/v1/credentials/{credential_id}/pdf"
        )
        self.assertEqual(pdf_status, 200)
        self.assertEqual(len(download["sha256"]), 64)

        warehouse_status, warehouse = self.request(
            "GET", f"/api/v1/students/{student_id}/credentials?status=SEALED"
        )
        self.assertEqual(warehouse_status, 200)
        self.assertEqual([credential_id], [item["id"] for item in warehouse["items"]])

    def test_04_student_and_organizer_exports(self) -> None:
        activity_id, student_id, credential_id = self.issue_credential()
        organizer_id = str(uuid.uuid4())
        _, batch = self.request(
            "POST",
            f"/api/v1/activities/{activity_id}/confirmation-batches",
            {"credential_ids": [credential_id], "confirmed_by": organizer_id},
        )
        self.request(
            "POST",
            f"/api/v1/confirmation-batches/{batch['id']}/seal",
            {"seal_id": str(uuid.uuid4()), "signed_by": organizer_id},
        )

        student_status, student_job = self.request(
            "POST",
            f"/api/v1/students/{student_id}/exports",
            {},
            {"Idempotency-Key": f"student-export-{uuid.uuid4()}"},
        )
        self.assertEqual(student_status, 202)
        self.assertEqual(student_job["status"], "SUCCEEDED")
        self.assertEqual(student_job["row_count"], 1)

        organizer_status, organizer_job = self.request(
            "POST",
            f"/api/v1/activities/{activity_id}/bonus-list-exports",
            {"format": "XLSX"},
            {
                "Idempotency-Key": f"organizer-export-{uuid.uuid4()}",
                "X-Demo-User-Id": organizer_id,
            },
        )
        self.assertEqual(organizer_status, 202)
        self.assertEqual(organizer_job["row_count"], 1)

        get_status, stored_job = self.request(
            "GET", f"/api/v1/export-jobs/{organizer_job['id']}"
        )
        self.assertEqual(get_status, 200)
        self.assertEqual(stored_job["id"], organizer_job["id"])

    def test_05_duplicate_checkin_with_new_key_is_rejected(self) -> None:
        activity_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        path = f"/api/v1/activities/{activity_id}/check-ins"
        body = {"student_id": student_id, "channel": "QR", "title": "校园活动"}
        first_status, _ = self.request(
            "POST", path, body, {"Idempotency-Key": f"first-{uuid.uuid4()}"}
        )
        duplicate_status, duplicate = self.request(
            "POST", path, body, {"Idempotency-Key": f"second-{uuid.uuid4()}"}
        )
        self.assertEqual(first_status, 201)
        self.assertEqual(duplicate_status, 409)
        self.assertEqual(duplicate["code"], "DUPLICATE_CHECKIN")


if __name__ == "__main__":
    unittest.main()
