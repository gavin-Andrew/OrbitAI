"""Web 路由、重定向与前端资源边界验收测试。"""

import unittest
from unittest.mock import patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from orbitai.catalog.edit_service import (
    CatalogEditConflict,
    CatalogEditValidationError,
)
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
            ("GET", "/organizations"),
            ("GET", "/people"),
            ("GET", "/segments/{segment_slug}"),
            ("GET", "/status"),
            ("GET", "/admin/status"),
            ("GET", "/admin/catalog"),
            ("POST", "/admin/catalog/preview"),
            ("POST", "/admin/catalog/save"),
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
        self.assertIn('href="/admin/catalog"', response.text)
        self.assertNotIn("/admin/regenerate", response.text)
        self.assertNotIn("重新生成静态 HTML", response.text)

    def test_catalog_admin_is_independent_and_uses_dedicated_assets(self):
        editor_data = {
            "entities": [],
            "organization_count": 6,
            "person_count": 6,
            "change_log": [],
            "options": {
                "organization_types": [],
                "statuses": {"organization": [], "person": []},
            },
        }
        with patch(
            "orbitai.web.routes.admin.load_catalog_management_data",
            return_value=editor_data,
        ):
            response = self.client.get("/admin/catalog")

        html = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/static/admin/catalog.css", html)
        self.assertIn("/static/admin/catalog_editor.js", html)
        self.assertNotIn("/static/materials/style.css", html)
        self.assertIn("产业与参与者名册管理", html)
        self.assertIn("1. 预览修改", html)
        self.assertIn("2. 确认并保存", html)

    def test_catalog_admin_api_exposes_preview_validation_and_conflict_statuses(self):
        with patch(
            "orbitai.web.routes.admin.preview_catalog_edit",
            return_value={"has_changes": True, "changes": {"name": {}}},
        ):
            preview_response = self.client.post(
                "/admin/catalog/preview",
                json={"example": True},
            )

        with patch(
            "orbitai.web.routes.admin.preview_catalog_edit",
            side_effect=CatalogEditValidationError(["名称不能为空。"]),
        ):
            validation_response = self.client.post(
                "/admin/catalog/preview",
                json={"example": True},
            )

        current = {"entity_id": "openai", "revision": "newer"}
        with patch(
            "orbitai.web.routes.admin.save_catalog_edit",
            side_effect=CatalogEditConflict(current),
        ):
            conflict_response = self.client.post(
                "/admin/catalog/save",
                json={"example": True},
            )

        self.assertEqual(preview_response.status_code, 200)
        self.assertTrue(preview_response.json()["ok"])
        self.assertEqual(validation_response.status_code, 422)
        self.assertEqual(validation_response.json()["error_type"], "validation")
        self.assertEqual(conflict_response.status_code, 409)
        self.assertEqual(conflict_response.json()["current"], current)

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
            "/static/admin/catalog.css",
            "/static/admin/catalog_editor.js",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

        self.assertEqual(self.client.get("/static/style.css").status_code, 404)
        self.assertEqual(self.client.get("/static/app.js").status_code, 404)


if __name__ == "__main__":
    unittest.main()
