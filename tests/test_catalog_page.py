import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from orbitai.catalog_import import apply_catalog_seed, load_json_document
from orbitai.catalog_service import load_industry_catalog
from orbitai.database import get_connection, init_db


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = PROJECT_ROOT / "data" / "catalog" / "foundation_models.v4.1.json"
SOURCE_REGISTRY_FILE = PROJECT_ROOT / "sources.v4.json"


class IndustryCatalogPageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_file = Path(self.temp_dir.name) / "catalog-page.db"
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

    def test_catalog_groups_all_26_segments_in_confirmed_order(self):
        catalog = load_industry_catalog(
            "artificial-intelligence",
            self.database_file,
        )

        self.assertIsNotNone(catalog)
        self.assertEqual(
            [group["name"] for group in catalog["groups"]],
            ["核心能力", "基础设施", "产品与应用", "外部环境"],
        )
        self.assertEqual(
            [group["segment_count"] for group in catalog["groups"]],
            [5, 6, 8, 7],
        )
        self.assertEqual(catalog["segment_count"], 26)
        self.assertEqual(catalog["built_count"], 1)
        self.assertEqual(catalog["pending_count"], 25)

    def test_built_status_comes_from_participant_relations_not_pilot_id(self):
        with get_connection(self.database_file) as connection:
            connection.execute("DELETE FROM organization_segments")
            connection.execute("DELETE FROM person_segments")
            connection.execute(
                """
                INSERT INTO organization_segments (
                    organization_id, segment_id, relationship_type
                ) VALUES ('openai', 'multimodal_understanding_generation', 'participant')
                """
            )
            connection.execute(
                """
                INSERT INTO person_segments (
                    person_id, segment_id, relationship_type
                ) VALUES ('sam_altman', 'multimodal_understanding_generation', 'participant')
                """
            )
            connection.commit()

        catalog = load_industry_catalog(
            "artificial-intelligence",
            self.database_file,
        )

        self.assertEqual(catalog["built_count"], 1)
        self.assertEqual(
            catalog["built_segments"][0]["id"],
            "multimodal_understanding_generation",
        )

    def test_catalog_page_renders_database_content(self):
        catalog = load_industry_catalog(
            "artificial-intelligence",
            self.database_file,
        )

        with (
            patch(
                "orbitai.web.routes.dossier.load_industry_catalog",
                return_value=catalog,
            ),
            patch(
                "orbitai.web.routes.dossier.get_status_summary",
                return_value={"version": "test"},
            ),
        ):
            response = TestClient(app).get(
                "/industries/artificial-intelligence"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("/static/shared/base.css", response.text)
        self.assertIn("/static/dossier/style.css", response.text)
        self.assertNotIn("/static/style.css", response.text)
        self.assertIn('href="/materials"', response.text)
        self.assertIn('href="/materials/featured"', response.text)
        self.assertIn('href="/admin/status"', response.text)
        for expected_text in (
            "核心能力",
            "基础设施",
            "产品与应用",
            "外部环境",
            "通用基础模型（含大语言模型）",
            "OpenAI",
            "Sam Altman",
            "待建设",
        ):
            self.assertIn(expected_text, response.text)

    def test_unknown_industry_returns_404(self):
        with patch(
            "orbitai.web.routes.dossier.load_industry_catalog",
            return_value=None,
        ):
            response = TestClient(app).get("/industries/not-found")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
