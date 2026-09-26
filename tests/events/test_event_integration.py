"""真实 HTTP 表单到临时 SQLite 的闭环，不模拟事件服务，也不连接活动库。"""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from orbitai.core.database import init_db, get_connection
from orbitai.events.service import load_event
from orbitai.web.app import create_app


class EventIntegrationTests(unittest.TestCase):
    def test_browser_forms_complete_review_correction_and_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "integration.db"
            init_db(db)
            with closing(get_connection(db)) as conn, conn:
                conn.execute("INSERT INTO organizations(id,name) VALUES ('org','Test organization')")
                conn.execute("INSERT INTO segments(id,name,slug,segment_kind) VALUES ('seg','Test segment','test-segment','core_capability')")
                conn.execute("INSERT INTO articles(id,title,link,summary_original) VALUES (1,'Original announcement','https://example.org/announcement','Original RSS excerpt')")
            with patch("orbitai.events.service.DATABASE_FILE", db):
                client = TestClient(create_app())
                form = dict(title="Test candidate", summary="Supported by excerpt", event_type_id="model_release",
                            status="candidate", date_start="2026-07-01", date_precision="day", notes="Research question",
                            organization_ids="org", segment_ids="seg", article_ids="1", role_1="background",
                            change_reason="Initial candidate")

                def save_form():
                    response = client.post("/events/preview", data=form)
                    self.assertEqual(response.status_code, 200, response.text)
                    soup = BeautifulSoup(response.text, "html.parser")
                    payload = {key: soup.select_one(f'input[name="{key}"]')["value"]
                               for key in ("payload", "preview_token")}
                    response = client.post("/events/save", data=payload, follow_redirects=False)
                    self.assertEqual(response.status_code, 303, response.text)
                    return response.headers["location"].rsplit("/", 1)[1]

                eid = save_form()
                self.assertNotIn("Test candidate", client.get("/timeline").text)
                event = load_event(eid)
                self.assertIn("Original RSS excerpt", client.get(f"/events/{eid}").text)
                form.update(id=eid, expected_revision=event["revision"], status="confirmed",
                            confirmed_by_user="yes", change_reason="Simulated human review in temporary DB")
                save_form()
                self.assertIn("Test candidate", client.get("/timeline?organization_id=org").text)
                event = load_event(eid)
                form.update(expected_revision=event["revision"], title="Corrected candidate", change_reason="Correct transcription")
                save_form()
                event = load_event(eid)
                self.assertEqual(len(event["history"]), 3)
                self.assertIn("Test candidate", event["history"][0]["before_json"])
                self.assertIn("Corrected candidate", event["history"][0]["after_json"])
                form.update(expected_revision=event["revision"], status="archived", change_reason="Archive duplicate")
                form.pop("confirmed_by_user")
                save_form()
                self.assertNotIn("Corrected candidate", client.get("/timeline").text)
                self.assertIn("Corrected candidate", client.get("/events?status=archived").text)


if __name__ == "__main__":
    unittest.main()
