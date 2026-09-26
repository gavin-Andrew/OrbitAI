"""Real HTTP/template V4.2 workflows, isolated from the active database/network."""

import json
import unittest
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from fastapi.testclient import TestClient

from orbitai.events.service import load_event
from orbitai.materials.intake import _fetch_signature
from tests.events import test_event_service as fixtures


class HiddenFields(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("type") == "hidden" and attrs.get("name"):
            self.values[attrs["name"]] = attrs.get("value", "")


class WorkflowIntegrationTests(unittest.TestCase):
    connection = fixtures.EventServiceTests.connection
    payload = fixtures.EventServiceTests.payload
    save = fixtures.EventServiceTests.save
    snapshot = fixtures.EventServiceTests.snapshot
    count = fixtures.EventServiceTests.count

    def setUp(self):
        fixtures.EventServiceTests.setUp(self)
        for target in ("orbitai.events.service.DATABASE_FILE", "orbitai.materials.intake.DATABASE_FILE"):
            mock = patch(target, self.db)
            mock.start()
            self.addCleanup(mock.stop)
        # Any accidental old repository path must fail rather than initialize the real DB.
        guard = patch("orbitai.materials.repository.get_connection", side_effect=AssertionError("Unisolated legacy repository"))
        guard.start()
        self.addCleanup(guard.stop)
        from orbitai.web.app import create_app
        self.client = TestClient(create_app())

    def manual_form(self):
        return dict(source_id=self.source_id, title="Original manual excerpt", url="https://example.org/manual",
                    published_at="", content_text="Actual source text <script>not executed</script>")

    def save_preview(self, response, endpoint):
        self.assertEqual(response.status_code, 200, response.text)
        fields = HiddenFields(response.text).values
        self.assertTrue(fields.get("preview_token"))
        saved = self.client.post(endpoint, data=fields, follow_redirects=False)
        self.assertEqual(saved.status_code, 303, saved.text)
        return saved

    def event_form(self, event_id, document_id):
        return dict(id=event_id, title="Announcement " + event_id, summary="Source describes an announcement",
                    event_type_id="other", date_precision="unknown", status="candidate", origin="user",
                    change_reason="Link original evidence", organization_ids="openai",
                    segment_ids="general_foundation_models", document_ids=document_id)

    def test_manual_material_event_and_merge_full_http_path(self):
        before = self.snapshot()
        preview = self.client.post("/events/materials/preview", data=self.manual_form())
        self.assertEqual(self.snapshot(), before)
        self.assertIn("&lt;script&gt;", preview.text)
        saved = self.save_preview(preview, "/events/materials/save")
        document_id = parse_qs(urlsplit(saved.headers["location"]).query)["saved"][0]
        self.assertEqual(self.count("events"), 0)
        new_form = self.client.get("/events/new", params={"document_id": document_id})
        self.assertEqual(new_form.status_code, 200)
        self.assertIn(document_id, new_form.text)
        for event_id in ("source", "target"):
            preview = self.client.post("/events/preview", data=self.event_form(event_id, document_id))
            self.save_preview(preview, "/events/save")
        merge_form = self.client.get("/events/source/merge")
        self.assertEqual(merge_form.status_code, 200)
        before = self.snapshot()
        preview = self.client.post("/events/merge/preview", data=dict(source_id="source", target_id="target",
            expected_source_revision=load_event("source", self.db)["revision"], change_reason="Duplicate announcement"))
        self.assertEqual(self.snapshot(), before)
        saved = self.save_preview(preview, "/events/merge/save")
        self.assertEqual(saved.headers["location"], "/events/target")
        self.assertEqual(load_event("source", self.db)["status"], "archived")
        self.assertEqual(load_event("target", self.db)["status"], "candidate")
        self.assertEqual(load_event("target", self.db)["confirmed_by_user"], 0)
        self.assertEqual(self.count("event_change_log"), 4)
        self.assertEqual(self.count("documents"), 1)
        self.assertEqual(self.client.get("/events/target").status_code, 200)

    def test_duplicate_document_and_rss_references_rejected_and_snapshot_change_expires_preview(self):
        self.save(self.payload())  # Produces article_1, usable by either reference style.
        form = self.event_form("new", "article_1")
        response = self.client.post("/events/preview", data={**form, "article_ids": "1"})
        self.assertEqual(response.status_code, 422, response.text)
        response = self.client.post("/events/preview", data=form)
        self.assertEqual(response.status_code, 200, response.text)
        fields = HiddenFields(response.text).values
        with self.connection() as conn:
            conn.execute("UPDATE documents SET content_text='Changed evidence' WHERE id='article_1'")
        before = self.snapshot()
        result = self.client.post("/events/save", data=fields)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(self.snapshot(), before)

    def test_static_routes_are_not_interpreted_as_event_ids(self):
        with patch("orbitai.web.routes.events.load_event", side_effect=AssertionError("Static route captured as ID")):
            for path in ("/events/review", "/events/materials", "/events/extract"):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_every_new_post_rejects_cross_site_and_json_before_any_operation(self):
        paths = ("/events/materials/preview", "/events/materials/fetch", "/events/materials/save",
                 "/events/extract", "/events/merge/preview", "/events/merge/save")
        with patch("orbitai.web.routes.event_workflow.fetch_website_document") as fetch, patch(
                "orbitai.web.routes.event_workflow.extract_candidate") as extract:
            before = self.snapshot()
            for path in paths:
                for headers in ({"Origin": "https://evil.example"}, {"Referer": "https://evil.example/form"},
                                {"Sec-Fetch-Site": "cross-site"}):
                    with self.subTest(path=path, headers=headers):
                        self.assertEqual(self.client.post(path, data={"payload": "{}"}, headers=headers).status_code, 422)
                self.assertEqual(self.client.post(path, json={"payload": {}}).status_code, 422)
            fetch.assert_not_called()
            extract.assert_not_called()
            self.assertEqual(self.snapshot(), before)

    def test_website_fetch_is_post_only_and_preserves_provenance_token_without_auto_save(self):
        payload = {**self.manual_form(), "document_type": "web_article"}
        payload["fetch_token"] = _fetch_signature(payload)
        with patch("orbitai.web.routes.event_workflow.fetch_website_document", return_value=payload) as fetch:
            before = self.snapshot()
            self.assertEqual(self.client.get("/events/materials/fetch").status_code, 405)
            fetch.assert_not_called()
            response = self.client.post("/events/materials/fetch", data={"source_id": self.source_id, "url": payload["url"]})
            self.assertEqual(response.status_code, 200, response.text)
            fetch.assert_called_once_with(self.source_id, payload["url"])
            self.assertEqual(before, self.snapshot())
            fields = HiddenFields(response.text).values
            self.assertEqual(json.loads(fields["payload"])["fetch_token"], payload["fetch_token"])
            self.save_preview(response, "/events/materials/save")
            self.assertEqual(self.count("events"), 0)
            with self.connection() as conn:
                row = conn.execute("SELECT document_type,origin FROM documents").fetchone()
                self.assertEqual(tuple(row), ("web_article", "import"))


if __name__ == "__main__":
    unittest.main()
