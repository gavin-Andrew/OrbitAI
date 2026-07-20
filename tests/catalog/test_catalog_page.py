"""产业目录服务与动态页面测试。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from orbitai.catalog.import_service import apply_catalog_seed, load_json_document
from orbitai.catalog.service import (
    load_industry_catalog,
    load_organization_directory,
    load_person_directory,
    load_segment_profile,
)
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

        with patch(
            "orbitai.web.routes.dossier.load_industry_catalog",
            return_value=catalog,
        ):
            response = TestClient(app).get(
                "/industries/artificial-intelligence"
            )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("/static/shared/base.css", html)
        self.assertIn("/static/dossier/style.css", html)
        self.assertNotIn("/static/style.css", html)
        self.assertIn("/industries/artificial-intelligence", html)
        self.assertIn("/organizations", html)
        self.assertIn("/people", html)
        self.assertNotIn('href="/materials"', html)
        self.assertNotIn('href="/admin/status"', html)
        self.assertIn(
            "/segments/general-foundation-models",
            html,
        )
        for expected_text in (
            "核心能力",
            "基础设施",
            "产品与应用",
            "外部环境",
            "通用基础模型（含大语言模型）",
            "内容待建设",
        ):
            self.assertIn(expected_text, html)

    def test_directory_services_read_seeded_organizations_people_and_roles(self):
        organizations = load_organization_directory(self.database_file)
        people = load_person_directory(self.database_file)

        self.assertEqual(organizations["organization_count"], 6)
        self.assertEqual(people["person_count"], 6)
        self.assertIn(
            "OpenAI",
            [item["name"] for item in organizations["organizations"]],
        )
        openai = next(
            item
            for item in organizations["organizations"]
            if item["name"] == "OpenAI"
        )
        self.assertEqual(openai["type_label"], "AI 企业")
        sam_altman = next(
            item for item in people["people"] if item["name"] == "Sam Altman"
        )
        self.assertEqual(sam_altman["current_roles"][0]["organization_name"], "OpenAI")
        self.assertTrue(sam_altman["current_roles"][0]["role_title"])

    def test_segment_profile_contains_real_pilot_roster(self):
        profile = load_segment_profile(
            "general-foundation-models",
            self.database_file,
        )

        self.assertIsNotNone(profile)
        self.assertTrue(profile["segment"]["is_built"])
        self.assertEqual(len(profile["organizations"]), 6)
        self.assertEqual(len(profile["people"]), 6)
        self.assertEqual(profile["participant_count"], 12)
        self.assertEqual(profile["segment"]["industry_slug"], "artificial-intelligence")

    def test_three_entry_pages_and_segment_page_render_real_data(self):
        organizations = load_organization_directory(self.database_file)
        people = load_person_directory(self.database_file)
        profile = load_segment_profile(
            "general-foundation-models",
            self.database_file,
        )

        client = TestClient(app)
        with (
            patch(
                "orbitai.web.routes.dossier.load_organization_directory",
                return_value=organizations,
            ),
            patch(
                "orbitai.web.routes.dossier.load_person_directory",
                return_value=people,
            ),
            patch(
                "orbitai.web.routes.dossier.load_segment_profile",
                return_value=profile,
            ),
        ):
            organization_response = client.get("/organizations")
            people_response = client.get("/people")
            segment_response = client.get(
                "/segments/general-foundation-models"
            )

        self.assertEqual(organization_response.status_code, 200)
        self.assertEqual(people_response.status_code, 200)
        self.assertEqual(segment_response.status_code, 200)
        self.assertIn("OpenAI", organization_response.content.decode("utf-8"))
        self.assertIn("Sam Altman", people_response.content.decode("utf-8"))
        segment_html = segment_response.content.decode("utf-8")
        self.assertIn("等待 V4.2 事件台账", segment_html)
        self.assertIn("OpenAI", segment_html)
        self.assertIn("Sam Altman", segment_html)

    def test_unknown_industry_returns_404(self):
        with patch(
            "orbitai.web.routes.dossier.load_industry_catalog",
            return_value=None,
        ):
            response = TestClient(app).get("/industries/not-found")

        self.assertEqual(response.status_code, 404)

    def test_unknown_segment_returns_404(self):
        with patch(
            "orbitai.web.routes.dossier.load_segment_profile",
            return_value=None,
        ):
            response = TestClient(app).get("/segments/not-found")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
