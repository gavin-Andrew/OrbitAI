"""事件页面协议与来源安全测试（不访问活动数据库）。"""

import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from orbitai.events.service import EventConflict


class EventRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.options = {key: [] for key in ("articles", "organizations", "people", "segments", "event_types", "sources")}
        self.event = {"id": "test-event", "title": "<script>alert(1)</script>", "summary": "摘要", "notes": "问题", "status": "candidate", "date_start": None, "date_end": None, "date_precision": "unknown", "event_type_id": "other", "revision": "rev", "documents": [{"id": "doc", "title": "来源", "url": "javascript:alert(1)", "content_text": "<img src=x onerror=alert(1)>", "published_at": None, "evidence_role": "official", "source_id": "src", "article_id": 1, "notes": "限摘要"}], "organizations": [], "segments": [], "people": [], "history": []}

    def test_list_and_timeline_pass_filters_without_writes(self):
        with patch("orbitai.web.routes.events.load_options", return_value=self.options), patch("orbitai.web.routes.events.list_events", return_value=[]) as listing:
            response = self.client.get("/timeline?organization_id=openai&segment_id=foundation")
            self.assertEqual(response.status_code, 200)
            listing.assert_called_once_with(status="confirmed", organization_id="openai", segment_id="foundation", person_id=None)
            self.assertIn("暂无事件", response.text)
            self.assertEqual(self.client.get("/events?status=invalid").status_code, 422)

    def test_new_and_edit_never_precheck_confirmation(self):
        with patch("orbitai.web.routes.events.load_options", return_value=self.options), patch("orbitai.web.routes.events.load_event", return_value={**self.event, "status": "confirmed", "confirmed_by_user": 1}):
            for url in ("/events/new", "/events/test-event/edit"):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('name="confirmed_by_user" value="yes">', response.text)

    def test_detail_escapes_materials_and_rejects_script_links(self):
        with patch("orbitai.web.routes.events.load_event", return_value=self.event):
            response = self.client.get("/events/test-event")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('<script>', response.text)
            self.assertNotIn('href="javascript:', response.text)
            self.assertIn('&lt;img', response.text)
            self.assertIn('不是已确认事实', response.text)
            self.assertIn('并非已验证的网页全文', response.text)

    def test_preview_does_not_save_and_retains_checked_ids(self):
        payload = {"id": "generated-id", "title": "新事件"}
        preview = {"payload": payload, "before": None, "after": payload, "preview_token": "token", "revision": ""}
        with patch("orbitai.web.routes.events.preview_event", return_value=preview) as preview_call, patch("orbitai.web.routes.events.save_event") as save:
            response = self.client.post("/events/preview", data={"title": "新事件", "article_ids": "1", "source_1": "openai", "role_1": "official", "confirmed_by_user": "yes"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(preview_call.call_args.args[0]["materials"][0]["source_id"], "openai")
            self.assertTrue(preview_call.call_args.args[0]["confirmed_by_user"])
            self.assertIn('/events/new', response.text)
            self.assertNotIn('/events/generated-id/edit', response.text)
            self.assertIn('新事件', response.text)
            save.assert_not_called()

    def test_save_conflict_and_invalid_payload(self):
        self.assertEqual(self.client.post("/events/save", data={"payload": "[]"}).status_code, 422)
        with patch("orbitai.web.routes.events.save_event", side_effect=EventConflict("版本已变化")):
            response = self.client.post("/events/save", data={"payload": "{}", "preview_token": "old"})
            self.assertEqual(response.status_code, 409)
            self.assertIn("版本已变化", response.text)

    def test_save_redirect_and_missing_event(self):
        with patch("orbitai.web.routes.events.save_event", return_value="new-event") as save:
            response = self.client.post("/events/save", data={"payload": json.dumps({"title": "测试"}), "preview_token": "token"}, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertTrue(response.headers["location"].endswith("/events/new-event"))
            save.assert_called_once_with({"title": "测试"}, "token")
        with patch("orbitai.web.routes.events.load_event", return_value=None):
            self.assertEqual(self.client.get("/events/missing").status_code, 404)

    def test_cross_site_forms_and_wrong_content_type_never_save(self):
        with patch("orbitai.web.routes.events.save_event") as save:
            for headers in ({"Origin": "https://evil.example"}, {"Referer": "https://evil.example/form"}, {"Sec-Fetch-Site": "cross-site"}):
                response = self.client.post("/events/save", data={"payload": "{}"}, headers=headers)
                self.assertEqual(response.status_code, 422)
            self.assertEqual(self.client.post("/events/save", json={"payload": {}}).status_code, 422)
            save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
