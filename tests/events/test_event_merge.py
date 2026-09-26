"""Duplicate-event merge checks exclusively against temporary databases."""

import sqlite3
import unittest

from orbitai.events.merge import preview_merge, save_merge
from orbitai.events.service import EventConflict, load_event, list_events
from tests.events import test_event_service as fixtures


class EventMergeTests(unittest.TestCase):
    setUp = fixtures.EventServiceTests.setUp
    connection = fixtures.EventServiceTests.connection
    payload = fixtures.EventServiceTests.payload
    save = fixtures.EventServiceTests.save
    snapshot = fixtures.EventServiceTests.snapshot
    count = fixtures.EventServiceTests.count

    def pair(self):
        source = self.save(self.payload(id="source", title="Source wording", materials=[
            dict(article_id=1, evidence_role="expert", notes="Source annotation"),
            dict(article_id=2, evidence_role="background")]))
        target = self.save(self.payload(id="target", title="Target wording", status="confirmed",
            confirmed_by_user=True, materials=[dict(article_id=1, evidence_role="official", notes="Target annotation")]))
        return dict(source_id=source["id"], target_id=target["id"],
            expected_source_revision=source["revision"], expected_target_revision=target["revision"],
            change_reason="Same announcement covered twice")

    def test_preview_read_only_and_merge_preserves_evidence_and_requires_confirmation(self):
        payload = self.pair()
        before = self.snapshot()
        preview = preview_merge(payload, self.db)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(preview["conflicts"][0]["target_evidence_role"], "official")
        self.assertEqual(save_merge(preview["payload"], preview["preview_token"], self.db), "target")
        source, target = [load_event(key, self.db) for key in ("source", "target")]
        self.assertEqual(source["status"], "archived")
        self.assertEqual(target["status"], "candidate")
        self.assertEqual(target["confirmed_by_user"], 0)
        self.assertEqual(target["title"], "Target wording")
        self.assertEqual(source["title"], "Source wording")
        self.assertEqual(len(source["documents"]), 2)
        self.assertEqual(len(target["documents"]), 2)
        self.assertEqual(self.count("documents"), 2)
        self.assertEqual(self.count("events"), 2)
        self.assertEqual(self.count("event_change_log"), 4)
        self.assertEqual(list_events(self.db, status="confirmed"), [])
        self.assertIn("target", source["notes"])
        self.assertIn("source", target["notes"])
        self.assertEqual(target["documents"][0]["evidence_role"], "official")
        self.assertIn("Source annotation", target["documents"][0]["notes"])
        self.assertEqual(sum(doc["is_primary"] for doc in target["documents"]), 1)
        self.assertEqual(source["documents"][0]["evidence_role"], "expert")

    def test_relationship_roles_notes_and_participants_are_preserved(self):
        payload = self.pair()
        with self.connection() as conn:
            other_org = conn.execute("SELECT id FROM organizations WHERE id<>'openai' LIMIT 1").fetchone()[0]
            conn.execute("INSERT INTO event_organizations VALUES (?,?,?,?)", ("source", other_org, "announcer", "Source role"))
            conn.execute("UPDATE event_organizations SET notes='Source organization note' WHERE event_id='source' AND organization_id='openai'")
        payload["expected_source_revision"] = load_event("source", self.db)["revision"]
        preview = preview_merge(payload, self.db)
        save_merge(payload, preview["preview_token"], self.db)
        with self.connection() as conn:
            row = conn.execute("SELECT role,notes FROM event_organizations WHERE event_id='target' AND organization_id=?", (other_org,)).fetchone()
            self.assertEqual(tuple(row), ("announcer", "Source role"))
            self.assertIn("Source organization note", conn.execute("SELECT notes FROM event_organizations WHERE event_id='target' AND organization_id='openai'").fetchone()[0])

    def test_invalid_pairs_and_missing_reason_are_rejected(self):
        payload = self.pair()
        for changes in ({"source_id": "target"}, {"target_id": "missing"}, {"change_reason": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                preview_merge(dict(payload, **changes), self.db)
        with self.connection() as conn:
            conn.execute("UPDATE events SET status='archived' WHERE id='source'")
        with self.assertRaisesRegex(ValueError, "归档"):
            preview_merge(payload, self.db)

    def test_token_tampering_and_payload_changes_roll_back(self):
        payload = self.pair()
        preview = preview_merge(payload, self.db)
        before = self.snapshot()
        for data, token in ((payload, "bad"), (dict(payload, change_reason="Changed"), preview["preview_token"])):
            with self.assertRaises(EventConflict):
                save_merge(data, token, self.db)
            self.assertEqual(self.snapshot(), before)

    def test_stale_source_target_and_materials_rejected(self):
        payload = self.pair()
        for sql in ("UPDATE events SET title='Changed' WHERE id='source'",
                    "UPDATE events SET title='Changed' WHERE id='target'",
                    "UPDATE documents SET content_text='Changed' WHERE id='article_1'",
                    "UPDATE event_organizations SET notes='Changed relation note' WHERE event_id='source'"):
            with self.subTest(sql=sql):
                payload["expected_source_revision"] = load_event("source", self.db)["revision"]
                payload["expected_target_revision"] = load_event("target", self.db)["revision"]
                preview = preview_merge(payload, self.db)
                with self.connection() as conn:
                    conn.execute(sql)
                before = self.snapshot()
                with self.assertRaises(EventConflict):
                    save_merge(payload, preview["preview_token"], self.db)
                self.assertEqual(self.snapshot(), before)

    def test_second_audit_failure_rolls_back_both_events_and_first_log(self):
        payload = self.pair()
        with self.connection() as conn:
            conn.execute("CREATE TRIGGER reject_merge_audit BEFORE INSERT ON event_change_log WHEN NEW.event_id='target' BEGIN SELECT RAISE(ABORT,'audit failure'); END")
        preview = preview_merge(payload, self.db)
        before = self.snapshot()
        with self.assertRaises(sqlite3.IntegrityError):
            save_merge(payload, preview["preview_token"], self.db)
        self.assertEqual(before, self.snapshot())

    def test_missing_audit_schema_is_not_auto_migrated(self):
        payload = self.pair()
        with self.connection() as conn:
            conn.execute("DROP TABLE event_change_log")
        payload["expected_source_revision"] = load_event("source", self.db)["revision"]
        payload["expected_target_revision"] = load_event("target", self.db)["revision"]
        preview = preview_merge(payload, self.db)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "0007"):
            save_merge(payload, preview["preview_token"], self.db)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
