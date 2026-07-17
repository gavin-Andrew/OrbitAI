"""V4.1 产业与参与者名册的 SQLite 仓储层。"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable


class CatalogSchemaError(RuntimeError):
    """数据库缺少名册导入所需的数据表。"""


class CatalogWriteConflict(RuntimeError):
    """幂等写入发现已有记录与种子内容不一致。"""


@dataclass(frozen=True)
class CatalogRecord:
    """一条准备与 SQLite 记录比较或写入的名册记录。"""

    entity_type: str
    table: str
    key_fields: tuple[str, ...]
    values: dict[str, Any]
    action_hint: str = "create"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[Any, ...]:
        return tuple(self.values[field_name] for field_name in self.key_fields)

    @property
    def key_text(self) -> str:
        return "|".join(str(value) for value in self.key)


REQUIRED_CATALOG_TABLES = (
    "industries",
    "segments",
    "industry_segments",
    "organizations",
    "organization_aliases",
    "people",
    "person_aliases",
    "person_organization_roles",
    "organization_segments",
    "person_segments",
    "sources",
    "source_entries",
)


def iter_catalog_records(seed: dict[str, Any]) -> Iterable[CatalogRecord]:
    """按外键依赖顺序，把种子对象转换成可持久化记录。"""

    for industry in seed["industries"]:
        yield CatalogRecord(
            "industry",
            "industries",
            ("id",),
            {
                "id": industry["id"],
                "name": industry["name"],
                "slug": industry["slug"],
                "description": industry.get("description", ""),
                "status": industry.get("status", "active"),
            },
        )

    for segment in seed["segments"]:
        yield CatalogRecord(
            "segment",
            "segments",
            ("id",),
            {
                "id": segment["id"],
                "name": segment["name"],
                "slug": segment["slug"],
                "segment_kind": segment["segment_kind"],
                "description": segment.get("description", ""),
                "status": segment.get("status", "active"),
            },
            metadata={"content_status": segment.get("content_status")},
        )

    for relation in seed["industry_segments"]:
        yield CatalogRecord(
            "industry_segment",
            "industry_segments",
            ("industry_id", "segment_id"),
            {
                "industry_id": relation["industry_id"],
                "segment_id": relation["segment_id"],
                "relationship_type": relation.get(
                    "relationship_type", "contains"
                ),
                "is_primary": relation.get("is_primary", 1),
                "notes": relation.get("notes", ""),
            },
        )

    for organization in seed["organizations"]:
        yield CatalogRecord(
            "organization",
            "organizations",
            ("id",),
            {
                "id": organization["id"],
                "name": organization["name"],
                "organization_type": organization.get(
                    "organization_type", "company"
                ),
                "homepage_url": organization.get("homepage_url"),
                "description": organization.get("description", ""),
                "status": organization.get("status", "active"),
                "founded_on": organization.get("founded_on"),
                "ended_on": organization.get("ended_on"),
            },
            metadata={
                "verification_status": organization.get("verification_status"),
                "verification_source_ids": organization.get(
                    "verification_source_ids", []
                ),
            },
        )
        for alias in organization.get("aliases", []):
            yield CatalogRecord(
                "organization_alias",
                "organization_aliases",
                ("organization_id", "alias"),
                {
                    "organization_id": organization["id"],
                    "alias": alias,
                },
            )

    for person in seed["people"]:
        yield CatalogRecord(
            "person",
            "people",
            ("id",),
            {
                "id": person["id"],
                "name": person["name"],
                "description": person.get("description", ""),
                "status": person.get("status", "active"),
            },
            metadata={
                "verification_status": person.get("verification_status"),
                "verification_source_ids": person.get(
                    "verification_source_ids", []
                ),
            },
        )
        for alias in person.get("aliases", []):
            yield CatalogRecord(
                "person_alias",
                "person_aliases",
                ("person_id", "alias"),
                {"person_id": person["id"], "alias": alias},
            )

    for role in seed["person_organization_roles"]:
        yield CatalogRecord(
            "person_organization_role",
            "person_organization_roles",
            ("person_id", "organization_id", "role_title", "started_on"),
            {
                "person_id": role["person_id"],
                "organization_id": role["organization_id"],
                "role_title": role["role_title"],
                "started_on": role.get("started_on", ""),
                "ended_on": role.get("ended_on"),
                "is_current": role.get("is_current", 0),
                "notes": role.get("notes", ""),
            },
            metadata={
                "verification_status": role.get("verification_status"),
                "verification_source_ids": role.get(
                    "verification_source_ids", []
                ),
            },
        )

    for relation in seed["organization_segments"]:
        yield CatalogRecord(
            "organization_segment",
            "organization_segments",
            ("organization_id", "segment_id", "relationship_type"),
            {
                "organization_id": relation["organization_id"],
                "segment_id": relation["segment_id"],
                "relationship_type": relation.get(
                    "relationship_type", "participant"
                ),
                "notes": relation.get("notes", ""),
            },
        )

    for relation in seed["person_segments"]:
        yield CatalogRecord(
            "person_segment",
            "person_segments",
            ("person_id", "segment_id", "relationship_type"),
            {
                "person_id": relation["person_id"],
                "segment_id": relation["segment_id"],
                "relationship_type": relation.get(
                    "relationship_type", "participant"
                ),
                "notes": relation.get("notes", ""),
            },
        )

    for source in seed["sources"]:
        action_hint = source.get("registry_action", "create")
        if source.get("mapping_status") == "intentionally_unbound":
            action_hint = "intentionally_unbound"
        elif action_hint == "propose_create":
            action_hint = "create"

        yield CatalogRecord(
            "source",
            "sources",
            ("id",),
            {
                "id": source["id"],
                "name": source["name"],
                "source_type": source["source_type"],
                "tier": source.get("tier", "watched"),
                "organization_id": source.get("organization_id"),
                "person_id": source.get("person_id"),
                "tracking_reason": source.get("tracking_reason", ""),
                "notes": source.get("notes", ""),
            },
            action_hint=action_hint,
            metadata={
                "registry_action": source.get("registry_action"),
                "mapping_status": source.get("mapping_status"),
            },
        )

        for entry in source.get("entries", []):
            yield CatalogRecord(
                "source_entry",
                "source_entries",
                ("id",),
                {
                    "id": entry["id"],
                    "source_id": source["id"],
                    "entry_type": entry["entry_type"],
                    "label": entry["label"],
                    "url": entry.get("url"),
                    "status": entry.get("status", "planned"),
                    "existing_in_sources_json": entry.get(
                        "existing_in_sources_json", 0
                    ),
                    "notes": entry.get("notes", ""),
                },
            )


class CatalogRepository:
    """对名册表执行集中、可测试的查询和只增不改写入。"""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def ensure_schema(self) -> None:
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        table_names = {row[0] for row in rows}
        missing = sorted(set(REQUIRED_CATALOG_TABLES) - table_names)
        if missing:
            raise CatalogSchemaError(
                "数据库尚未具备 V4 名册表：" + ", ".join(missing)
            )

    def fetch_table(self, table: str) -> list[dict[str, Any]]:
        if table not in REQUIRED_CATALOG_TABLES:
            raise ValueError(f"不允许读取未登记的名册表：{table}")
        cursor = self.connection.execute(f"SELECT * FROM {table}")
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def load_state(self) -> dict[str, list[dict[str, Any]]]:
        self.ensure_schema()
        return {
            table: self.fetch_table(table)
            for table in REQUIRED_CATALOG_TABLES
        }

    @staticmethod
    def _rows_as_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """把 SQLite 查询结果转换成页面层容易使用的字典。"""

        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_industry_by_slug(self, slug: str) -> dict[str, Any] | None:
        """按稳定的网页标识 slug 读取一个产业。"""

        self.ensure_schema()
        cursor = self.connection.execute(
            """
            SELECT id, name, slug, description, status
            FROM industries
            WHERE slug = ? AND status = 'active'
            """,
            (slug,),
        )
        rows = self._rows_as_dicts(cursor)
        return rows[0] if rows else None

    def list_industry_segments(
        self,
        industry_id: str,
    ) -> list[dict[str, Any]]:
        """读取产业下的赛道，并同时统计已关联的组织和人物。"""

        self.ensure_schema()
        cursor = self.connection.execute(
            """
            SELECT
                s.id,
                s.name,
                s.slug,
                s.segment_kind,
                s.description,
                COUNT(DISTINCT os.organization_id) AS organization_count,
                COUNT(DISTINCT ps.person_id) AS person_count
            FROM industry_segments AS industry_link
            JOIN segments AS s
                ON s.id = industry_link.segment_id
            LEFT JOIN organization_segments AS os
                ON os.segment_id = s.id
            LEFT JOIN person_segments AS ps
                ON ps.segment_id = s.id
            WHERE industry_link.industry_id = ?
                AND s.status = 'active'
            GROUP BY
                s.id,
                s.name,
                s.slug,
                s.segment_kind,
                s.description
            ORDER BY
                CASE
                    WHEN COUNT(DISTINCT os.organization_id)
                       + COUNT(DISTINCT ps.person_id) > 0
                    THEN 0
                    ELSE 1
                END,
                s.name COLLATE NOCASE
            """,
            (industry_id,),
        )
        return self._rows_as_dicts(cursor)

    def list_segment_organizations(
        self,
        segment_id: str,
    ) -> list[dict[str, Any]]:
        """读取一个赛道已经登记的组织参与者。"""

        cursor = self.connection.execute(
            """
            SELECT
                o.id,
                o.name,
                o.organization_type,
                o.homepage_url,
                o.description
            FROM organization_segments AS segment_link
            JOIN organizations AS o
                ON o.id = segment_link.organization_id
            WHERE segment_link.segment_id = ?
                AND o.status = 'active'
            ORDER BY o.name COLLATE NOCASE
            """,
            (segment_id,),
        )
        return self._rows_as_dicts(cursor)

    def list_segment_people(
        self,
        segment_id: str,
    ) -> list[dict[str, Any]]:
        """读取一个赛道已经登记的人物及其当前任职摘要。"""

        cursor = self.connection.execute(
            """
            SELECT
                p.id,
                p.name,
                p.description,
                role.role_title,
                organization.name AS organization_name
            FROM person_segments AS segment_link
            JOIN people AS p
                ON p.id = segment_link.person_id
            LEFT JOIN person_organization_roles AS role
                ON role.person_id = p.id
                AND role.is_current = 1
            LEFT JOIN organizations AS organization
                ON organization.id = role.organization_id
            WHERE segment_link.segment_id = ?
                AND p.status = 'active'
            ORDER BY p.name COLLATE NOCASE
            """,
            (segment_id,),
        )
        return self._rows_as_dicts(cursor)

    def find_record(self, record: CatalogRecord) -> dict[str, Any] | None:
        where_clause = " AND ".join(
            f"{field_name} = ?" for field_name in record.key_fields
        )
        row = self.connection.execute(
            f"SELECT * FROM {record.table} WHERE {where_clause}",
            record.key,
        ).fetchone()
        if row is None:
            return None
        columns = [item[0] for item in self.connection.execute(
            f"SELECT * FROM {record.table} LIMIT 0"
        ).description]
        return dict(zip(columns, row))

    @staticmethod
    def changed_fields(
        record: CatalogRecord,
        existing: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        return {
            field_name: {
                "database": existing.get(field_name),
                "seed": seed_value,
            }
            for field_name, seed_value in record.values.items()
            if existing.get(field_name) != seed_value
        }

    def insert_records(
        self,
        records: Iterable[CatalogRecord],
    ) -> dict[str, int]:
        """只插入缺失记录；相同记录跳过，不同记录拒绝覆盖。"""

        inserted: Counter[str] = Counter()
        for record in records:
            existing = self.find_record(record)
            if existing is not None:
                changes = self.changed_fields(record, existing)
                if changes:
                    raise CatalogWriteConflict(
                        f"{record.entity_type}:{record.key_text} 已存在且内容不同"
                    )
                continue

            columns = tuple(record.values)
            placeholders = ", ".join("?" for _ in columns)
            self.connection.execute(
                f"INSERT INTO {record.table} "
                f"({', '.join(columns)}) VALUES ({placeholders})",
                tuple(record.values[column] for column in columns),
            )
            inserted[record.entity_type] += 1

        return dict(sorted(inserted.items()))
