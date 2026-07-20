"""产业与参与者名册的 SQLite 仓储层。"""

from __future__ import annotations

import json
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

    def get_segment_by_slug(self, slug: str) -> dict[str, Any] | None:
        """读取一个赛道，并带回它所属的主要产业。"""

        self.ensure_schema()
        cursor = self.connection.execute(
            """
            SELECT
                s.id,
                s.name,
                s.slug,
                s.segment_kind,
                s.description,
                industry.id AS industry_id,
                industry.name AS industry_name,
                industry.slug AS industry_slug,
                (
                    SELECT COUNT(DISTINCT organization_id)
                    FROM organization_segments
                    WHERE segment_id = s.id
                ) AS organization_count,
                (
                    SELECT COUNT(DISTINCT person_id)
                    FROM person_segments
                    WHERE segment_id = s.id
                ) AS person_count
            FROM segments AS s
            LEFT JOIN industry_segments AS industry_link
                ON industry_link.segment_id = s.id
                AND industry_link.is_primary = 1
            LEFT JOIN industries AS industry
                ON industry.id = industry_link.industry_id
                AND industry.status = 'active'
            WHERE s.slug = ? AND s.status = 'active'
            ORDER BY industry.name COLLATE NOCASE
            LIMIT 1
            """,
            (slug,),
        )
        rows = self._rows_as_dicts(cursor)
        return rows[0] if rows else None

    def list_active_organizations(self) -> list[dict[str, Any]]:
        """读取企业与机构档案入口需要的基础信息。"""

        self.ensure_schema()
        cursor = self.connection.execute(
            """
            SELECT
                o.id,
                o.name,
                o.organization_type,
                o.homepage_url,
                o.description,
                o.founded_on,
                COUNT(DISTINCT segment_link.segment_id) AS segment_count
            FROM organizations AS o
            LEFT JOIN organization_segments AS segment_link
                ON segment_link.organization_id = o.id
            WHERE o.status = 'active'
            GROUP BY
                o.id,
                o.name,
                o.organization_type,
                o.homepage_url,
                o.description,
                o.founded_on
            ORDER BY o.name COLLATE NOCASE
            """
        )
        return self._rows_as_dicts(cursor)

    def list_organization_aliases(self) -> list[dict[str, Any]]:
        """读取全部有效组织别名，由服务层按组织归组。"""

        self.ensure_schema()
        cursor = self.connection.execute(
            """
            SELECT alias.organization_id, alias.alias
            FROM organization_aliases AS alias
            JOIN organizations AS organization
                ON organization.id = alias.organization_id
            WHERE organization.status = 'active'
            ORDER BY alias.organization_id, alias.alias COLLATE NOCASE
            """
        )
        return self._rows_as_dicts(cursor)

    def list_active_people(self) -> list[dict[str, Any]]:
        """读取人物档案入口需要的基础信息。"""

        self.ensure_schema()
        cursor = self.connection.execute(
            """
            SELECT
                p.id,
                p.name,
                p.description,
                COUNT(DISTINCT segment_link.segment_id) AS segment_count
            FROM people AS p
            LEFT JOIN person_segments AS segment_link
                ON segment_link.person_id = p.id
            WHERE p.status = 'active'
            GROUP BY p.id, p.name, p.description
            ORDER BY p.name COLLATE NOCASE
            """
        )
        return self._rows_as_dicts(cursor)

    def list_person_aliases(self) -> list[dict[str, Any]]:
        """读取全部有效人物别名，由服务层按人物归组。"""

        self.ensure_schema()
        cursor = self.connection.execute(
            """
            SELECT alias.person_id, alias.alias
            FROM person_aliases AS alias
            JOIN people AS person ON person.id = alias.person_id
            WHERE person.status = 'active'
            ORDER BY alias.person_id, alias.alias COLLATE NOCASE
            """
        )
        return self._rows_as_dicts(cursor)

    def list_current_person_roles(self) -> list[dict[str, Any]]:
        """读取人物当前任职关系，由服务层放回相应人物档案。"""

        self.ensure_schema()
        cursor = self.connection.execute(
            """
            SELECT
                role.person_id,
                role.organization_id,
                organization.name AS organization_name,
                role.role_title,
                role.started_on
            FROM person_organization_roles AS role
            JOIN people AS person ON person.id = role.person_id
            JOIN organizations AS organization
                ON organization.id = role.organization_id
            WHERE role.is_current = 1
                AND person.status = 'active'
                AND organization.status = 'active'
            ORDER BY
                role.person_id,
                organization.name COLLATE NOCASE,
                role.role_title COLLATE NOCASE
            """
        )
        return self._rows_as_dicts(cursor)

    def get_entity_for_edit(
        self,
        entity_type: str,
        entity_id: str,
    ) -> dict[str, Any] | None:
        """读取一个可管理的组织或人物，包括已经归档的记录。"""

        self.ensure_schema()
        table = {
            "organization": "organizations",
            "person": "people",
        }.get(entity_type)
        if table is None:
            raise ValueError(f"不支持的名册对象类型：{entity_type}")

        cursor = self.connection.execute(
            f"SELECT * FROM {table} WHERE id = ?",
            (entity_id,),
        )
        rows = self._rows_as_dicts(cursor)
        return rows[0] if rows else None

    def list_entity_aliases_for_edit(
        self,
        entity_type: str,
        entity_id: str,
    ) -> list[str]:
        """读取一个组织或人物的全部别名。"""

        config = {
            "organization": ("organization_aliases", "organization_id"),
            "person": ("person_aliases", "person_id"),
        }.get(entity_type)
        if config is None:
            raise ValueError(f"不支持的名册对象类型：{entity_type}")
        table, owner_field = config
        rows = self.connection.execute(
            f"""
            SELECT alias FROM {table}
            WHERE {owner_field} = ?
            ORDER BY alias COLLATE NOCASE
            """,
            (entity_id,),
        ).fetchall()
        return [row["alias"] for row in rows]

    def update_entity_for_edit(
        self,
        entity_type: str,
        entity_id: str,
        values: dict[str, Any],
        updated_at: str,
    ) -> None:
        """更新经过服务层校验的有限字段。"""

        allowed_fields = {
            "organization": {
                "name",
                "organization_type",
                "homepage_url",
                "description",
                "status",
            },
            "person": {"name", "description", "status"},
        }
        fields = allowed_fields.get(entity_type)
        if fields is None:
            raise ValueError(f"不支持的名册对象类型：{entity_type}")
        if not set(values).issubset(fields):
            unexpected = sorted(set(values) - fields)
            raise ValueError(f"不允许修改字段：{', '.join(unexpected)}")

        table = "organizations" if entity_type == "organization" else "people"
        assignments = [f"{field_name} = ?" for field_name in values]
        assignments.append("updated_at = ?")
        parameters = [values[field_name] for field_name in values]
        parameters.extend((updated_at, entity_id))
        cursor = self.connection.execute(
            f"UPDATE {table} SET {', '.join(assignments)} WHERE id = ?",
            parameters,
        )
        if cursor.rowcount != 1:
            raise LookupError(f"名册对象不存在：{entity_type}:{entity_id}")

    def replace_entity_aliases(
        self,
        entity_type: str,
        entity_id: str,
        aliases: list[str],
    ) -> None:
        """在当前事务中整体替换别名集合。"""

        config = {
            "organization": ("organization_aliases", "organization_id"),
            "person": ("person_aliases", "person_id"),
        }.get(entity_type)
        if config is None:
            raise ValueError(f"不支持的名册对象类型：{entity_type}")
        table, owner_field = config
        self.connection.execute(
            f"DELETE FROM {table} WHERE {owner_field} = ?",
            (entity_id,),
        )
        self.connection.executemany(
            f"INSERT INTO {table} ({owner_field}, alias) VALUES (?, ?)",
            ((entity_id, alias) for alias in aliases),
        )

    def insert_catalog_change_log(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        changes: dict[str, Any],
        before: dict[str, Any],
        after: dict[str, Any],
        change_reason: str,
        actor: str,
        expected_revision: str,
        result_revision: str,
    ) -> int:
        """写入与业务修改处于同一事务的审计记录。"""

        cursor = self.connection.execute(
            """
            INSERT INTO catalog_change_log (
                entity_type,
                entity_id,
                action,
                changed_fields_json,
                before_json,
                after_json,
                change_reason,
                actor,
                expected_revision,
                result_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                action,
                json.dumps(changes, ensure_ascii=False, sort_keys=True),
                json.dumps(before, ensure_ascii=False, sort_keys=True),
                json.dumps(after, ensure_ascii=False, sort_keys=True),
                change_reason,
                actor,
                expected_revision,
                result_revision,
            ),
        )
        return int(cursor.lastrowid)

    def list_catalog_change_log(self, limit: int = 30) -> list[dict[str, Any]]:
        """读取最近的名册修改记录。"""

        cursor = self.connection.execute(
            """
            SELECT
                id,
                entity_type,
                entity_id,
                action,
                changed_fields_json,
                before_json,
                after_json,
                change_reason,
                actor,
                expected_revision,
                result_revision,
                created_at
            FROM catalog_change_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
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
