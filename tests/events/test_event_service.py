"""临时数据库上的预览、确认、追溯、冲突和原子回滚验证。"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from orbitai.catalog.import_service import apply_catalog_seed, load_json_document
from orbitai.core.database import get_connection, init_db
from orbitai.core.migrations import apply_migrations, rollback_last_migration
from orbitai.events.service import EventConflict, list_events, load_event, preview_event, save_event


ROOT = Path(__file__).resolve().parents[2]


class EventServiceTests(unittest.TestCase):
    def connection(self):
        conn = get_connection(self.db)
        self.addCleanup(conn.close)
        return conn

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "events.db"
        init_db(self.db)
        with self.connection() as conn:
            apply_catalog_seed(conn,
                load_json_document(ROOT / "data/seeds/catalog/foundation_models.v4.1.json", "test seed"),
                load_json_document(ROOT / "data/registries/sources.v4.json", "test sources"))
            self.source_id = conn.execute("SELECT id FROM sources ORDER BY id LIMIT 1").fetchone()[0]
            for aid in (1, 2):
                conn.execute("INSERT INTO articles (id,title,source,link,published,summary_original,summary_cn) VALUES (?,?,?,?,?,?,?)",
                    (aid, f"Original {aid}", "Test", f"https://example.org/news/{aid}",
                     "2026-07-01", f"Original source excerpt {aid}", "AI output must not be evidence"))

    def payload(self, **changes):
        result = dict(id="event_test", title="A narrowly scoped release", summary="Original evidence only",
            event_type_id="other", status="candidate", date_precision="day", date_start="2026-07-01",
            date_end="", notes="Evidence covers the announcement, not independent performance validation",
            change_reason="Initial candidate", organization_ids=["openai"],
            segment_ids=["general_foundation_models"], person_ids=[],
            materials=[dict(article_id=1, source_id=self.source_id, evidence_role="background")])
        result.update(changes)
        return result

    def save(self, payload):
        preview = preview_event(payload, self.db)
        event_id = save_event(preview["payload"], preview["preview_token"], self.db)
        return load_event(event_id, self.db)

    def count(self, table):
        with self.connection() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def snapshot(self):
        with self.connection() as conn:
            return list(conn.iterdump())

    def test_preview_is_read_only(self):
        before = self.snapshot()
        preview = preview_event(self.payload(), self.db)
        self.assertEqual(preview["after"]["status"], "candidate")
        self.assertEqual(before, self.snapshot())

    def test_candidate_confirm_correct_and_archive_lifecycle(self):
        event = self.save(self.payload())
        self.assertEqual(list_events(self.db, status="confirmed"), [])
        event = self.save(self.payload(expected_revision=event["revision"], status="confirmed",
            confirmed_by_user=True, change_reason="Manually checked original excerpt"))
        self.assertEqual(len(list_events(self.db, status="confirmed", organization_id="openai")), 1)
        self.assertEqual(len(event["history"]), 2)
        event = self.save(self.payload(expected_revision=event["revision"], title="Corrected title",
            status="confirmed", confirmed_by_user=True, change_reason="Correct title transcription"))
        entry = event["history"][0]
        self.assertEqual(json.loads(entry["before_json"])["title"], "A narrowly scoped release")
        self.assertEqual(json.loads(entry["after_json"])["title"], "Corrected title")
        event = self.save(self.payload(expected_revision=event["revision"], status="archived",
            change_reason="Duplicate candidate archived"))
        self.assertEqual(len(event["history"]), 4)
        self.assertEqual(list_events(self.db, status="confirmed"), [])
        self.assertEqual(self.count("events"), 1)
        self.assertEqual(self.count("documents"), 1)

    def test_confirmation_requires_actual_boolean_true(self):
        for value in (False, 1, "true", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                preview_event(self.payload(status="confirmed", confirmed_by_user=value), self.db)

    def test_empty_original_cannot_fall_back_to_ai(self):
        with self.connection() as conn:
            conn.execute("UPDATE articles SET summary_original='' WHERE id=1")
        with self.assertRaises(ValueError):
            preview_event(self.payload(status="confirmed", confirmed_by_user=True), self.db)
        self.assertEqual(self.count("documents"), 0)

    def test_token_tampering_and_changed_payload_are_rejected(self):
        preview = preview_event(self.payload(), self.db)
        with self.assertRaises(EventConflict):
            save_event(preview["payload"], "tampered", self.db)
        altered = dict(preview["payload"], title="Not previewed")
        with self.assertRaises(EventConflict):
            save_event(altered, preview["preview_token"], self.db)
        self.assertEqual(self.count("events"), 0)

    def test_stale_revision_and_changed_material_are_rejected(self):
        event = self.save(self.payload())
        stale = self.payload(expected_revision=event["revision"], title="Old edit")
        self.save(self.payload(expected_revision=event["revision"], title="New edit"))
        with self.assertRaises(EventConflict):
            preview_event(stale, self.db)
        # A second article has no saved immutable document yet.
        fresh = self.payload(id="event_fresh", materials=[dict(article_id=2)])
        preview = preview_event(fresh, self.db)
        with self.connection() as conn:
            conn.execute("UPDATE articles SET summary_original='Changed original' WHERE id=2")
        with self.assertRaises(EventConflict):
            save_event(preview["payload"], preview["preview_token"], self.db)

    def test_second_article_reuses_event_and_documents_are_shared(self):
        source_count = self.count("sources")
        event = self.save(self.payload())
        materials = [dict(article_id=i, source_id=self.source_id) for i in (1, 2)]
        event = self.save(self.payload(expected_revision=event["revision"], materials=materials))
        self.assertEqual(self.count("events"), 1)
        self.assertEqual(len(event["documents"]), 2)
        self.save(self.payload(id="event_other", materials=materials))
        self.assertEqual(self.count("documents"), 2)
        self.assertEqual(self.count("event_documents"), 4)
        self.assertEqual(self.count("sources"), source_count)
        self.assertEqual(event["documents"][0]["content_text"], "Original source excerpt 1")

    def test_dates_match_precision_and_range(self):
        for precision, start, end in (("unknown", "", ""), ("month", "2026-07", ""),
                ("quarter", "2026-Q3", ""), ("year", "2026", ""),
                ("range", "2026-07-01", "2026-07-03")):
            with self.subTest(precision=precision):
                preview_event(self.payload(date_precision=precision, date_start=start, date_end=end), self.db)
        for precision, start, end in (("unknown", "2026", ""), ("month", "2026-13", ""),
                ("day", "2026-02-30", ""), ("quarter", "2026-Q5", ""),
                ("year", "2026-01-01", ""), ("range", "2026-07-03", "2026-07-01"),
                ("range", "2026-07-01", ""), ("day", "2026-07-01", "2026-07-02")):
            with self.subTest(precision=precision, start=start), self.assertRaises(ValueError):
                preview_event(self.payload(date_precision=precision, date_start=start, date_end=end), self.db)

    def test_generated_id_survives_preview_save_roundtrip(self):
        payload = self.payload()
        del payload["id"]
        preview = preview_event(payload, self.db)
        event_id = save_event(preview["payload"], preview["preview_token"], self.db)
        self.assertEqual(event_id, preview["after"]["id"])
        self.assertEqual(self.count("events"), 1)

    def test_document_id_collision_must_not_attach_unpreviewed_evidence(self):
        with self.connection() as conn:
            conn.execute("INSERT INTO documents (id,article_id,title,url,content_text,document_type,origin) VALUES (?,?,?,?,?,?,?)",
                ("article_1", 2, "Wrong article", "https://example.org/news/2", "Unpreviewed body", "rss_excerpt", "import"))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.save(self.payload(status="confirmed", confirmed_by_user=True))
        self.assertEqual(before, self.snapshot())

    def test_saved_document_source_and_original_are_not_overwritten(self):
        event = self.save(self.payload())
        with self.connection() as conn:
            other_source = conn.execute("SELECT id FROM sources WHERE id<>? LIMIT 1", (self.source_id,)).fetchone()[0]
            conn.execute("UPDATE articles SET summary_original='Later feed text',summary_cn='AI replacement' WHERE id=1")
        with self.assertRaises(ValueError):
            preview_event(self.payload(expected_revision=event["revision"],
                materials=[dict(article_id=1, source_id=other_source)]), self.db)
        updated = self.save(self.payload(expected_revision=event["revision"], title="Retain source snapshot"))
        self.assertEqual(updated["documents"][0]["content_text"], "Original source excerpt 1")
        self.assertEqual(updated["documents"][0]["source_id"], self.source_id)

    def test_bad_foreign_keys_and_urls_are_rejected(self):
        for changes in (dict(event_type_id="missing"), dict(organization_ids=["missing"]),
                dict(segment_ids=["missing"]), dict(person_ids=["missing"]),
                dict(materials=[dict(article_id=999)]), dict(materials=[dict(article_id=1, source_id="missing")]),
                dict(materials=[]), dict(materials=[dict(article_id=True)])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                preview_event(self.payload(**changes), self.db)
        for url in ("javascript:alert(1)", "file:///tmp/a", "https://user:pass@example.org/a", "not-a-url"):
            with self.connection() as conn:
                conn.execute("UPDATE articles SET link=? WHERE id=1", (url,))
            with self.subTest(url=url), self.assertRaises(ValueError):
                preview_event(self.payload(), self.db)

    def test_audit_failure_rolls_back_creation_and_edits(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    event = self.save(self.payload())
                    payload = self.payload(expected_revision=event["revision"], title="Must roll back",
                        materials=[dict(article_id=2)])
                else:
                    payload = self.payload()
                with self.connection() as conn:
                    conn.execute("CREATE TRIGGER reject_event_audit BEFORE INSERT ON event_change_log BEGIN SELECT RAISE(ABORT,'test audit failure'); END")
                before = self.snapshot()
                with self.assertRaises(sqlite3.IntegrityError):
                    self.save(payload)
                self.assertEqual(self.snapshot(), before)
                with self.connection() as conn:
                    conn.execute("DROP TRIGGER reject_event_audit")

    def test_document_id_collision_never_links_another_articles_evidence(self):
        with self.connection() as conn:
            conn.execute("INSERT INTO documents(id,article_id,title,url,content_text) VALUES ('article_1',2,'Wrong article','https://example.org/wrong','Wrong evidence')")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.save(self.payload(status="confirmed", confirmed_by_user=True))
        self.assertEqual(self.snapshot(), before)

    def test_migration_0007_only_adds_audit_and_requires_explicit_rollback(self):
        with self.connection() as conn:
            with self.assertRaises(RuntimeError):
                rollback_last_migration(conn)
            self.assertEqual(rollback_last_migration(conn, allow_destructive=True), "0007")
        before = self.snapshot()
        preview = preview_event(self.payload(), self.db)
        with self.assertRaises(ValueError):
            save_event(preview["payload"], preview["preview_token"], self.db)
        self.assertEqual(before, self.snapshot())
        counts = {table: self.count(table) for table in ("articles", "events", "documents", "sources", "organizations")}
        with self.connection() as conn:
            self.assertEqual(apply_migrations(conn), ["0007"])
        self.assertEqual(self.count("event_change_log"), 0)
        self.assertEqual(counts, {table: self.count(table) for table in counts})


if __name__ == "__main__":
    unittest.main()
