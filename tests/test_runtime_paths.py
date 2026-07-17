import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orbitai.core import config
from orbitai.core.database import get_connection, init_db
from orbitai.materials import repository


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RuntimePathTests(unittest.TestCase):
    def test_runtime_and_versioned_data_paths_are_separated(self):
        self.assertEqual(config.VAR_DIR, PROJECT_ROOT / "var")
        self.assertEqual(config.DATABASE_FILE, PROJECT_ROOT / "var" / "orbitai.db")
        self.assertEqual(
            config.SNAPSHOT_DIR,
            PROJECT_ROOT / "var" / "snapshots",
        )
        self.assertEqual(config.DATA_FILE, PROJECT_ROOT / "data" / "archive" / "data.json")
        self.assertEqual(
            config.SOURCES_FILE,
            PROJECT_ROOT / "data" / "registries" / "sources.json",
        )
        self.assertEqual(
            config.SOURCE_REGISTRY_FILE,
            PROJECT_ROOT / "data" / "registries" / "sources.v4.json",
        )
        self.assertEqual(
            config.CATALOG_SEED_FILE,
            PROJECT_ROOT
            / "data"
            / "seeds"
            / "catalog"
            / "foundation_models.v4.1.json",
        )

    def test_read_connection_refuses_to_create_a_missing_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_file = Path(temp_dir) / "missing.db"

            with self.assertRaisesRegex(FileNotFoundError, "拒绝静默创建空库"):
                get_connection(database_file)

            self.assertFalse(database_file.exists())

    def test_explicit_initialization_can_create_a_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_file = Path(temp_dir) / "explicit.db"

            applied = init_db(database_file)

            self.assertTrue(database_file.exists())
            self.assertEqual(applied, ["0001", "0002", "0003", "0004", "0005"])

    def test_material_repository_refuses_a_missing_activity_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_file = Path(temp_dir) / "missing-active.db"
            with patch("orbitai.core.database.DATABASE_FILE", database_file):
                with self.assertRaisesRegex(
                    FileNotFoundError,
                    "拒绝静默创建空库",
                ):
                    repository.get_all_articles()

            self.assertFalse(database_file.exists())

    def test_relocated_versioned_json_files_are_readable(self):
        rss_sources = json.loads(config.SOURCES_FILE.read_text(encoding="utf-8"))
        source_registry = json.loads(
            config.SOURCE_REGISTRY_FILE.read_text(encoding="utf-8")
        )
        catalog_seed = json.loads(
            config.CATALOG_SEED_FILE.read_text(encoding="utf-8")
        )

        self.assertIsInstance(rss_sources, list)
        self.assertIsInstance(source_registry, dict)
        self.assertEqual(catalog_seed["seed_id"], "v4_1_foundation_models_roster")


if __name__ == "__main__":
    unittest.main()
