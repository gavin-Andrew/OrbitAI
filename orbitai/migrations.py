"""OrbitAI 的轻量 SQLite 数据库迁移机制。"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


MigrationAction = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    """一条按版本顺序执行的数据库迁移。"""

    version: str
    name: str
    up: MigrationAction
    down: MigrationAction | None = None
    destructive_down: bool = False


def _execute_statements(
    connection: sqlite3.Connection,
    statements: tuple[str, ...],
) -> None:
    for statement in statements:
        connection.execute(statement)


def _create_articles_baseline(connection: sqlite3.Connection) -> None:
    """建立文章表，并兼容 V3 早期缺少字段的数据库。"""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            title_cn TEXT,
            source TEXT,
            link TEXT UNIQUE,
            published TEXT,
            fetched_at TEXT,
            summary_original TEXT,
            summary_cn TEXT,
            category_rule TEXT,
            ai_category TEXT,
            tags TEXT,
            scores TEXT,
            final_score REAL,
            processed INTEGER DEFAULT 0,
            processed_at TEXT,
            error TEXT,
            error_type TEXT,
            failed_at TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(articles)").fetchall()
    }
    required_columns = {
        "title_cn": "TEXT",
        "summary_cn": "TEXT",
        "ai_category": "TEXT",
        "tags": "TEXT",
        "scores": "TEXT",
        "final_score": "REAL",
        "processed": "INTEGER DEFAULT 0",
        "processed_at": "TEXT",
        "error": "TEXT",
        "error_type": "TEXT",
        "failed_at": "TEXT",
        "retry_count": "INTEGER DEFAULT 0",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            connection.execute(
                f"ALTER TABLE articles ADD COLUMN {column_name} {column_type}"
            )


V4_CORE_SCHEMA_UP = (
    """
    CREATE TABLE industries (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'archived')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE segments (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        segment_kind TEXT NOT NULL
            CHECK (segment_kind IN (
                'capability_product',
                'support_system',
                'external_environment'
            )),
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'archived')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE industry_segments (
        industry_id TEXT NOT NULL REFERENCES industries(id) ON DELETE CASCADE,
        segment_id TEXT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
        relationship_type TEXT NOT NULL DEFAULT 'contains'
            CHECK (relationship_type IN ('contains', 'supports', 'influences')),
        is_primary INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0, 1)),
        notes TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (industry_id, segment_id)
    )
    """,
    """
    CREATE TABLE segment_relation_types (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        is_directional INTEGER NOT NULL DEFAULT 1
            CHECK (is_directional IN (0, 1))
    )
    """,
    """
    CREATE TABLE segment_relations (
        source_segment_id TEXT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
        target_segment_id TEXT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
        relation_type_id TEXT NOT NULL REFERENCES segment_relation_types(id),
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (source_segment_id, target_segment_id, relation_type_id),
        CHECK (source_segment_id != target_segment_id)
    )
    """,
    """
    CREATE TABLE organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        organization_type TEXT NOT NULL DEFAULT 'company',
        homepage_url TEXT,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive', 'acquired', 'closed', 'archived')),
        founded_on TEXT,
        ended_on TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE organization_aliases (
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        alias TEXT NOT NULL COLLATE NOCASE,
        PRIMARY KEY (organization_id, alias)
    )
    """,
    """
    CREATE TABLE people (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive', 'archived')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE person_aliases (
        person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        alias TEXT NOT NULL COLLATE NOCASE,
        PRIMARY KEY (person_id, alias)
    )
    """,
    """
    CREATE TABLE person_organization_roles (
        person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        role_title TEXT NOT NULL,
        started_on TEXT NOT NULL DEFAULT '',
        ended_on TEXT,
        is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
        notes TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (person_id, organization_id, role_title, started_on)
    )
    """,
    """
    CREATE TABLE organization_segments (
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        segment_id TEXT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
        relationship_type TEXT NOT NULL DEFAULT 'participant',
        notes TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (organization_id, segment_id, relationship_type)
    )
    """,
    """
    CREATE TABLE person_segments (
        person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        segment_id TEXT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
        relationship_type TEXT NOT NULL DEFAULT 'participant',
        notes TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (person_id, segment_id, relationship_type)
    )
    """,
    """
    CREATE TABLE event_types (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE events (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        event_type_id TEXT NOT NULL DEFAULT 'other' REFERENCES event_types(id),
        status TEXT NOT NULL DEFAULT 'candidate'
            CHECK (status IN (
                'candidate',
                'confirmed',
                'disputed',
                'needs_evidence',
                'archived'
            )),
        date_start TEXT,
        date_end TEXT,
        date_precision TEXT NOT NULL DEFAULT 'unknown'
            CHECK (date_precision IN (
                'day', 'month', 'quarter', 'year', 'range', 'unknown'
            )),
        origin TEXT NOT NULL DEFAULT 'user'
            CHECK (origin IN ('user', 'ai', 'import')),
        confirmed_by_user INTEGER NOT NULL DEFAULT 0
            CHECK (confirmed_by_user IN (0, 1)),
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK (
            origin != 'ai'
            OR status != 'confirmed'
            OR confirmed_by_user = 1
        )
    )
    """,
    """
    CREATE TABLE event_segments (
        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        segment_id TEXT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
        relationship_type TEXT NOT NULL DEFAULT 'primary',
        notes TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (event_id, segment_id, relationship_type)
    )
    """,
    """
    CREATE TABLE event_organizations (
        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        role TEXT NOT NULL DEFAULT 'participant',
        notes TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (event_id, organization_id, role)
    )
    """,
    """
    CREATE TABLE event_people (
        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        role TEXT NOT NULL DEFAULT 'participant',
        notes TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (event_id, person_id, role)
    )
    """,
    """
    CREATE TABLE sources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        tier TEXT NOT NULL DEFAULT 'watched'
            CHECK (tier IN ('core', 'watched', 'reference', 'archived')),
        organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
        person_id TEXT REFERENCES people(id) ON DELETE SET NULL,
        tracking_reason TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK (organization_id IS NULL OR person_id IS NULL)
    )
    """,
    """
    CREATE TABLE source_entries (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
        entry_type TEXT NOT NULL
            CHECK (entry_type IN (
                'rss', 'website', 'api', 'youtube', 'podcast', 'manual', 'other'
            )),
        label TEXT NOT NULL,
        url TEXT,
        status TEXT NOT NULL DEFAULT 'planned'
            CHECK (status IN ('enabled', 'planned', 'disabled', 'archived')),
        existing_in_sources_json INTEGER NOT NULL DEFAULT 0
            CHECK (existing_in_sources_json IN (0, 1)),
        notes TEXT NOT NULL DEFAULT '',
        UNIQUE (source_id, entry_type, url)
    )
    """,
    """
    CREATE TABLE documents (
        id TEXT PRIMARY KEY,
        source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
        article_id INTEGER UNIQUE REFERENCES articles(id) ON DELETE SET NULL,
        document_type TEXT NOT NULL DEFAULT 'article',
        title TEXT NOT NULL,
        url TEXT UNIQUE,
        published_at TEXT,
        content_text TEXT,
        origin TEXT NOT NULL DEFAULT 'user'
            CHECK (origin IN ('user', 'import', 'ai')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE event_documents (
        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        evidence_role TEXT NOT NULL DEFAULT 'background'
            CHECK (evidence_role IN (
                'official',
                'independent',
                'expert',
                'user_feedback',
                'background'
            )),
        is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
        notes TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (event_id, document_id)
    )
    """,
    "CREATE INDEX idx_events_date_start ON events(date_start)",
    "CREATE INDEX idx_events_status ON events(status)",
    "CREATE INDEX idx_documents_article_id ON documents(article_id)",
    "CREATE INDEX idx_event_segments_segment_id ON event_segments(segment_id)",
    "CREATE INDEX idx_event_organizations_org_id ON event_organizations(organization_id)",
    "CREATE INDEX idx_event_people_person_id ON event_people(person_id)",
)


V4_CORE_SCHEMA_DOWN = (
    "DROP TABLE IF EXISTS event_documents",
    "DROP TABLE IF EXISTS documents",
    "DROP TABLE IF EXISTS source_entries",
    "DROP TABLE IF EXISTS sources",
    "DROP TABLE IF EXISTS event_people",
    "DROP TABLE IF EXISTS event_organizations",
    "DROP TABLE IF EXISTS event_segments",
    "DROP TABLE IF EXISTS events",
    "DROP TABLE IF EXISTS event_types",
    "DROP TABLE IF EXISTS person_segments",
    "DROP TABLE IF EXISTS organization_segments",
    "DROP TABLE IF EXISTS person_organization_roles",
    "DROP TABLE IF EXISTS person_aliases",
    "DROP TABLE IF EXISTS people",
    "DROP TABLE IF EXISTS organization_aliases",
    "DROP TABLE IF EXISTS organizations",
    "DROP TABLE IF EXISTS segment_relations",
    "DROP TABLE IF EXISTS segment_relation_types",
    "DROP TABLE IF EXISTS industry_segments",
    "DROP TABLE IF EXISTS segments",
    "DROP TABLE IF EXISTS industries",
)


SEGMENT_RELATION_TYPES = (
    ("supports", "支持", 1),
    ("depends_on", "依赖", 1),
    ("supplies", "供应", 1),
    ("adopts", "采用", 1),
    ("competes_with", "竞争", 0),
    ("substitutes", "替代", 1),
    ("collaborates_with", "合作", 0),
    ("regulates", "监管", 1),
    ("influences", "影响", 1),
)


EVENT_TYPES = (
    ("model_release", "模型发布"),
    ("product_release", "产品发布"),
    ("research_result", "研究成果"),
    ("corporate_action", "公司行动"),
    ("partnership", "合作"),
    ("funding", "融资"),
    ("infrastructure", "基础设施"),
    ("policy_regulation", "政策与监管"),
    ("leadership_change", "管理层变动"),
    ("adoption", "采用与落地"),
    ("incident", "事故与争议"),
    ("other", "其他"),
)


EVENT_TYPE_RULES_V1 = (
    (
        "model_release",
        "模型发布与重大更新",
        "以命名模型首次发布、开放使用或重大版本升级为核心；"
        "不含仅使用既有模型的产品功能和仅发表论文的研究结果。",
    ),
    (
        "product_release",
        "产品发布与重大更新",
        "以面向用户或开发者的 AI 产品、服务、工具或重大功能正式上线为核心；"
        "不含底层模型本身发布。",
    ),
    (
        "research_result",
        "研究成果发布",
        "以新研究方法、实验、评测或科学发现正式公开为核心；"
        "若公开可用模型是主体则优先选择模型发布与重大更新。",
    ),
    (
        "corporate_action",
        "组织结构变动",
        "以组织成立、合并收购、拆分、重组、更名或关闭等结构性变化为核心；"
        "不含融资、合作和关键人物任免。",
    ),
    (
        "partnership",
        "合作",
        "以两个或更多组织正式建立联合开发、授权、供应、分销或战略合作为核心；"
        "单方实际使用归为采用与落地。",
    ),
    (
        "funding",
        "融资",
        "以企业、机构或项目获得股权、债务、战略投资、资助或上市融资为核心；"
        "不含收购和无实际交易的估值传闻。",
    ),
    (
        "infrastructure",
        "基础设施建设与扩容",
        "以算力集群、数据中心、网络、电力或冷却设施建设、投运或显著扩容为核心；"
        "不含仅发布硬件产品或仅签署合作。",
    ),
    (
        "policy_regulation",
        "政策与监管",
        "以政府、监管机构、法院或标准组织提出、通过、执行、调查、处罚"
        "或发布正式规则和标准为核心。",
    ),
    (
        "leadership_change",
        "管理层变动",
        "以对组织或赛道有显著影响的关键人物任命、离职、解职或职务变化为核心；"
        "不含普通人员变动。",
    ),
    (
        "adoption",
        "采用与落地",
        "以明确客户、组织或行业实际选择、部署、集成或扩大使用模型或 AI 产品为核心；"
        "不含仅宣布可用或仅表达使用意向。",
    ),
    (
        "incident",
        "事故与重大争议",
        "以可追溯的服务中断、安全隐私失效、严重滥用、造假撤回"
        "或有具体触发点的重大争议为核心；不含一般批评。",
    ),
    (
        "other",
        "其他",
        "仅用于符合事件粒度但无法归入其他类型的事件；"
        "必须说明原因并建议是否新增类型。",
    ),
)


def _create_v4_core_schema(connection: sqlite3.Connection) -> None:
    _execute_statements(connection, V4_CORE_SCHEMA_UP)
    connection.executemany(
        """
        INSERT INTO segment_relation_types (id, name, is_directional)
        VALUES (?, ?, ?)
        """,
        SEGMENT_RELATION_TYPES,
    )
    connection.executemany(
        "INSERT INTO event_types (id, name) VALUES (?, ?)",
        EVENT_TYPES,
    )


def _drop_v4_core_schema(connection: sqlite3.Connection) -> None:
    _execute_statements(connection, V4_CORE_SCHEMA_DOWN)


def _apply_event_type_rules_v1(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT INTO event_types (id, name, description)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description
        """,
        EVENT_TYPE_RULES_V1,
    )


def _rollback_event_type_rules_v1(connection: sqlite3.Connection) -> None:
    previous_names = {
        event_type_id: name
        for event_type_id, name in EVENT_TYPES
    }
    connection.executemany(
        """
        UPDATE event_types
        SET name = ?, description = ''
        WHERE id = ?
        """,
        (
            (previous_names[event_type_id], event_type_id)
            for event_type_id, _, _ in EVENT_TYPE_RULES_V1
        ),
    )


SEGMENT_KINDS_V1 = (
    "core_capability",
    "infrastructure",
    "product_application",
    "external_environment",
)


def _rebuild_segments_with_kinds(
    connection: sqlite3.Connection,
    *,
    suffix: str,
    allowed_kinds: tuple[str, ...],
    kind_expression: str,
) -> None:
    """在保留赛道及其关联数据的前提下重建 segment_kind 约束。"""

    segments_table = f"segments_{suffix}"
    industry_segments_table = f"industry_segments_{suffix}"
    segment_relations_table = f"segment_relations_{suffix}"
    organization_segments_table = f"organization_segments_{suffix}"
    person_segments_table = f"person_segments_{suffix}"
    event_segments_table = f"event_segments_{suffix}"
    allowed_values = ", ".join(f"'{item}'" for item in allowed_kinds)

    connection.execute(
        f"""
        CREATE TABLE {segments_table} (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            segment_kind TEXT NOT NULL
                CHECK (segment_kind IN ({allowed_values})),
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'archived')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO {segments_table} (
            id, name, slug, segment_kind, description,
            status, created_at, updated_at
        )
        SELECT
            id, name, slug, {kind_expression}, description,
            status, created_at, updated_at
        FROM segments
        """
    )

    connection.execute(
        f"""
        CREATE TABLE {industry_segments_table} (
            industry_id TEXT NOT NULL
                REFERENCES industries(id) ON DELETE CASCADE,
            segment_id TEXT NOT NULL
                REFERENCES {segments_table}(id) ON DELETE CASCADE,
            relationship_type TEXT NOT NULL DEFAULT 'contains'
                CHECK (relationship_type IN ('contains', 'supports', 'influences')),
            is_primary INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0, 1)),
            notes TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (industry_id, segment_id)
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO {industry_segments_table} (
            industry_id, segment_id, relationship_type, is_primary, notes
        )
        SELECT industry_id, segment_id, relationship_type, is_primary, notes
        FROM industry_segments
        """
    )

    connection.execute(
        f"""
        CREATE TABLE {segment_relations_table} (
            source_segment_id TEXT NOT NULL
                REFERENCES {segments_table}(id) ON DELETE CASCADE,
            target_segment_id TEXT NOT NULL
                REFERENCES {segments_table}(id) ON DELETE CASCADE,
            relation_type_id TEXT NOT NULL REFERENCES segment_relation_types(id),
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source_segment_id, target_segment_id, relation_type_id),
            CHECK (source_segment_id != target_segment_id)
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO {segment_relations_table} (
            source_segment_id, target_segment_id,
            relation_type_id, notes, created_at
        )
        SELECT
            source_segment_id, target_segment_id,
            relation_type_id, notes, created_at
        FROM segment_relations
        """
    )

    connection.execute(
        f"""
        CREATE TABLE {organization_segments_table} (
            organization_id TEXT NOT NULL
                REFERENCES organizations(id) ON DELETE CASCADE,
            segment_id TEXT NOT NULL
                REFERENCES {segments_table}(id) ON DELETE CASCADE,
            relationship_type TEXT NOT NULL DEFAULT 'participant',
            notes TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (organization_id, segment_id, relationship_type)
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO {organization_segments_table} (
            organization_id, segment_id, relationship_type, notes
        )
        SELECT organization_id, segment_id, relationship_type, notes
        FROM organization_segments
        """
    )

    connection.execute(
        f"""
        CREATE TABLE {person_segments_table} (
            person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
            segment_id TEXT NOT NULL
                REFERENCES {segments_table}(id) ON DELETE CASCADE,
            relationship_type TEXT NOT NULL DEFAULT 'participant',
            notes TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (person_id, segment_id, relationship_type)
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO {person_segments_table} (
            person_id, segment_id, relationship_type, notes
        )
        SELECT person_id, segment_id, relationship_type, notes
        FROM person_segments
        """
    )

    connection.execute(
        f"""
        CREATE TABLE {event_segments_table} (
            event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            segment_id TEXT NOT NULL
                REFERENCES {segments_table}(id) ON DELETE CASCADE,
            relationship_type TEXT NOT NULL DEFAULT 'primary',
            notes TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (event_id, segment_id, relationship_type)
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO {event_segments_table} (
            event_id, segment_id, relationship_type, notes
        )
        SELECT event_id, segment_id, relationship_type, notes
        FROM event_segments
        """
    )

    _execute_statements(
        connection,
        (
            "DROP TABLE event_segments",
            "DROP TABLE person_segments",
            "DROP TABLE organization_segments",
            "DROP TABLE segment_relations",
            "DROP TABLE industry_segments",
            "DROP TABLE segments",
            f"ALTER TABLE {segments_table} RENAME TO segments",
            f"ALTER TABLE {industry_segments_table} "
            "RENAME TO industry_segments",
            f"ALTER TABLE {segment_relations_table} "
            "RENAME TO segment_relations",
            f"ALTER TABLE {organization_segments_table} "
            "RENAME TO organization_segments",
            f"ALTER TABLE {person_segments_table} RENAME TO person_segments",
            f"ALTER TABLE {event_segments_table} RENAME TO event_segments",
            "CREATE INDEX idx_event_segments_segment_id "
            "ON event_segments(segment_id)",
        ),
    )

    foreign_key_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()
    if foreign_key_errors:
        raise RuntimeError(
            "重建 segments 表后出现外键错误："
            f"{[tuple(row) for row in foreign_key_errors]}"
        )


def _upgrade_segment_kinds_v1(connection: sqlite3.Connection) -> None:
    """把旧三类赛道分组升级为用户确认的四类目录。"""

    _rebuild_segments_with_kinds(
        connection,
        suffix="four_kinds",
        allowed_kinds=SEGMENT_KINDS_V1,
        kind_expression="""
            CASE segment_kind
                WHEN 'capability_product' THEN 'core_capability'
                WHEN 'support_system' THEN 'infrastructure'
                WHEN 'external_environment' THEN 'external_environment'
            END
        """,
    )


def _rollback_segment_kinds_v1(connection: sqlite3.Connection) -> None:
    """回到旧三类目录；核心能力和产品应用会重新合并。"""

    _rebuild_segments_with_kinds(
        connection,
        suffix="three_kinds",
        allowed_kinds=(
            "capability_product",
            "support_system",
            "external_environment",
        ),
        kind_expression="""
            CASE segment_kind
                WHEN 'core_capability' THEN 'capability_product'
                WHEN 'product_application' THEN 'capability_product'
                WHEN 'infrastructure' THEN 'support_system'
                WHEN 'external_environment' THEN 'external_environment'
            END
        """,
    )


MIGRATIONS = (
    Migration("0001", "articles_baseline", _create_articles_baseline),
    Migration(
        "0002",
        "v4_dossier_core",
        _create_v4_core_schema,
        _drop_v4_core_schema,
        destructive_down=True,
    ),
    Migration(
        "0003",
        "event_type_rules_v1",
        _apply_event_type_rules_v1,
        _rollback_event_type_rules_v1,
    ),
    Migration(
        "0004",
        "segment_kinds_v1",
        _upgrade_segment_kinds_v1,
        _rollback_segment_kinds_v1,
        destructive_down=True,
    ),
)


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def get_applied_migrations(connection: sqlite3.Connection) -> list[dict]:
    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'schema_migrations'
        """
    ).fetchone()
    if table_exists is None:
        return []

    rows = connection.execute(
        """
        SELECT version, name, applied_at
        FROM schema_migrations
        ORDER BY version
        """
    ).fetchall()
    return [
        {
            "version": row[0],
            "name": row[1],
            "applied_at": row[2],
        }
        for row in rows
    ]


def apply_migrations(
    connection: sqlite3.Connection,
    target_version: str | None = None,
) -> list[str]:
    """按顺序执行未应用的迁移，并返回本次应用的版本。"""

    connection.execute("PRAGMA foreign_keys = ON")
    with connection:
        _ensure_migration_table(connection)

    applied_versions = {
        item["version"]
        for item in get_applied_migrations(connection)
    }
    newly_applied = []

    for migration in MIGRATIONS:
        if target_version is not None and migration.version > target_version:
            break
        if migration.version in applied_versions:
            continue

        with connection:
            migration.up(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        newly_applied.append(migration.version)

    return newly_applied


def rollback_last_migration(
    connection: sqlite3.Connection,
    *,
    allow_destructive: bool = False,
) -> str | None:
    """回滚最后一条迁移；可能丢数据的回滚必须显式允许。"""

    applied = get_applied_migrations(connection)
    if not applied:
        return None

    last_version = applied[-1]["version"]
    migration = next(
        (item for item in MIGRATIONS if item.version == last_version),
        None,
    )
    if migration is None:
        raise RuntimeError(f"无法回滚未知迁移版本：{last_version}")
    if migration.down is None:
        raise RuntimeError(f"迁移 {last_version} 不支持回滚")
    if migration.destructive_down and not allow_destructive:
        raise RuntimeError(
            f"迁移 {last_version} 的回滚会删除数据；"
            "请显式传入 allow_destructive=True"
        )

    connection.execute("PRAGMA foreign_keys = ON")
    with connection:
        migration.down(connection)
        connection.execute(
            "DELETE FROM schema_migrations WHERE version = ?",
            (last_version,),
        )
    return last_version


def _open_database(database_file: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def main() -> None:
    from orbitai.config import DATABASE_FILE

    parser = argparse.ArgumentParser(description="OrbitAI SQLite 迁移工具")
    parser.add_argument("command", choices=("up", "status", "down"))
    parser.add_argument(
        "--database",
        type=Path,
        default=DATABASE_FILE,
        help="SQLite 数据库路径，默认读取 orbitai.config.DATABASE_FILE",
    )
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="允许 down 删除对应迁移创建的数据表",
    )
    args = parser.parse_args()

    with _open_database(args.database) as connection:
        if args.command == "up":
            applied = apply_migrations(connection)
            print("已应用迁移：" + (", ".join(applied) if applied else "无"))
        elif args.command == "down":
            version = rollback_last_migration(
                connection,
                allow_destructive=args.allow_destructive,
            )
            print(f"已回滚迁移：{version or '无'}")
        else:
            applied = get_applied_migrations(connection)
            if not applied:
                print("当前没有已记录的迁移。")
            for item in applied:
                print(
                    f"{item['version']} {item['name']} "
                    f"{item['applied_at']}"
                )


if __name__ == "__main__":
    main()
