"""Original material intake uses temporary databases and mocked network only."""

import sqlite3
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, patch

from orbitai.core.database import init_db
from orbitai.materials import intake


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "materials.db"
        init_db(self.db)
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO sources (id,name,source_type) VALUES ('anthropic','Anthropic','institution')")

    def payload(self, **changes):
        payload = dict(source_id="anthropic", title="Original announcement", url="https://example.org/article",
                       published_at="", content_text="Exact original excerpt, not an AI summary.",
                       document_type="manual_excerpt")
        payload.update(changes)
        return payload

    def snapshot(self):
        with sqlite3.connect(self.db) as conn:
            return list(conn.iterdump())

    def save(self, payload):
        preview = intake.preview_document(payload, self.db)
        return intake.save_document(preview["payload"], preview["preview_token"], self.db)

    def test_preview_read_only_save_original_without_event(self):
        before = self.snapshot()
        preview = intake.preview_document(self.payload(), self.db)
        self.assertEqual(before, self.snapshot())
        doc_id = intake.save_document(preview["payload"], preview["preview_token"], self.db)
        document = intake.list_documents(self.db)[0]
        self.assertEqual(document["id"], doc_id)
        self.assertEqual(document["content_text"], self.payload()["content_text"])
        self.assertEqual(document["document_type"], "manual_excerpt")
        self.assertEqual(document["origin"], "user")
        self.assertIsNone(document["published_at"])
        self.assertEqual(document["source_name"], "Anthropic")
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_invalid_input_unknown_source_and_unsafe_urls(self):
        for changes in ({"source_id": "missing"}, {"title": ""}, {"content_text": ""},
                        {"url": "javascript:alert(1)"}, {"url": "https://user:pass@example.com/a"},
                        {"url": "https://example.org:invalid/a"}, {"document_type": "rss_excerpt"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                intake.preview_document(self.payload(**changes), self.db)

    def test_duplicate_url_fragment_normalization_never_overwrites(self):
        self.save(self.payload())
        before = self.snapshot()
        with self.assertRaises(intake.DocumentConflict):
            self.save(self.payload(url="https://EXAMPLE.org:443/article#section", content_text="Replacement"))
        self.assertEqual(before, self.snapshot())

    def test_tampering_and_source_changes_invalidate_preview(self):
        preview = intake.preview_document(self.payload(), self.db)
        with self.assertRaises(intake.DocumentConflict):
            intake.save_document(self.payload(title="Changed"), preview["preview_token"], self.db)
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE sources SET name='New name'")
        with self.assertRaises(intake.DocumentConflict):
            intake.save_document(preview["payload"], preview["preview_token"], self.db)
        self.assertEqual(intake.list_documents(self.db), [])

    def test_duplicate_insert_between_preview_and_save(self):
        preview = intake.preview_document(self.payload(), self.db)
        self.save(self.payload())
        with self.assertRaises(intake.DocumentConflict):
            intake.save_document(preview["payload"], preview["preview_token"], self.db)
        self.assertEqual(len(intake.list_documents(self.db)), 1)

    def test_transaction_rolls_back_on_insert_failure(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TRIGGER deny_document BEFORE INSERT ON documents BEGIN SELECT RAISE(ABORT,'denied'); END")
        before = self.snapshot()
        with self.assertRaises(sqlite3.IntegrityError):
            self.save(self.payload())
        self.assertEqual(before, self.snapshot())

    def test_missing_database_never_created(self):
        missing = Path(self.tmp.name) / "missing.db"
        with self.assertRaises(sqlite3.OperationalError):
            intake.preview_document(self.payload(), missing)
        with self.assertRaises(sqlite3.OperationalError):
            intake.save_document(self.payload(), "token", missing)
        self.assertFalse(missing.exists())

    def website_payload(self):
        html = '<article><h1>New model announcement</h1><time datetime="2026-09-15">Date</time><p>' + ("Original source sentence. " * 25) + '</p></article>'
        with patch.object(intake, "_read_official", return_value=("https://www.anthropic.com/news/model", html)):
            return intake.fetch_website_document("anthropic", "https://www.anthropic.com/news/model?tracking=1")

    def test_website_ready_body_saved_and_cannot_be_forged(self):
        payload = self.website_payload()
        doc_id = self.save(payload)
        document = intake.list_documents(self.db)[0]
        self.assertEqual(document["id"], doc_id)
        self.assertEqual(document["origin"], "import")
        self.assertEqual(document["document_type"], "web_article")
        self.assertEqual(document["published_at"], "2026-09-15")
        for changes in ({"content_text": "Fabricated"}, {"source_id": "meta_ai"}, {"fetch_token": "forged"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                intake.preview_document(dict(payload, **changes), self.db)

    def test_website_not_ready_never_imported(self):
        for html in ("<h1>Title</h1><p>Too short</p>",
                     "<article><h1>Title</h1><p>" + "Words " * 100 + "</p></article>"):
            with patch.object(intake, "_read_official", return_value=("https://www.anthropic.com/news/model", html)):
                with self.assertRaises(ValueError):
                    intake.fetch_website_document("anthropic", "https://www.anthropic.com/news/model")
        self.assertEqual(intake.list_documents(self.db), [])

    def test_manual_and_web_official_url_identity_is_symmetric(self):
        web = self.website_payload()
        manual = self.payload(url=web["url"] + "?tracking=1#section")
        for first, second in ((web, manual), (manual, web)):
            with self.subTest(first=first["document_type"]):
                self.save(first)
                before = self.snapshot()
                with self.assertRaises(intake.DocumentConflict):
                    self.save(second)
                self.assertEqual(before, self.snapshot())
                with sqlite3.connect(self.db) as conn:
                    conn.execute("DELETE FROM documents")

    def test_unknown_site_keeps_meaningful_query_identity(self):
        self.save(self.payload(url="https://example.org/article?id=1"))
        self.save(self.payload(url="https://example.org/article?id=2"))
        self.assertEqual(len(intake.list_documents(self.db)), 2)

    def test_website_whitelist_and_no_paid_fallback(self):
        with patch.object(intake, "_read_official") as read:
            for source, url in (("spacexai", "https://x.ai/news/model"),
                                ("anthropic", "https://evil.example/news/model"),
                                ("anthropic", "https://www.anthropic.com/news"),
                                ("anthropic", "https://www.anthropic.com:8080/news/model")):
                with self.assertRaises(ValueError):
                    intake.fetch_website_document(source, url)
            read.assert_not_called()

    def test_redirect_rejected_before_follow_and_response_checked(self):
        rule = intake.web_sources.WEBSITE_SOURCE_RULES["anthropic"]
        response = MagicMock()
        response.geturl.return_value = "https://www.anthropic.com/news/model"
        response.headers = Message()
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        response.read.return_value = b"<article>Original</article>"
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        with patch.object(intake, "build_opener", return_value=opener) as build:
            intake._read_official(rule, "https://www.anthropic.com/news/model")
            redirect = build.call_args.args[1]
            with self.assertRaises(ValueError):
                redirect.redirect_request(None, None, 302, "", {}, "https://evil.example/news/model")
            response.geturl.return_value = "https://evil.example/news/model"
            with self.assertRaises(ValueError):
                intake._read_official(rule, "https://www.anthropic.com/news/model")


if __name__ == "__main__":
    unittest.main()
