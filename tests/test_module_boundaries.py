import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orbitai import catalog_import as catalog_import_cli
from orbitai import migrations as migrations_cli
from orbitai.catalog import import_service
from orbitai.core import migrations
from orbitai.core.database import init_db


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RETIRED_MODULES = (
    "orbitai/config.py",
    "orbitai/database.py",
    "orbitai/repository.py",
    "orbitai/rss_fetcher.py",
    "orbitai/ai_client.py",
    "orbitai/ai_processor.py",
    "orbitai/scoring.py",
    "orbitai/data_utils.py",
    "orbitai/catalog_repository.py",
    "orbitai/catalog_service.py",
    "orbitai/html_generator.py",
    "orbitai/models.py",
    "orbitai/materials/legacy_json.py",
    "orbitai/web/static_snapshots.py",
)

RETIRED_IMPORT_PATHS = (
    "orbitai.config",
    "orbitai.database",
    "orbitai.repository",
    "orbitai.rss_fetcher",
    "orbitai.ai_client",
    "orbitai.ai_processor",
    "orbitai.scoring",
    "orbitai.data_utils",
    "orbitai.catalog_repository",
    "orbitai.catalog_service",
    "orbitai.html_generator",
    "orbitai.models",
    "orbitai.materials.legacy_json",
    "orbitai.web.static_snapshots",
)


class ModuleBoundaryTests(unittest.TestCase):
    def test_retired_compatibility_modules_are_absent(self):
        for relative_path in RETIRED_MODULES:
            with self.subTest(relative_path=relative_path):
                self.assertFalse((PROJECT_ROOT / relative_path).exists())

    def test_active_modules_do_not_import_retired_paths(self):
        active_files = [PROJECT_ROOT / "main.py"]
        for package in ("core", "materials", "catalog", "web"):
            active_files.extend(
                (PROJECT_ROOT / "orbitai" / package).rglob("*.py")
            )

        for path in active_files:
            source = path.read_text(encoding="utf-8")
            for retired_import in RETIRED_IMPORT_PATHS:
                self.assertNotIn(retired_import, source, str(path))

    def test_supported_cli_wrappers_forward_to_active_implementations(self):
        self.assertIs(catalog_import_cli.main, import_service.main)
        self.assertIs(
            catalog_import_cli.preview_catalog_import,
            import_service.preview_catalog_import,
        )
        self.assertIs(migrations_cli.main, migrations.main)
        self.assertIs(migrations_cli.MIGRATIONS, migrations.MIGRATIONS)

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
