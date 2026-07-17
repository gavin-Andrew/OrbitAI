import unittest
from unittest.mock import patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from orbitai.web.app import create_app


class WebStructureTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_application_exposes_legacy_and_module_urls(self):
        actual_routes = {
            (method, route.path)
            for route in self.app.routes
            if isinstance(route, APIRoute)
            for method in route.methods
            if method in {"GET", "POST"}
        }
        expected_routes = {
            ("GET", "/"),
            ("GET", "/index.html"),
            ("GET", "/featured"),
            ("GET", "/featured.html"),
            ("GET", "/daily"),
            ("GET", "/daily.html"),
            ("GET", "/materials"),
            ("GET", "/materials/featured"),
            ("GET", "/materials/daily"),
            ("GET", "/industries/{industry_slug}"),
            ("GET", "/status"),
            ("GET", "/admin/status"),
            ("POST", "/admin/fetch"),
            ("POST", "/admin/process-ai"),
            ("POST", "/admin/regenerate"),
            ("GET", "/api/items"),
            ("GET", "/api/featured"),
            ("GET", "/api/daily"),
            ("GET", "/api/status"),
            ("GET", "/api/top"),
            ("GET", "/health"),
        }

        self.assertEqual(actual_routes, expected_routes)

    def test_material_pages_use_layered_assets_on_old_and_new_urls(self):
        status = {
            "version": "test",
            "today_count": 0,
            "high_score_count": 0,
        }
        with (
            patch(
                "orbitai.web.routes.materials.load_articles_from_db",
                return_value=[],
            ),
            patch(
                "orbitai.web.view_helpers.get_status_summary",
                return_value=status,
            ),
        ):
            for path in (
                "/",
                "/index.html",
                "/featured",
                "/featured.html",
                "/daily",
                "/daily.html",
                "/materials",
                "/materials/featured",
                "/materials/daily",
            ):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("/static/shared/base.css", response.text)
                    self.assertIn("/static/materials/style.css", response.text)
                    self.assertNotIn("/static/style.css", response.text)

    def test_admin_old_and_new_urls_use_admin_assets(self):
        for path in ("/status", "/admin/status"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("/static/shared/base.css", response.text)
                self.assertIn("/static/admin/style.css", response.text)
                self.assertIn("/static/admin/app.js", response.text)

    def test_static_assets_are_partitioned_by_page_boundary(self):
        for path in (
            "/static/shared/base.css",
            "/static/materials/style.css",
            "/static/materials/app.js",
            "/static/dossier/style.css",
            "/static/admin/style.css",
            "/static/admin/app.js",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

        self.assertEqual(self.client.get("/static/style.css").status_code, 404)
        self.assertEqual(self.client.get("/static/app.js").status_code, 404)


if __name__ == "__main__":
    unittest.main()
