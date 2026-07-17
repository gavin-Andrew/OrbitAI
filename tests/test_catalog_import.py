import copy
import sqlite3
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from orbitai.catalog.import_service import (
    CatalogImportBlocked,
    apply_catalog_seed,
    load_json_document,
    normalize_identity_name,
    preview_catalog_import,
    validate_catalog_seed,
)
from orbitai.catalog.repository import iter_catalog_records
from orbitai.database import get_connection, init_db


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = (
    PROJECT_ROOT
    / "data"
    / "seeds"
    / "catalog"
    / "foundation_models.v4.1.json"
)
SOURCE_REGISTRY_FILE = PROJECT_ROOT / "data" / "registries" / "sources.v4.json"
CATALOG_TABLES = (
    "industries",
    "segments",
    "industry_segments",
    "organizations",
    "organization_aliases",
    "people",
    "person_aliases",
    "person_organization_roles",
    "organization_segments",
    "person_segments",
    "sources",
    "source_entries",
)


class CatalogImportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_file = Path(self.temp_dir.name) / "catalog.db"
        init_db(self.database_file)
        self.seed = load_json_document(SEED_FILE, "测试名册种子")
        self.source_registry = load_json_document(
            SOURCE_REGISTRY_FILE,
            "测试来源注册表",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _catalog_counts(self, connection) -> dict[str, int]:
        return {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in CATALOG_TABLES
        }

    def test_identity_normalization_keeps_equivalent_forms_together(self):
        self.assertEqual(
            normalize_identity_name("  ＯｐｅｎＡＩ   Research  "),
            "openai research",
        )

    def test_confirmed_seed_passes_validation_with_two_known_warnings(self):
        result = validate_catalog_seed(self.seed, self.source_registry)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])
        self.assertEqual(
            [item.code for item in result.warnings],
            ["needs_primary_source", "needs_primary_source"],
        )

    def test_validation_rejects_broken_reference_and_identity_collision(self):
        invalid_seed = copy.deepcopy(self.seed)
        invalid_seed["person_segments"][0]["segment_id"] = "missing_segment"
        invalid_seed["people"][1]["aliases"].append("  SAM ALTMAN  ")

        result = validate_catalog_seed(invalid_seed, self.source_registry)
        error_codes = {item.code for item in result.errors}

        self.assertFalse(result.is_valid)
        self.assertIn("missing_reference", error_codes)
        self.assertIn("identity_name_collision", error_codes)

    def test_validation_reports_malformed_collection_item_without_crashing(self):
        invalid_seed = copy.deepcopy(self.seed)
        invalid_seed["organizations"][0] = "not-an-object"

        result = validate_catalog_seed(invalid_seed, self.source_registry)

        self.assertFalse(result.is_valid)
        self.assertIn(
            "invalid_collection_item",
            {item.code for item in result.errors},
        )

    def test_preview_is_read_only_and_exposes_all_action_types(self):
        with get_connection(self.database_file) as connection:
            before = self._catalog_counts(connection)
            report = preview_catalog_import(
                connection,
                self.seed,
                self.source_registry,
            )
            after = self._catalog_counts(connection)

        self.assertEqual(before, after)
        self.assertTrue(report.can_apply)
        self.assertFalse(report.applied)
        self.assertEqual(
            report.summary["action_counts"],
            {
                "create": 115,
                "create_from_split": 1,
                "intentionally_unbound": 1,
                "map_existing": 7,
            },
        )

    def test_normalized_database_identity_collision_blocks_apply(self):
        with get_connection(self.database_file) as connection:
            connection.execute(
                """
                INSERT INTO organizations (id, name)
                VALUES ('other_openai', '  OPENAI  ')
                """
            )
            connection.commit()

            report = preview_catalog_import(
                connection,
                self.seed,
                self.source_registry,
            )

        conflicts = [
            item
            for item in report.operations
            if item.entity_type == "organization" and item.action == "conflict"
        ]
        self.assertFalse(report.can_apply)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("other_openai", conflicts[0].reason)

    def test_apply_is_idempotent_and_writes_expected_rows(self):
        expected_counts = Counter(
            record.table for record in iter_catalog_records(self.seed)
        )

        with get_connection(self.database_file) as connection:
            first_report = apply_catalog_seed(
                connection,
                self.seed,
                self.source_registry,
            )
            first_counts = self._catalog_counts(connection)
            second_report = apply_catalog_seed(
                connection,
                self.seed,
                self.source_registry,
            )
            second_counts = self._catalog_counts(connection)

        self.assertTrue(first_report.applied)
        self.assertEqual(first_report.summary["inserted_count"], 124)
        self.assertEqual(first_counts, dict(expected_counts))
        self.assertTrue(second_report.applied)
        self.assertEqual(second_report.summary["inserted_count"], 0)
        self.assertEqual(second_counts, first_counts)
        self.assertEqual(
            second_report.summary["action_counts"],
            {"unchanged": 124},
        )

    def test_existing_user_change_is_previewed_and_never_overwritten(self):
        user_description = "用户自己补充的 OpenAI 描述"
        with get_connection(self.database_file) as connection:
            apply_catalog_seed(connection, self.seed, self.source_registry)
            connection.execute(
                "UPDATE organizations SET description = ? WHERE id = 'openai'",
                (user_description,),
            )
            connection.commit()

            report = preview_catalog_import(
                connection,
                self.seed,
                self.source_registry,
            )
            with self.assertRaises(CatalogImportBlocked):
                apply_catalog_seed(connection, self.seed, self.source_registry)
            stored_description = connection.execute(
                "SELECT description FROM organizations WHERE id = 'openai'"
            ).fetchone()[0]

        updates = [
            item
            for item in report.operations
            if item.entity_type == "organization"
            and item.key == "openai"
            and item.action == "update_preview"
        ]
        self.assertFalse(report.can_apply)
        self.assertEqual(len(updates), 1)
        self.assertIn("description", updates[0].changes)
        self.assertEqual(stored_description, user_description)

    def test_database_failure_rolls_back_the_whole_catalog(self):
        with get_connection(self.database_file) as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_deepseek
                BEFORE INSERT ON organizations
                WHEN NEW.id = 'deepseek'
                BEGIN
                    SELECT RAISE(ABORT, 'forced catalog failure');
                END
                """
            )
            connection.commit()

            with self.assertRaises(sqlite3.IntegrityError):
                apply_catalog_seed(connection, self.seed, self.source_registry)
            counts = self._catalog_counts(connection)

        self.assertEqual(counts, {table: 0 for table in CATALOG_TABLES})


if __name__ == "__main__":
    unittest.main()
