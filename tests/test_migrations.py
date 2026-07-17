import sqlite3
import tempfile
import unittest
from pathlib import Path

from orbitai.database import get_connection, init_db
from orbitai.migrations import (
    apply_migrations,
    get_applied_migrations,
    rollback_last_migration,
)


EXPECTED_V4_TABLES = {
    "industries",
    "segments",
    "industry_segments",
    "segment_relation_types",
    "segment_relations",
    "organizations",
    "organization_aliases",
    "people",
    "person_aliases",
    "person_organization_roles",
    "organization_segments",
    "person_segments",
    "event_types",
    "events",
    "event_segments",
    "event_organizations",
    "event_people",
    "sources",
    "source_entries",
    "documents",
    "event_documents",
}


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_file = Path(self.temp_dir.name) / "test.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fresh_database_applies_all_migrations_once(self):
        self.assertEqual(
            init_db(self.database_file),
            ["0001", "0002", "0003", "0004", "0005"],
        )
        self.assertEqual(init_db(self.database_file), [])

        with get_connection(self.database_file) as connection:
            table_names = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            applied = get_applied_migrations(connection)

        self.assertIn("articles", table_names)
        self.assertTrue(EXPECTED_V4_TABLES.issubset(table_names))
        self.assertEqual(
            [item["version"] for item in applied],
            ["0001", "0002", "0003", "0004", "0005"],
        )

    def test_catalog_lookup_indexes_are_created(self):
        init_db(self.database_file)

        with get_connection(self.database_file) as connection:
            index_names = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }

        self.assertTrue(
            {
                "idx_organizations_name_nocase",
                "idx_organization_aliases_alias_nocase",
                "idx_people_name_nocase",
                "idx_person_aliases_alias_nocase",
                "idx_organization_segments_segment_id",
                "idx_person_segments_segment_id",
                "idx_sources_organization_id",
                "idx_sources_person_id",
            }.issubset(index_names)
        )

    def test_confirmed_event_type_rules_are_seeded(self):
        init_db(self.database_file)

        with get_connection(self.database_file) as connection:
            rows = connection.execute(
                """
                SELECT id, name, description
                FROM event_types
                ORDER BY id
                """
            ).fetchall()

        event_types = {
            row["id"]: {
                "name": row["name"],
                "description": row["description"],
            }
            for row in rows
        }

        self.assertEqual(len(event_types), 12)
        self.assertEqual(
            event_types["model_release"]["name"],
            "模型发布与重大更新",
        )
        self.assertEqual(
            event_types["corporate_action"]["name"],
            "组织结构变动",
        )
        self.assertEqual(
            event_types["infrastructure"]["name"],
            "基础设施建设与扩容",
        )
        self.assertTrue(
            all(item["description"] for item in event_types.values())
        )

    def test_legacy_articles_are_preserved_and_upgraded(self):
        with sqlite3.connect(self.database_file) as connection:
            connection.execute(
                """
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    link TEXT UNIQUE
                )
                """
            )
            connection.execute(
                "INSERT INTO articles (title, link) VALUES (?, ?)",
                ("旧文章", "https://example.com/legacy"),
            )

        init_db(self.database_file)

        with get_connection(self.database_file) as connection:
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(articles)"
                ).fetchall()
            }
            article = connection.execute(
                "SELECT title, link FROM articles"
            ).fetchone()

        self.assertIn("scores", columns)
        self.assertIn("processed_at", columns)
        self.assertEqual(article["title"], "旧文章")
        self.assertEqual(article["link"], "https://example.com/legacy")

    def test_segment_kinds_upgrade_to_confirmed_four_groups(self):
        with get_connection(
            self.database_file,
            allow_create=True,
        ) as connection:
            self.assertEqual(
                apply_migrations(connection, target_version="0003"),
                ["0001", "0002", "0003"],
            )
            connection.execute(
                """
                INSERT INTO industries (id, name, slug)
                VALUES ('ai', '人工智能产业', 'ai')
                """
            )
            connection.executemany(
                """
                INSERT INTO segments (id, name, slug, segment_kind)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (
                        "foundation_models",
                        "通用基础模型",
                        "foundation-models",
                        "capability_product",
                    ),
                    (
                        "ai_chips",
                        "AI 芯片",
                        "ai-chips",
                        "support_system",
                    ),
                    (
                        "policy_regulation",
                        "政策与监管",
                        "policy-regulation",
                        "external_environment",
                    ),
                ),
            )
            connection.executemany(
                """
                INSERT INTO industry_segments (industry_id, segment_id)
                VALUES ('ai', ?)
                """,
                (
                    ("foundation_models",),
                    ("ai_chips",),
                    ("policy_regulation",),
                ),
            )
            connection.execute(
                """
                INSERT INTO segment_relations (
                    source_segment_id, target_segment_id, relation_type_id
                ) VALUES ('foundation_models', 'ai_chips', 'depends_on')
                """
            )
            connection.execute(
                """
                INSERT INTO organizations (id, name)
                VALUES ('example_lab', '示例实验室')
                """
            )
            connection.execute(
                """
                INSERT INTO organization_segments (organization_id, segment_id)
                VALUES ('example_lab', 'foundation_models')
                """
            )
            connection.execute(
                """
                INSERT INTO people (id, name)
                VALUES ('example_person', '示例人物')
                """
            )
            connection.execute(
                """
                INSERT INTO person_segments (person_id, segment_id)
                VALUES ('example_person', 'foundation_models')
                """
            )
            connection.execute(
                """
                INSERT INTO events (id, title)
                VALUES ('example_event', '示例事件')
                """
            )
            connection.execute(
                """
                INSERT INTO event_segments (event_id, segment_id)
                VALUES ('example_event', 'foundation_models')
                """
            )

            self.assertEqual(
                apply_migrations(connection, target_version="0004"),
                ["0004"],
            )
            connection.execute(
                """
                INSERT INTO segments (id, name, slug, segment_kind)
                VALUES (
                    'ai_agents', 'AI Agent 与软件自动化',
                    'ai-agents', 'product_application'
                )
                """
            )
            rows = connection.execute(
                """
                SELECT id, segment_kind
                FROM segments
                ORDER BY id
                """
            ).fetchall()
            linked_segment_ids = {
                row["segment_id"]
                for row in connection.execute(
                    "SELECT segment_id FROM industry_segments"
                ).fetchall()
            }
            dependent_counts = {
                table_name: connection.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                for table_name in (
                    "industry_segments",
                    "segment_relations",
                    "organization_segments",
                    "person_segments",
                    "event_segments",
                )
            }

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO segments (id, name, slug, segment_kind)
                    VALUES (
                        'legacy_kind', '旧分组',
                        'legacy-kind', 'capability_product'
                    )
                    """
                )

            foreign_key_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            self.assertEqual(
                rollback_last_migration(
                    connection,
                    allow_destructive=True,
                ),
                "0004",
            )
            rolled_back_kinds = {
                row["id"]: row["segment_kind"]
                for row in connection.execute(
                    "SELECT id, segment_kind FROM segments"
                ).fetchall()
            }
            rollback_foreign_key_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            rollback_dependent_counts = {
                table_name: connection.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                for table_name in dependent_counts
            }

        segment_kinds = {row["id"]: row["segment_kind"] for row in rows}
        self.assertEqual(
            segment_kinds,
            {
                "ai_agents": "product_application",
                "ai_chips": "infrastructure",
                "foundation_models": "core_capability",
                "policy_regulation": "external_environment",
            },
        )
        self.assertEqual(
            linked_segment_ids,
            {"foundation_models", "ai_chips", "policy_regulation"},
        )
        self.assertEqual(
            dependent_counts,
            {
                "industry_segments": 3,
                "segment_relations": 1,
                "organization_segments": 1,
                "person_segments": 1,
                "event_segments": 1,
            },
        )
        self.assertEqual(foreign_key_errors, [])
        self.assertEqual(
            rolled_back_kinds,
            {
                "ai_agents": "capability_product",
                "ai_chips": "support_system",
                "foundation_models": "capability_product",
                "policy_regulation": "external_environment",
            },
        )
        self.assertEqual(rollback_foreign_key_errors, [])
        self.assertEqual(rollback_dependent_counts, dependent_counts)

    def test_core_schema_supports_traceable_event_path(self):
        init_db(self.database_file)

        with get_connection(self.database_file) as connection:
            connection.execute(
                """
                INSERT INTO industries (id, name, slug)
                VALUES ('ai', '人工智能产业', 'ai')
                """
            )
            connection.execute(
                """
                INSERT INTO segments (id, name, slug, segment_kind)
                VALUES ('foundation_models', '基础模型与 LLM',
                        'foundation-models', 'core_capability')
                """
            )
            connection.execute(
                """
                INSERT INTO industry_segments (industry_id, segment_id)
                VALUES ('ai', 'foundation_models')
                """
            )
            connection.execute(
                """
                INSERT INTO organizations (id, name, organization_type)
                VALUES ('example_lab', '示例实验室', 'research_lab')
                """
            )
            connection.execute(
                """
                INSERT INTO organization_segments (organization_id, segment_id)
                VALUES ('example_lab', 'foundation_models')
                """
            )
            connection.execute(
                """
                INSERT INTO events (
                    id, title, event_type_id, status,
                    date_start, date_precision, origin, confirmed_by_user
                ) VALUES (
                    'example_event', '示例模型发布', 'model_release', 'confirmed',
                    '2026-07-10', 'day', 'user', 1
                )
                """
            )
            connection.execute(
                """
                INSERT INTO event_segments (event_id, segment_id)
                VALUES ('example_event', 'foundation_models')
                """
            )
            connection.execute(
                """
                INSERT INTO event_organizations (event_id, organization_id)
                VALUES ('example_event', 'example_lab')
                """
            )
            connection.execute(
                """
                INSERT INTO sources (
                    id, name, source_type, organization_id, tier
                ) VALUES (
                    'example_lab_source', '示例实验室官网',
                    'organization', 'example_lab', 'core'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO documents (
                    id, source_id, document_type, title, url, origin
                ) VALUES (
                    'example_document', 'example_lab_source', 'announcement',
                    '示例公告', 'https://example.com/announcement', 'user'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO event_documents (
                    event_id, document_id, evidence_role, is_primary
                ) VALUES (
                    'example_event', 'example_document', 'official', 1
                )
                """
            )

            trace = connection.execute(
                """
                SELECT
                    industries.name AS industry_name,
                    segments.name AS segment_name,
                    organizations.name AS organization_name,
                    events.title AS event_title,
                    documents.url AS document_url
                FROM industries
                JOIN industry_segments
                    ON industry_segments.industry_id = industries.id
                JOIN segments
                    ON segments.id = industry_segments.segment_id
                JOIN event_segments
                    ON event_segments.segment_id = segments.id
                JOIN events
                    ON events.id = event_segments.event_id
                JOIN event_organizations
                    ON event_organizations.event_id = events.id
                JOIN organizations
                    ON organizations.id = event_organizations.organization_id
                JOIN event_documents
                    ON event_documents.event_id = events.id
                JOIN documents
                    ON documents.id = event_documents.document_id
                WHERE industries.id = 'ai'
                """
            ).fetchone()

        self.assertEqual(trace["industry_name"], "人工智能产业")
        self.assertEqual(trace["segment_name"], "基础模型与 LLM")
        self.assertEqual(trace["organization_name"], "示例实验室")
        self.assertEqual(trace["event_title"], "示例模型发布")
        self.assertEqual(
            trace["document_url"],
            "https://example.com/announcement",
        )

    def test_ai_event_cannot_be_confirmed_without_user_confirmation(self):
        init_db(self.database_file)

        with get_connection(self.database_file) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO events (
                        id, title, status, origin, confirmed_by_user
                    ) VALUES (
                        'ai_event', 'AI 候选事件', 'confirmed', 'ai', 0
                    )
                    """
                )

    def test_destructive_rollback_requires_explicit_permission(self):
        init_db(self.database_file)

        with get_connection(self.database_file) as connection:
            self.assertEqual(
                rollback_last_migration(connection),
                "0005",
            )
            with self.assertRaises(RuntimeError):
                rollback_last_migration(connection)

            self.assertEqual(
                rollback_last_migration(
                    connection,
                    allow_destructive=True,
                ),
                "0004",
            )
            self.assertEqual(
                rollback_last_migration(connection),
                "0003",
            )

            with self.assertRaises(RuntimeError):
                rollback_last_migration(connection)

            version = rollback_last_migration(
                connection,
                allow_destructive=True,
            )
            remaining_tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            applied_versions = [
                item["version"]
                for item in get_applied_migrations(connection)
            ]

        self.assertEqual(version, "0002")
        self.assertIn("articles", remaining_tables)
        self.assertNotIn("events", remaining_tables)
        self.assertEqual(applied_versions, ["0001"])


if __name__ == "__main__":
    unittest.main()
