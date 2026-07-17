import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orbitai import config as legacy_config
from orbitai import database as legacy_database
from orbitai import migrations as legacy_migrations
from orbitai.catalog_import import (
    DEFAULT_DATABASE_FILE,
    DEFAULT_SEED_FILE,
    DEFAULT_SOURCE_REGISTRY_FILE,
)
from orbitai.core import config as core_config
from orbitai.core import database as core_database
from orbitai.core import migrations as core_migrations


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class CorePathTests(unittest.TestCase):
    def test_current_project_paths_are_absolute_and_centralized(self):
        expected_paths = {
            "PROJECT_ROOT": PROJECT_ROOT,
            "DATA_FILE": PROJECT_ROOT / "data.json",
            "DATABASE_FILE": PROJECT_ROOT / "orbitai.db",
            "SNAPSHOT_DIR": PROJECT_ROOT / "snapshots",
            "SOURCES_FILE": PROJECT_ROOT / "sources.json",
            "SOURCE_REGISTRY_FILE": PROJECT_ROOT / "sources.v4.json",
            "CATALOG_SEED_FILE": (
                PROJECT_ROOT
                / "data"
                / "catalog"
                / "foundation_models.v4.1.json"
            ),
            "TEMPLATES_DIR": PROJECT_ROOT / "templates",
            "STATIC_DIR": PROJECT_ROOT / "static",
        }

        for name, expected in expected_paths.items():
            actual = getattr(core_config, name)
            self.assertTrue(actual.is_absolute(), name)
            self.assertEqual(actual, expected, name)

    def test_legacy_modules_forward_to_core_implementations(self):
        self.assertIs(legacy_config.PROJECT_ROOT, core_config.PROJECT_ROOT)
        self.assertIs(legacy_config.DATABASE_FILE, core_config.DATABASE_FILE)
        self.assertIs(
            legacy_database.get_connection,
            core_database.get_connection,
        )
        self.assertIs(legacy_database.init_db, core_database.init_db)
        self.assertIs(
            legacy_database.apply_migrations,
            core_database.apply_migrations,
        )
        self.assertIs(
            legacy_migrations.apply_migrations,
            core_migrations.apply_migrations,
        )
        self.assertIs(legacy_migrations.MIGRATIONS, core_migrations.MIGRATIONS)

    def test_catalog_cli_defaults_use_centralized_paths(self):
        self.assertIs(DEFAULT_DATABASE_FILE, core_config.DATABASE_FILE)
        self.assertIs(DEFAULT_SEED_FILE, core_config.CATALOG_SEED_FILE)
        self.assertIs(
            DEFAULT_SOURCE_REGISTRY_FILE,
            core_config.SOURCE_REGISTRY_FILE,
        )

    def test_app_import_is_independent_of_current_working_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self._run_from_other_directory(
                temp_dir,
                """
import os
from pathlib import Path

from app import app
from orbitai.core.config import (
    DATABASE_FILE,
    PROJECT_ROOT,
    STATIC_DIR,
    TEMPLATES_DIR,
)

expected_root = Path(os.environ["ORBITAI_EXPECTED_ROOT"])
assert PROJECT_ROOT == expected_root
assert DATABASE_FILE == expected_root / "orbitai.db"
assert STATIC_DIR == expected_root / "static"
assert TEMPLATES_DIR == expected_root / "templates"
assert any(route.path == "/industries/{industry_slug}" for route in app.routes)
""",
            )

        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_legacy_and_core_migration_clis_work_from_other_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_file = Path(temp_dir) / "cli.db"
            environment = self._subprocess_environment()

            for module_name in (
                "orbitai.migrations",
                "orbitai.core.migrations",
            ):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        module_name,
                        "status",
                        "--database",
                        str(database_file),
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

    def _run_from_other_directory(
        self,
        working_directory: str,
        code: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=working_directory,
            env=self._subprocess_environment(),
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def _subprocess_environment() -> dict[str, str]:
        environment = os.environ.copy()
        existing_pythonpath = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(
            value
            for value in (str(PROJECT_ROOT), existing_pythonpath)
            if value
        )
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["ORBITAI_EXPECTED_ROOT"] = str(PROJECT_ROOT)
        return environment


if __name__ == "__main__":
    unittest.main()
