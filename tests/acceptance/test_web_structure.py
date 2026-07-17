"""Web 路由、重定向与前端资源边界验收测试。"""

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
            ("GET", "/api/items"),
            ("GET", "/api/featured"),
            ("GET", "/api/daily"),
            ("GET", "/api/status"),
            ("GET", "/api/top"),
            ("GET", "/health"),
        }

        self.assertEqual(actual_routes, expected_routes)

    def test_canonical_material_pages_use_layered_assets(self):
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
                    self.assertIn('href="/materials"', response.text)
                    self.assertIn('href="/admin/status"', response.text)

    def test_admin_canonical_url_uses_admin_assets(self):
        response = self.client.get("/admin/status")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/static/shared/base.css", response.text)
        self.assertIn("/static/admin/style.css", response.text)
        self.assertIn("/static/admin/app.js", response.text)
        self.assertIn('href="/materials"', response.text)
        self.assertIn('href="/admin/status"', response.text)
        self.assertNotIn("/admin/regenerate", response.text)
        self.assertNotIn("重新生成静态 HTML", response.text)

    def test_root_and_legacy_urls_use_temporary_redirects(self):
        expected_redirects = {
            "/": "/industries/artificial-intelligence",
            "/index.html": "/materials",
            "/featured": "/materials/featured",
            "/featured.html": "/materials/featured",
            "/daily": "/materials/daily",
            "/daily.html": "/materials/daily",
            "/status": "/admin/status",
        }

        for path, target in expected_redirects.items():
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=False)
                self.assertEqual(response.status_code, 307)
                self.assertEqual(response.headers["location"], target)

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
