import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orbitai import ai_client as legacy_ai_client
from orbitai import ai_processor as legacy_ai_processor
from orbitai import catalog_import as legacy_catalog_import
from orbitai import catalog_repository as legacy_catalog_repository
from orbitai import catalog_service as legacy_catalog_service
from orbitai import data_utils as legacy_data_utils
from orbitai import html_generator as legacy_html_generator
from orbitai import repository as legacy_repository
from orbitai import rss_fetcher as legacy_rss
from orbitai import scoring as legacy_scoring
from orbitai.catalog import import_service, repository as catalog_repository
from orbitai.catalog import service as catalog_service
from orbitai.core.database import init_db
from orbitai.materials import ai_client, ai_processor, fields, legacy_json
from orbitai.materials import repository, rss, scoring
from orbitai.web import static_snapshots, view_helpers


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ModuleBoundaryTests(unittest.TestCase):
    def test_legacy_material_modules_forward_to_active_implementations(self):
        self.assertIs(legacy_ai_client.create_ai_client, ai_client.create_ai_client)
        self.assertIs(
            legacy_ai_processor.process_ai_items,
            ai_processor.process_ai_items,
        )
        self.assertIs(
            legacy_repository.get_all_articles,
            repository.get_all_articles,
        )
        self.assertIs(legacy_rss.fetch_rss, rss.fetch_rss)
        self.assertIs(legacy_scoring.get_featured_items, scoring.get_featured_items)
        self.assertIs(legacy_data_utils.create_new_item, fields.create_new_item)
        self.assertIs(
            legacy_data_utils.load_existing_data,
            legacy_json.load_existing_data,
        )

    def test_legacy_catalog_modules_forward_to_active_implementations(self):
        self.assertIs(
            legacy_catalog_repository.CatalogRepository,
            catalog_repository.CatalogRepository,
        )
        self.assertIs(
            legacy_catalog_service.load_industry_catalog,
            catalog_service.load_industry_catalog,
        )
        self.assertIs(
            legacy_catalog_import.preview_catalog_import,
            import_service.preview_catalog_import,
        )
        self.assertIs(legacy_catalog_import.main, import_service.main)

    def test_display_helpers_and_static_generation_have_separate_owners(self):
        self.assertIs(
            legacy_html_generator.get_display_title,
            view_helpers.get_display_title,
        )
        self.assertIs(
            legacy_html_generator.get_today_items,
            view_helpers.get_today_items,
        )
        self.assertIs(
            legacy_html_generator.generate_html,
            static_snapshots.generate_html,
        )
        self.assertIs(
            legacy_html_generator.generate_daily_html,
            static_snapshots.generate_daily_html,
        )

    def test_active_modules_do_not_import_legacy_implementation_paths(self):
        legacy_imports = (
            "orbitai.repository",
            "orbitai.rss_fetcher",
            "orbitai.ai_client",
            "orbitai.ai_processor",
            "orbitai.scoring",
            "orbitai.data_utils",
            "orbitai.catalog_repository",
            "orbitai.catalog_service",
            "orbitai.catalog_import",
            "orbitai.html_generator",
        )
        active_files = [PROJECT_ROOT / "main.py"]
        for package in ("materials", "catalog", "web"):
            active_files.extend(
                (PROJECT_ROOT / "orbitai" / package).rglob("*.py")
            )

        for path in active_files:
            source = path.read_text(encoding="utf-8")
            for legacy_import in legacy_imports:
                self.assertNotIn(legacy_import, source, str(path))

    def test_legacy_and_active_catalog_clis_match_from_other_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_file = Path(temp_dir) / "catalog-cli.db"
            init_db(database_file)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                value
                for value in (
                    str(PROJECT_ROOT),
                    environment.get("PYTHONPATH", ""),
                )
                if value
            )
            environment["PYTHONDONTWRITEBYTECODE"] = "1"

            for module_name in (
                "orbitai.catalog_import",
                "orbitai.catalog.import_service",
            ):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        module_name,
                        "preview",
                        "--database",
                        str(database_file),
                        "--summary-only",
                    ],
                    cwd=temp_dir,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=(
                        f"module={module_name}\n"
                        f"stdout:\n{result.stdout}\n"
                        f"stderr:\n{result.stderr}"
                    ),
                )
                self.assertIn('"applied": false', result.stdout)


if __name__ == "__main__":
    unittest.main()
