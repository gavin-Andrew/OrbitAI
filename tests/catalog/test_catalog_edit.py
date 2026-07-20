"""V4.1-D 名册编辑、冲突检测、事务与修改记录测试。"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from orbitai.catalog.edit_service import (
    CatalogEditConflict,
    CatalogEditValidationError,
    load_catalog_management_data,
    preview_catalog_edit,
    save_catalog_edit,
)
from orbitai.catalog.import_service import apply_catalog_seed, load_json_document
from orbitai.core.database import get_connection, init_db


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_FILE = (
    PROJECT_ROOT
    / "data"
    / "seeds"
    / "catalog"
    / "foundation_models.v4.1.json"
)
SOURCE_REGISTRY_FILE = PROJECT_ROOT / "data" / "registries" / "sources.v4.json"


class CatalogEditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_file = Path(self.temp_dir.name) / "catalog-edit.db"
        init_db(self.database_file)

        seed = load_json_document(SEED_FILE, "测试名册种子")
        source_registry = load_json_document(
            SOURCE_REGISTRY_FILE,
            "测试来源注册表",
        )
        with get_connection(self.database_file) as connection:
            apply_catalog_seed(connection, seed, source_registry)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _entity(self, entity_type: str, entity_id: str):
        data = load_catalog_management_data(self.database_file)
        return next(
            item
            for item in data["entities"]
            if item["entity_type"] == entity_type
            and item["entity_id"] == entity_id
        )

    @staticmethod
    def _payload(entity: dict, **overrides):
        values = {
            "name": entity["name"],
            "description": entity["description"],
            "status": entity["status"],
            "aliases": list(entity["aliases"]),
        }
        if entity["entity_type"] == "organization":
            values.update(
                {
                    "organization_type": entity["organization_type"],
                    "homepage_url": entity["homepage_url"],
                }
            )
        values.update(overrides)
        return {
            "entity_type": entity["entity_type"],
            "entity_id": entity["entity_id"],
            "expected_revision": entity["revision"],
            "values": values,
        }

    def test_management_data_contains_12_entities_and_no_initial_log(self):
        data = load_catalog_management_data(self.database_file)

        self.assertEqual(data["organization_count"], 6)
        self.assertEqual(data["person_count"], 6)
        self.assertEqual(len(data["entities"]), 12)
        self.assertEqual(data["change_log"], [])
        self.assertTrue(all(item["revision"] for item in data["entities"]))

    def test_preview_reports_diff_without_writing(self):
        before = self._entity("organization", "openai")
        payload = self._payload(
            before,
            description="经过预览但尚未保存的新简介。",
            aliases=[*before["aliases"], "Open AI Lab"],
        )

        preview = preview_catalog_edit(payload, self.database_file)
        after = self._entity("organization", "openai")

        self.assertTrue(preview["has_changes"])
        self.assertEqual(set(preview["changes"]), {"description", "aliases"})
        self.assertEqual(after["description"], before["description"])
        self.assertEqual(after["aliases"], before["aliases"])

    def test_save_updates_entity_and_log_in_one_transaction(self):
        before = self._entity("person", "sam_altman")
        payload = self._payload(
            before,
            description="经过人工确认的新人物简介。",
            aliases=[*before["aliases"], "S. Altman"],
        )
        payload["change_reason"] = "补充已经人工确认的人物说明和别名"

        result = save_catalog_edit(payload, self.database_file)
        data = load_catalog_management_data(self.database_file)
        after = self._entity("person", "sam_altman")

        self.assertTrue(result["ok"])
        self.assertNotEqual(after["revision"], before["revision"])
        self.assertIn("S. Altman", after["aliases"])
        self.assertEqual(len(data["change_log"]), 1)
        log = data["change_log"][0]
        self.assertEqual(log["entity_id"], "sam_altman")
        self.assertEqual(log["change_reason"], payload["change_reason"])
        self.assertEqual(set(log["changes"]), {"description", "aliases"})
        self.assertEqual(log["before"]["revision"], before["revision"])
        self.assertEqual(log["after"]["revision"], after["revision"])

    def test_stale_revision_refuses_to_overwrite_newer_save(self):
        original = self._entity("organization", "anthropic")
        first = self._payload(original, description="第一位用户保存的内容。")
        first["change_reason"] = "保存第一份已经确认的修改"
        save_catalog_edit(first, self.database_file)

        stale = self._payload(original, description="旧页面准备覆盖的内容。")
        stale["change_reason"] = "尝试从旧页面保存修改"

        with self.assertRaises(CatalogEditConflict) as context:
            save_catalog_edit(stale, self.database_file)

        current = self._entity("organization", "anthropic")
        self.assertEqual(current["description"], "第一位用户保存的内容。")
        self.assertEqual(context.exception.current["revision"], current["revision"])

    def test_normalized_name_collision_is_rejected(self):
        anthropic = self._entity("organization", "anthropic")
        payload = self._payload(
            anthropic,
            aliases=[*anthropic["aliases"], "  OPENAI  "],
        )

        with self.assertRaises(CatalogEditValidationError) as context:
            preview_catalog_edit(payload, self.database_file)

        self.assertIn("OpenAI", str(context.exception))

    def test_audit_failure_rolls_back_entity_and_aliases(self):
        before = self._entity("organization", "deepseek")
        payload = self._payload(
            before,
            name="DeepSeek Research",
            aliases=[*before["aliases"], "DeepSeek Lab"],
        )
        payload["change_reason"] = "验证审计失败时整组修改回滚"

        with get_connection(self.database_file) as connection:
            connection.execute(
                """
                CREATE TRIGGER fail_catalog_change_log
                BEFORE INSERT ON catalog_change_log
                BEGIN
                    SELECT RAISE(ABORT, 'forced audit failure');
                END
                """
            )

        with self.assertRaises(sqlite3.IntegrityError):
            save_catalog_edit(payload, self.database_file)

        after = self._entity("organization", "deepseek")
        self.assertEqual(after["name"], before["name"])
        self.assertEqual(after["aliases"], before["aliases"])
        self.assertEqual(after["revision"], before["revision"])

    def test_archiving_is_recorded_as_archive_action(self):
        person = self._entity("person", "elon_musk")
        payload = self._payload(person, status="archived")
        payload["change_reason"] = "演示错误对象采用归档而不是物理删除"

        result = save_catalog_edit(payload, self.database_file)
        data = load_catalog_management_data(self.database_file)

        self.assertEqual(result["action"], "archive")
        self.assertEqual(data["change_log"][0]["action"], "archive")
        self.assertEqual(self._entity("person", "elon_musk")["status"], "archived")


if __name__ == "__main__":
    unittest.main()
