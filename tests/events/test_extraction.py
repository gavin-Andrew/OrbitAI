"""Mock model responses and temporary databases; never call a remote provider."""

import json
import unittest
from unittest.mock import patch

from tests.events import test_event_service as fixtures
from orbitai.events.extraction import (
    ExtractionError, build_extraction_input, extract_candidate, validate_candidate,
)


class ExtractionTests(unittest.TestCase):
    connection = fixtures.EventServiceTests.connection
    payload = fixtures.EventServiceTests.payload
    save = fixtures.EventServiceTests.save
    snapshot = fixtures.EventServiceTests.snapshot

    def setUp(self):
        fixtures.EventServiceTests.setUp(self)
        with self.connection() as conn:
            conn.execute("UPDATE articles SET title='OpenAI announces a model', "
                         "summary_original='OpenAI announced a model on 2026-07-01.' WHERE id=1")

    def response(self, **changes):
        event = dict(title="OpenAI 公布模型", summary="原文称 OpenAI 公布了模型。",
                     event_type_id="model_release", organization_ids=["openai"], person_ids=[],
                     evidence=[dict(article_id=1, quote="OpenAI announced a model on 2026-07-01.")],
                     date_start="", date_quote="", date_article_id=None, doubts=[])
        event.update(changes)
        return json.dumps(dict(event=event, reason="模型公告，单个事件"), ensure_ascii=False)

    def test_valid_proposal_is_read_only_and_never_confirmed(self):
        before = self.snapshot()
        result = validate_candidate([1], self.response(), self.db)
        self.assertEqual(result["event"]["origin"], "ai")
        self.assertFalse(result["event"]["confirmed_by_user"])
        self.assertEqual(result["event"]["date_precision"], "unknown")
        self.assertEqual(result["event"]["id"], "")
        self.assertEqual(before, self.snapshot())

    def test_original_only_and_existing_snapshot_wins(self):
        self.save(self.payload())
        with self.connection() as conn:
            conn.execute("UPDATE articles SET summary_original='Changed current excerpt' WHERE id=1")
        result = build_extraction_input([1], self.db)
        self.assertIn("OpenAI announced", result["materials"][0]["excerpt"])
        self.assertNotIn("AI output must not be evidence", json.dumps(result))

    def test_bounds_missing_original_and_ai_fallback_rejected(self):
        for ids in ([], [1, 1], [True], [1, 2, 3, 4], [999], ["1"]):
            with self.subTest(ids=ids), self.assertRaises(ExtractionError):
                build_extraction_input(ids, self.db)
        with self.connection() as conn:
            conn.execute("UPDATE articles SET summary_original='' WHERE id=1")
        with self.assertRaises(ExtractionError):
            build_extraction_input([1], self.db)

    def test_fabricated_quote_and_unrelated_person_rejected(self):
        for changes in (dict(evidence=[dict(article_id=1, quote="Invented")]),
                        dict(evidence=[dict(article_id=2, quote="OpenAI")]),
                        dict(organization_ids=["unlisted"]), dict(person_ids=["sam_altman"])):
            with self.subTest(changes=changes), self.assertRaises(ExtractionError):
                validate_candidate([1], self.response(**changes), self.db)

    def test_date_requires_explicit_original_evidence(self):
        unsupported = validate_candidate([1], self.response(date_start="2026-07-01"), self.db)
        self.assertEqual(unsupported["event"]["date_precision"], "unknown")
        supported = validate_candidate([1], self.response(date_start="2026-07-01",
            date_quote="OpenAI announced a model on 2026-07-01.", date_article_id=1), self.db)
        self.assertEqual(supported["event"]["date_start"], "2026-07-01")
        self.assertIn("日期原文依据", supported["payload"]["notes"])

    def test_null_event_and_linked_event_suggestion(self):
        self.save(self.payload())
        result = validate_candidate([1], '{"event":null,"reason":"材料不支持事件"}', self.db)
        self.assertIsNone(result["event"])
        self.assertEqual(result["related_events"][0]["id"], "event_test")

    def test_strict_json_rejects_extra_fields_and_confirmation(self):
        bad = json.loads(self.response())
        bad["event"]["confirmed_by_user"] = True
        for response in ("```json\n{}\n```", "[]", '{"event":null,"event":null,"reason":"x"}',
                         json.dumps(bad), self.response(doubts="wrong"), self.response(organization_ids=True)):
            with self.subTest(response=response), self.assertRaises(ExtractionError):
                validate_candidate([1], response, self.db)

    def test_provider_receives_only_selected_original_materials(self):
        response = self.response(organization_ids=["OpenAI"])
        before = self.snapshot()
        with patch("orbitai.events.extraction.create_ai_client", return_value={
                "base_url": "https://api.deepseek.com", "api_key": "secret"}), \
             patch("orbitai.events.extraction.request_chat_completion", return_value=response) as request:
            result = extract_candidate([1], self.db)
        sent = json.loads(request.call_args.args[1][1]["content"])
        self.assertEqual(set(sent), {"materials"})
        self.assertEqual(set(sent["materials"][0]), {"id", "title", "excerpt"})
        self.assertEqual(request.call_args.kwargs, {"max_tokens": 1600, "thinking": False})
        self.assertEqual(result["payload"]["organization_ids"], ["openai"])
        self.assertEqual(before, self.snapshot())

    def test_custom_destination_rejected_before_network_and_error_redacted(self):
        for url in ("https://custom.example", "http://api.deepseek.com", "https://api.deepseek.com@evil.example",
                    "https://api.deepseek.com/other", "https://api.deepseek.com?x=1"):
            with self.subTest(url=url), patch("orbitai.events.extraction.create_ai_client", return_value={
                    "base_url": url, "api_key": "secret"}), \
                 patch("orbitai.events.extraction.request_chat_completion") as request:
                with self.assertRaises(ExtractionError):
                    extract_candidate([1], self.db)
                request.assert_not_called()
        with patch("orbitai.events.extraction.create_ai_client", return_value={
                "base_url": "https://api.deepseek.com", "api_key": "secret"}), \
             patch("orbitai.events.extraction.request_chat_completion", side_effect=RuntimeError("secret")):
            with self.assertRaises(ExtractionError) as failure:
                extract_candidate([1], self.db)
            self.assertNotIn("secret", str(failure.exception))

    def test_segments_follow_local_relations_without_pilot_hardcoding(self):
        with self.connection() as conn:
            conn.execute("DELETE FROM organization_segments WHERE organization_id='openai'")
            conn.execute("INSERT INTO organization_segments(organization_id,segment_id) VALUES ('openai','multimodal_understanding_generation')")
        result = validate_candidate([1], self.response(), self.db)
        self.assertEqual(result["payload"]["segment_ids"], ["multimodal_understanding_generation"])

    def test_generation_rejects_material_changed_during_model_call(self):
        def changed(*args, **kwargs):
            with self.connection() as conn:
                conn.execute("UPDATE articles SET summary_original=summary_original || ' Retracted.' WHERE id=1")
            return self.response(organization_ids=["OpenAI"])
        with patch("orbitai.events.extraction.create_ai_client", return_value={"base_url": "https://api.deepseek.com"}), \
             patch("orbitai.events.extraction.request_chat_completion", side_effect=changed):
            with self.assertRaisesRegex(ExtractionError, "生成期间"):
                extract_candidate([1], self.db)

    def test_unlisted_model_entity_becomes_doubt_without_expanding_roster(self):
        with patch("orbitai.events.extraction.create_ai_client", return_value={"base_url": "https://api.deepseek.com"}), \
             patch("orbitai.events.extraction.request_chat_completion", return_value=self.response(organization_ids=["OpenAI", "Unlisted"] )):
            result = extract_candidate([1], self.db)
        self.assertEqual(result["payload"]["organization_ids"], ["openai"])
        self.assertIn("未自动新增或关联", " ".join(result["doubts"]))


if __name__ == "__main__":
    unittest.main()
