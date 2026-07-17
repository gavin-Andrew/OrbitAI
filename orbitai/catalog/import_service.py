"""V4.1 名册种子的校验、导入预览和显式幂等写入。"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from orbitai.catalog.repository import (
    CatalogRecord,
    CatalogRepository,
    CatalogSchemaError,
    iter_catalog_records,
)
from orbitai.core.config import (
    CATALOG_SEED_FILE,
    DATABASE_FILE,
    SOURCE_REGISTRY_FILE,
)
from orbitai.core.database import get_connection, init_db


DEFAULT_SEED_FILE = CATALOG_SEED_FILE
DEFAULT_SOURCE_REGISTRY_FILE = SOURCE_REGISTRY_FILE
DEFAULT_DATABASE_FILE = DATABASE_FILE

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PARTIAL_DATE_PATTERN = re.compile(
    r"^(?:[0-9]{4})(?:-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12][0-9]|3[01]))?)?$"
)

SEGMENT_KINDS = {
    "core_capability",
    "infrastructure",
    "product_application",
    "external_environment",
}
REQUIRED_COLLECTIONS = (
    "verification_sources",
    "industries",
    "segment_groups",
    "segments",
    "industry_segments",
    "organizations",
    "people",
    "person_organization_roles",
    "organization_segments",
    "person_segments",
    "source_registry_operations",
    "sources",
)
ALLOWED_CONTENT_STATUSES = {"pilot_active", "directory_only"}
ALLOWED_SOURCE_TIERS = {"core", "watched", "reference", "archived"}
ALLOWED_ENTRY_TYPES = {
    "rss",
    "website",
    "api",
    "youtube",
    "podcast",
    "manual",
    "other",
}
ALLOWED_ENTRY_STATUSES = {"enabled", "planned", "disabled", "archived"}
ALLOWED_REGISTRY_ACTIONS = {
    "map_existing",
    "propose_create",
    "create_from_split",
}
ALLOWED_MAPPING_STATUSES = {"confirmed", "intentionally_unbound"}


class CatalogDocumentError(RuntimeError):
    """种子或来源注册表不是可读取的 JSON 文档。"""


class CatalogImportBlocked(RuntimeError):
    """预览发现错误或冲突，因此禁止写库。"""

    def __init__(self, report: "CatalogImportReport"):
        super().__init__("名册导入被校验错误或数据库冲突阻止")
        self.report = report


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [item for item in self.issues if item.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [item for item in self.issues if item.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def add(
        self,
        severity: str,
        code: str,
        path: str,
        message: str,
    ) -> None:
        self.issues.append(ValidationIssue(severity, code, path, message))

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [item.to_dict() for item in self.issues],
        }


@dataclass(frozen=True)
class PreviewOperation:
    entity_type: str
    key: str
    action: str
    blocking: bool
    reason: str
    changes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "key": self.key,
            "action": self.action,
            "blocking": self.blocking,
            "reason": self.reason,
            "changes": self.changes,
            "metadata": self.metadata,
        }


@dataclass
class CatalogImportReport:
    seed_id: str
    seed_status: str
    validation: ValidationResult
    operations: list[PreviewOperation]
    applied: bool = False
    inserted: dict[str, int] = field(default_factory=dict)

    @property
    def blocking_operations(self) -> list[PreviewOperation]:
        return [item for item in self.operations if item.blocking]

    @property
    def can_apply(self) -> bool:
        return self.validation.is_valid and not self.blocking_operations

    @property
    def summary(self) -> dict[str, Any]:
        action_counts = Counter(item.action for item in self.operations)
        return {
            "operation_count": len(self.operations),
            "action_counts": dict(sorted(action_counts.items())),
            "blocking_count": len(self.blocking_operations),
            "can_apply": self.can_apply,
            "applied": self.applied,
            "inserted_count": sum(self.inserted.values()),
            "inserted_by_type": self.inserted,
        }

    def to_dict(self, *, include_operations: bool = True) -> dict[str, Any]:
        result = {
            "seed_id": self.seed_id,
            "seed_status": self.seed_status,
            "validation": self.validation.to_dict(),
            "summary": self.summary,
        }
        if include_operations:
            result["operations"] = [item.to_dict() for item in self.operations]
        return result


def load_json_document(path: str | Path, label: str) -> dict[str, Any]:
    file_path = Path(path)
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogDocumentError(f"无法读取{label} {file_path}: {exc}") from exc

    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CatalogDocumentError(
            f"{label}不是有效 JSON：{file_path}:{exc.lineno}:{exc.colno}"
        ) from exc

    if not isinstance(document, dict):
        raise CatalogDocumentError(f"{label}顶层必须是 JSON 对象：{file_path}")
    return document


def normalize_identity_name(value: str) -> str:
    """为身份匹配生成检索键，同时保留原显示名称不变。"""

    normalized = unicodedata.normalize("NFKC", str(value))
    return " ".join(normalized.strip().split()).casefold()


def _validate_unique_ids(
    result: ValidationResult,
    items: Iterable[dict[str, Any]],
    path: str,
) -> set[str]:
    ids: set[str] = set()
    for index, item in enumerate(items):
        item_path = f"{path}[{index}].id"
        item_id = item.get("id")
        if not isinstance(item_id, str) or not ID_PATTERN.fullmatch(item_id):
            result.add(
                "error",
                "invalid_stable_id",
                item_path,
                "稳定 ID 必须由小写英文、数字和下划线组成。",
            )
            continue
        if item_id in ids:
            result.add(
                "error",
                "duplicate_id",
                item_path,
                f"同一集合中重复使用 ID：{item_id}",
            )
        ids.add(item_id)
    return ids


def _validate_identity_namespace(
    result: ValidationResult,
    items: list[dict[str, Any]],
    path: str,
) -> None:
    seen: dict[str, tuple[str, str]] = {}
    for index, item in enumerate(items):
        item_id = item.get("id", f"index:{index}")
        names = [("name", item.get("name"))]
        names.extend(
            (f"aliases[{alias_index}]", alias)
            for alias_index, alias in enumerate(item.get("aliases", []))
        )
        for field_path, value in names:
            full_path = f"{path}[{index}].{field_path}"
            if not isinstance(value, str) or not normalize_identity_name(value):
                result.add(
                    "error",
                    "empty_identity_name",
                    full_path,
                    "规范名称和别名都必须是非空字符串。",
                )
                continue
            key = normalize_identity_name(value)
            previous = seen.get(key)
            if previous is not None:
                result.add(
                    "error",
                    "identity_name_collision",
                    full_path,
                    f"名称规范化后与 {previous[0]} 的 {previous[1]} 冲突。",
                )
            else:
                seen[key] = (str(item_id), full_path)


def _validate_date(
    result: ValidationResult,
    value: Any,
    path: str,
) -> None:
    if value is None or value == "":
        return
    if not isinstance(value, str) or not PARTIAL_DATE_PATTERN.fullmatch(value):
        result.add(
            "error",
            "invalid_partial_date",
            path,
            "日期只能使用 YYYY、YYYY-MM、YYYY-MM-DD、空字符串或 null。",
        )


def _registry_sources(source_registry: dict[str, Any] | None) -> list[dict[str, Any]]:
    if source_registry is None:
        return []
    sources = source_registry.get("sources", [])
    return sources if isinstance(sources, list) else []


def validate_catalog_seed(
    seed: dict[str, Any],
    source_registry: dict[str, Any] | None = None,
) -> ValidationResult:
    """校验种子结构、业务约束、引用闭合和来源拆分。"""

    result = ValidationResult()
    if not isinstance(seed.get("seed_id"), str) or not seed.get("seed_id"):
        result.add("error", "missing_seed_id", "seed_id", "缺少种子 ID。")
    if seed.get("status") != "draft":
        result.add(
            "warning",
            "unexpected_seed_status",
            "status",
            "V4.1 策划输入通常应保持 draft，并通过显式确认写库。",
        )

    if not isinstance(seed.get("confirmed_scope"), dict):
        result.add(
            "error",
            "missing_confirmed_scope",
            "confirmed_scope",
            "confirmed_scope 必须是对象。",
        )
    if not isinstance(seed.get("import_policy"), dict):
        result.add(
            "error",
            "missing_import_policy",
            "import_policy",
            "import_policy 必须是对象。",
        )
    if not isinstance(seed.get("verification_statuses"), list) or not all(
        isinstance(item, str) for item in seed.get("verification_statuses", [])
    ):
        result.add(
            "error",
            "invalid_verification_statuses",
            "verification_statuses",
            "verification_statuses 必须是字符串数组。",
        )

    missing_or_invalid = False
    for collection_name in REQUIRED_COLLECTIONS:
        if not isinstance(seed.get(collection_name), list):
            result.add(
                "error",
                "missing_collection",
                collection_name,
                f"{collection_name} 必须是数组。",
            )
            missing_or_invalid = True
    if missing_or_invalid:
        return result

    for collection_name in REQUIRED_COLLECTIONS:
        for index, item in enumerate(seed[collection_name]):
            if not isinstance(item, dict):
                result.add(
                    "error",
                    "invalid_collection_item",
                    f"{collection_name}[{index}]",
                    "集合中的每一项都必须是 JSON 对象。",
                )
                missing_or_invalid = True
    if missing_or_invalid:
        return result
    for collection_name in ("organizations", "people"):
        for index, item in enumerate(seed[collection_name]):
            aliases = item.get("aliases", [])
            if not isinstance(aliases, list) or not all(
                isinstance(alias, str) for alias in aliases
            ):
                result.add(
                    "error",
                    "invalid_aliases",
                    f"{collection_name}[{index}].aliases",
                    "aliases 必须是字符串数组。",
                )
                missing_or_invalid = True
    for source_index, source in enumerate(seed["sources"]):
        entries = source.get("entries", [])
        if not isinstance(entries, list) or not all(
            isinstance(entry, dict) for entry in entries
        ):
            result.add(
                "error",
                "invalid_source_entries",
                f"sources[{source_index}].entries",
                "entries 必须是 JSON 对象数组。",
            )
            missing_or_invalid = True
    for operation_index, operation in enumerate(
        seed["source_registry_operations"]
    ):
        to_ids = operation.get("to_source_ids", [])
        if not isinstance(to_ids, list) or not all(
            isinstance(item, str) for item in to_ids
        ):
            result.add(
                "error",
                "invalid_split_targets",
                f"source_registry_operations[{operation_index}].to_source_ids",
                "to_source_ids 必须是字符串数组。",
            )
            missing_or_invalid = True
    if missing_or_invalid:
        return result

    verification_ids = _validate_unique_ids(
        result, seed["verification_sources"], "verification_sources"
    )
    industry_ids = _validate_unique_ids(result, seed["industries"], "industries")
    group_ids = _validate_unique_ids(
        result, seed["segment_groups"], "segment_groups"
    )
    segment_ids = _validate_unique_ids(result, seed["segments"], "segments")
    organization_ids = _validate_unique_ids(
        result, seed["organizations"], "organizations"
    )
    person_ids = _validate_unique_ids(result, seed["people"], "people")
    source_ids = _validate_unique_ids(result, seed["sources"], "sources")

    _validate_identity_namespace(result, seed["organizations"], "organizations")
    _validate_identity_namespace(result, seed["people"], "people")
    _validate_identity_namespace(result, seed["sources"], "sources")

    scope = seed.get("confirmed_scope", {})
    declared_counts = {
        "segment_group_count": len(seed["segment_groups"]),
        "segment_count": len(seed["segments"]),
        "organization_count": len(seed["organizations"]),
        "person_count": len(seed["people"]),
    }
    for field_name, actual_count in declared_counts.items():
        if scope.get(field_name) != actual_count:
            result.add(
                "error",
                "scope_count_mismatch",
                f"confirmed_scope.{field_name}",
                f"声明值 {scope.get(field_name)!r} 与实际数量 {actual_count} 不一致。",
            )

    if group_ids != SEGMENT_KINDS:
        result.add(
            "error",
            "segment_group_mismatch",
            "segment_groups",
            "目录分组必须与数据库允许的四个 segment_kind 完全一致。",
        )
    display_orders = [item.get("display_order") for item in seed["segment_groups"]]
    if (
        not all(isinstance(item, int) for item in display_orders)
        or sorted(display_orders) != list(range(1, len(display_orders) + 1))
    ):
        result.add(
            "error",
            "invalid_group_order",
            "segment_groups",
            "display_order 必须从 1 开始连续且不重复。",
        )

    actual_group_counts = Counter()
    pilot_segment_ids = []
    slugs: set[str] = set()
    for index, segment in enumerate(seed["segments"]):
        path = f"segments[{index}]"
        slug = segment.get("slug")
        if not isinstance(slug, str) or not SLUG_PATTERN.fullmatch(slug):
            result.add(
                "error",
                "invalid_slug",
                f"{path}.slug",
                "slug 必须使用小写英文、数字和连字符。",
            )
        elif slug in slugs:
            result.add("error", "duplicate_slug", f"{path}.slug", f"slug 重复：{slug}")
        if isinstance(slug, str):
            slugs.add(slug)

        kind = segment.get("segment_kind")
        if kind not in group_ids:
            result.add(
                "error",
                "unknown_segment_group",
                f"{path}.segment_kind",
                f"赛道引用了不存在的目录分组：{kind}",
            )
        else:
            actual_group_counts[kind] += 1

        content_status = segment.get("content_status")
        if content_status not in ALLOWED_CONTENT_STATUSES:
            result.add(
                "error",
                "invalid_content_status",
                f"{path}.content_status",
                f"不支持的内容状态：{content_status}",
            )
        if content_status == "pilot_active":
            pilot_segment_ids.append(segment.get("id"))

    declared_group_counts = {
        item.get("id"): item.get("segment_count")
        for item in seed["segment_groups"]
    }
    if dict(actual_group_counts) != declared_group_counts:
        result.add(
            "error",
            "segment_group_count_mismatch",
            "segment_groups",
            f"分组声明数量 {declared_group_counts} 与赛道实际数量 {dict(actual_group_counts)} 不一致。",
        )
    if pilot_segment_ids != [scope.get("pilot_segment_id")]:
        result.add(
            "error",
            "pilot_segment_mismatch",
            "confirmed_scope.pilot_segment_id",
            "必须恰好有一个 pilot_active，且与 confirmed_scope 一致。",
        )

    relation_keys: set[tuple[Any, ...]] = set()
    related_segment_ids: set[str] = set()
    for index, relation in enumerate(seed["industry_segments"]):
        path = f"industry_segments[{index}]"
        industry_id = relation.get("industry_id")
        segment_id = relation.get("segment_id")
        key = (industry_id, segment_id)
        if key in relation_keys:
            result.add("error", "duplicate_relation", path, f"重复产业赛道关系：{key}")
        relation_keys.add(key)
        related_segment_ids.add(segment_id)
        if industry_id not in industry_ids:
            result.add("error", "missing_reference", f"{path}.industry_id", "引用了不存在的产业。")
        if segment_id not in segment_ids:
            result.add("error", "missing_reference", f"{path}.segment_id", "引用了不存在的赛道。")
    if related_segment_ids != segment_ids:
        result.add(
            "error",
            "incomplete_industry_catalog",
            "industry_segments",
            "每个赛道必须且只能通过产业赛道关系进入目录。",
        )

    verification_statuses = set(seed.get("verification_statuses", []))
    for collection_name in ("organizations", "people", "person_organization_roles"):
        for index, item in enumerate(seed[collection_name]):
            path = f"{collection_name}[{index}]"
            status = item.get("verification_status")
            if status not in verification_statuses:
                result.add(
                    "error",
                    "invalid_verification_status",
                    f"{path}.verification_status",
                    f"未登记的核查状态：{status}",
                )
            if status == "needs_primary_source":
                result.add(
                    "warning",
                    "needs_primary_source",
                    f"{path}.verification_status",
                    "允许进入名册，但仍需在后续补充一手来源。",
                )
            for source_id in item.get("verification_source_ids", []):
                if source_id not in verification_ids:
                    result.add(
                        "error",
                        "missing_reference",
                        f"{path}.verification_source_ids",
                        f"引用了不存在的核查来源：{source_id}",
                    )

    role_keys: set[tuple[Any, ...]] = set()
    for index, role in enumerate(seed["person_organization_roles"]):
        path = f"person_organization_roles[{index}]"
        key = (
            role.get("person_id"),
            role.get("organization_id"),
            role.get("role_title"),
            role.get("started_on", ""),
        )
        if key in role_keys:
            result.add("error", "duplicate_relation", path, f"重复任职关系：{key}")
        role_keys.add(key)
        if role.get("person_id") not in person_ids:
            result.add("error", "missing_reference", f"{path}.person_id", "引用了不存在的人物。")
        if role.get("organization_id") not in organization_ids:
            result.add("error", "missing_reference", f"{path}.organization_id", "引用了不存在的组织。")
        _validate_date(result, role.get("started_on", ""), f"{path}.started_on")
        _validate_date(result, role.get("ended_on"), f"{path}.ended_on")

    for collection_name, owner_field, owner_ids in (
        ("organization_segments", "organization_id", organization_ids),
        ("person_segments", "person_id", person_ids),
    ):
        keys: set[tuple[Any, ...]] = set()
        owners: set[str] = set()
        for index, relation in enumerate(seed[collection_name]):
            path = f"{collection_name}[{index}]"
            owner_id = relation.get(owner_field)
            segment_id = relation.get("segment_id")
            key = (owner_id, segment_id, relation.get("relationship_type", "participant"))
            if key in keys:
                result.add("error", "duplicate_relation", path, f"重复赛道关系：{key}")
            keys.add(key)
            owners.add(owner_id)
            if owner_id not in owner_ids:
                result.add("error", "missing_reference", f"{path}.{owner_field}", "引用了不存在的参与者。")
            if segment_id not in segment_ids:
                result.add("error", "missing_reference", f"{path}.segment_id", "引用了不存在的赛道。")
        if owners != owner_ids:
            result.add(
                "error",
                "incomplete_participant_mapping",
                collection_name,
                "每个首批参与者必须至少关联一个赛道。",
            )

    entry_ids: set[str] = set()
    participant_bindings: set[tuple[str, str]] = set()
    participant_sources = 0
    supplemental_sources = 0
    for source_index, source in enumerate(seed["sources"]):
        path = f"sources[{source_index}]"
        organization_id = source.get("organization_id")
        person_id = source.get("person_id")
        if organization_id is not None and person_id is not None:
            result.add(
                "error",
                "ambiguous_source_owner",
                path,
                "一个来源不能同时绑定组织和人物。",
            )
        if organization_id is not None:
            participant_sources += 1
            binding = ("organization", organization_id)
            if organization_id not in organization_ids:
                result.add("error", "missing_reference", f"{path}.organization_id", "来源引用了不存在的组织。")
            if binding in participant_bindings:
                result.add("error", "duplicate_source_binding", path, "同一参与者绑定了多个首批来源。")
            participant_bindings.add(binding)
        elif person_id is not None:
            participant_sources += 1
            binding = ("person", person_id)
            if person_id not in person_ids:
                result.add("error", "missing_reference", f"{path}.person_id", "来源引用了不存在的人物。")
            if binding in participant_bindings:
                result.add("error", "duplicate_source_binding", path, "同一参与者绑定了多个首批来源。")
            participant_bindings.add(binding)
        else:
            supplemental_sources += 1

        if (organization_id is not None or person_id is not None) and source.get("tier") != "core":
            result.add("error", "participant_source_not_core", f"{path}.tier", "首批参与者来源必须使用 core 层级。")
        if source.get("tier") not in ALLOWED_SOURCE_TIERS:
            result.add("error", "invalid_source_tier", f"{path}.tier", "来源层级不受数据库支持。")
        if source.get("registry_action") not in ALLOWED_REGISTRY_ACTIONS:
            result.add("error", "invalid_registry_action", f"{path}.registry_action", "来源注册动作不受支持。")
        if source.get("mapping_status") not in ALLOWED_MAPPING_STATUSES:
            result.add("error", "invalid_mapping_status", f"{path}.mapping_status", "来源映射状态不受支持。")

        for entry_index, entry in enumerate(source.get("entries", [])):
            entry_path = f"{path}.entries[{entry_index}]"
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not ID_PATTERN.fullmatch(entry_id):
                result.add("error", "invalid_stable_id", f"{entry_path}.id", "入口 ID 格式不正确。")
            elif entry_id in entry_ids:
                result.add("error", "duplicate_id", f"{entry_path}.id", f"入口 ID 重复：{entry_id}")
            entry_ids.add(entry_id)
            if entry.get("entry_type") not in ALLOWED_ENTRY_TYPES:
                result.add("error", "invalid_entry_type", f"{entry_path}.entry_type", "入口类型不受数据库支持。")
            if entry.get("status") not in ALLOWED_ENTRY_STATUSES:
                result.add("error", "invalid_entry_status", f"{entry_path}.status", "入口状态不受数据库支持。")
            if entry.get("existing_in_sources_json") not in (0, 1, False, True):
                result.add(
                    "error",
                    "invalid_boolean_flag",
                    f"{entry_path}.existing_in_sources_json",
                    "existing_in_sources_json 必须是 0 或 1。",
                )

    expected_participant_bindings = {
        *(("organization", item_id) for item_id in organization_ids),
        *(("person", item_id) for item_id in person_ids),
    }
    if participant_bindings != expected_participant_bindings:
        result.add(
            "error",
            "incomplete_source_mapping",
            "sources",
            "6 个组织和 6 位人物都必须恰好拥有一个核心来源。",
        )
    if participant_sources != scope.get("participant_source_count"):
        result.add(
            "error",
            "scope_count_mismatch",
            "confirmed_scope.participant_source_count",
            f"声明值与实际参与者来源数 {participant_sources} 不一致。",
        )
    if supplemental_sources != scope.get("supplemental_source_count"):
        result.add(
            "error",
            "scope_count_mismatch",
            "confirmed_scope.supplemental_source_count",
            f"声明值与实际补充来源数 {supplemental_sources} 不一致。",
        )

    registry_items = _registry_sources(source_registry)
    registry_by_id = {item.get("id"): item for item in registry_items}
    registry_entry_ids = {
        entry.get("id")
        for item in registry_items
        for entry in item.get("collection_entries", [])
    }
    split_targets: dict[str, str] = {}
    for index, operation in enumerate(seed["source_registry_operations"]):
        path = f"source_registry_operations[{index}]"
        if operation.get("operation") != "split":
            result.add("error", "unsupported_registry_operation", f"{path}.operation", "当前只支持来源拆分操作。")
            continue
        from_id = operation.get("from_source_id")
        to_ids = operation.get("to_source_ids", [])
        if source_registry is not None and from_id not in registry_by_id:
            result.add("error", "missing_legacy_source", f"{path}.from_source_id", "拆分源在 data/registries/sources.v4.json 中不存在。")
        if from_id in source_ids:
            result.add("error", "legacy_source_still_active", path, "拆分后的旧组合来源不能继续作为活动来源。")
        for target_id in to_ids:
            if target_id not in source_ids:
                result.add("error", "missing_split_target", f"{path}.to_source_ids", f"拆分目标不存在：{target_id}")
            split_targets[target_id] = from_id

    if source_registry is None:
        result.add(
            "warning",
            "source_registry_not_checked",
            "source_registry_file",
            "未提供 data/registries/sources.v4.json，因此没有校验复用和拆分来源。",
        )
    else:
        for source_index, source in enumerate(seed["sources"]):
            path = f"sources[{source_index}]"
            action = source.get("registry_action")
            source_id = source.get("id")
            if action == "map_existing" and source_id not in registry_by_id:
                result.add("error", "missing_legacy_source", f"{path}.id", "map_existing 来源在 data/registries/sources.v4.json 中不存在。")
            if action == "propose_create" and source_id in registry_by_id:
                result.add("error", "legacy_source_already_exists", f"{path}.registry_action", "来源已经存在，不应标记 propose_create。")
            if action == "create_from_split" and source_id not in split_targets:
                result.add("error", "missing_split_operation", f"{path}.registry_action", "create_from_split 来源没有对应拆分操作。")
            for entry_index, entry in enumerate(source.get("entries", [])):
                if entry.get("existing_in_sources_json") and entry.get("id") not in registry_entry_ids:
                    result.add(
                        "error",
                        "missing_legacy_entry",
                        f"{path}.entries[{entry_index}].id",
                        "标记为现有入口，但在 data/registries/sources.v4.json 中不存在。",
                    )

    return result


def _state_index(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> dict[tuple[Any, ...], dict[str, Any]]:
    return {
        tuple(row.get(field_name) for field_name in fields): row
        for row in rows
    }


def _identity_index(
    state: dict[str, list[dict[str, Any]]],
    entity_type: str,
) -> dict[str, set[str]]:
    if entity_type == "organization":
        owners = state["organizations"]
        aliases = state["organization_aliases"]
        owner_field = "organization_id"
    elif entity_type == "person":
        owners = state["people"]
        aliases = state["person_aliases"]
        owner_field = "person_id"
    else:
        owners = state["sources"]
        aliases = []
        owner_field = "source_id"

    index: dict[str, set[str]] = {}
    for owner in owners:
        key = normalize_identity_name(owner["name"])
        index.setdefault(key, set()).add(owner["id"])
    for alias in aliases:
        key = normalize_identity_name(alias["alias"])
        index.setdefault(key, set()).add(alias[owner_field])
    return index


def _alternative_conflict(
    record: CatalogRecord,
    state: dict[str, list[dict[str, Any]]],
    identity_indexes: dict[str, dict[str, set[str]]],
) -> str | None:
    if record.entity_type in {"industry", "segment"}:
        slug_matches = [
            row for row in state[record.table]
            if row.get("slug") == record.values.get("slug")
        ]
        if slug_matches:
            return f"slug 已由其他 ID 使用：{slug_matches[0]['id']}"

    if record.entity_type in {"organization", "person", "source"}:
        owner_id = record.values["id"]
        names = [record.values["name"]]
        if record.entity_type in {"organization", "person"}:
            alias_table = (
                "organization_aliases"
                if record.entity_type == "organization"
                else "person_aliases"
            )
            owner_field = (
                "organization_id"
                if record.entity_type == "organization"
                else "person_id"
            )
            names.extend(
                row["alias"]
                for row in state[alias_table]
                if row[owner_field] == owner_id
            )
        matched_ids = set()
        for name in names:
            matched_ids.update(
                identity_indexes[record.entity_type].get(
                    normalize_identity_name(name), set()
                )
            )
        matched_ids.discard(owner_id)
        if matched_ids:
            return "规范名称与现有身份或别名匹配，但稳定 ID 不同：" + ", ".join(sorted(matched_ids))

    if record.entity_type in {"organization_alias", "person_alias"}:
        namespace = "organization" if record.entity_type.startswith("organization") else "person"
        owner_field = "organization_id" if namespace == "organization" else "person_id"
        owner_id = record.values[owner_field]
        matched_ids = set(
            identity_indexes[namespace].get(
                normalize_identity_name(record.values["alias"]), set()
            )
        )
        matched_ids.discard(owner_id)
        if matched_ids:
            return "别名已经指向其他身份：" + ", ".join(sorted(matched_ids))

    if record.entity_type == "source_entry" and record.values.get("url") is not None:
        for row in state["source_entries"]:
            unique_key = (row.get("source_id"), row.get("entry_type"), row.get("url"))
            candidate_key = (
                record.values.get("source_id"),
                record.values.get("entry_type"),
                record.values.get("url"),
            )
            if unique_key == candidate_key and row.get("id") != record.values.get("id"):
                return f"相同来源、类型和 URL 已由入口 {row['id']} 使用"
    return None


def _build_preview(
    connection: sqlite3.Connection,
    seed: dict[str, Any],
    validation: ValidationResult,
) -> CatalogImportReport:
    if not validation.is_valid:
        return CatalogImportReport(
            str(seed.get("seed_id", "")),
            str(seed.get("status", "")),
            validation,
            [],
        )

    repository = CatalogRepository(connection)
    state = repository.load_state()
    identity_indexes = {
        entity_type: _identity_index(state, entity_type)
        for entity_type in ("organization", "person", "source")
    }
    indexes: dict[tuple[str, tuple[str, ...]], dict[tuple[Any, ...], dict[str, Any]]] = {}
    operations = []

    for record in iter_catalog_records(seed):
        index_key = (record.table, record.key_fields)
        if index_key not in indexes:
            indexes[index_key] = _state_index(state[record.table], record.key_fields)
        existing = indexes[index_key].get(record.key)
        if existing is not None:
            changes = repository.changed_fields(record, existing)
            if changes:
                operations.append(
                    PreviewOperation(
                        record.entity_type,
                        record.key_text,
                        "update_preview",
                        True,
                        "数据库已有同一稳定键，但内容不同；为保护用户修改，本轮不自动覆盖。",
                        changes,
                        record.metadata,
                    )
                )
            else:
                operations.append(
                    PreviewOperation(
                        record.entity_type,
                        record.key_text,
                        "unchanged",
                        False,
                        "数据库记录与种子可持久化字段一致。",
                        metadata=record.metadata,
                    )
                )
            continue

        conflict_reason = _alternative_conflict(record, state, identity_indexes)
        if conflict_reason:
            operations.append(
                PreviewOperation(
                    record.entity_type,
                    record.key_text,
                    "conflict",
                    True,
                    conflict_reason,
                    metadata=record.metadata,
                )
            )
            continue

        reason = "数据库中不存在，将在显式 apply 时创建。"
        if record.action_hint == "map_existing":
            reason = "复用 data/registries/sources.v4.json 的来源身份，并映射到 V4 数据表。"
        elif record.action_hint == "create_from_split":
            reason = "根据已确认拆分操作创建新的来源身份。"
        elif record.action_hint == "intentionally_unbound":
            reason = "创建已确认暂不绑定参与者的补充来源。"
        operations.append(
            PreviewOperation(
                record.entity_type,
                record.key_text,
                record.action_hint,
                False,
                reason,
                metadata=record.metadata,
            )
        )

    return CatalogImportReport(
        str(seed.get("seed_id", "")),
        str(seed.get("status", "")),
        validation,
        operations,
    )


def preview_catalog_import(
    connection: sqlite3.Connection,
    seed: dict[str, Any],
    source_registry: dict[str, Any] | None = None,
) -> CatalogImportReport:
    """只读取数据库并返回操作计划，不创建表也不写入业务数据。"""

    validation = validate_catalog_seed(seed, source_registry)
    return _build_preview(connection, seed, validation)


def apply_catalog_seed(
    connection: sqlite3.Connection,
    seed: dict[str, Any],
    source_registry: dict[str, Any] | None = None,
) -> CatalogImportReport:
    """在一笔事务中应用已通过预览的种子，失败时整批回滚。"""

    validation = validate_catalog_seed(seed, source_registry)
    if not validation.is_valid:
        raise CatalogImportBlocked(
            CatalogImportReport(
                str(seed.get("seed_id", "")),
                str(seed.get("status", "")),
                validation,
                [],
            )
        )
    if connection.in_transaction:
        raise RuntimeError("apply_catalog_seed 需要一个尚未开启事务的连接。")

    try:
        connection.execute("BEGIN IMMEDIATE")
        report = _build_preview(connection, seed, validation)
        if not report.can_apply:
            raise CatalogImportBlocked(report)

        repository = CatalogRepository(connection)
        inserted = repository.insert_records(iter_catalog_records(seed))
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError(
                "名册写入后出现外键错误："
                f"{[tuple(row) for row in foreign_key_errors]}"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    report.applied = True
    report.inserted = inserted
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验、预览或显式写入 OrbitAI V4.1 名册种子。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--seed", default=str(DEFAULT_SEED_FILE))
        command_parser.add_argument(
            "--source-registry",
            default=str(DEFAULT_SOURCE_REGISTRY_FILE),
        )
        command_parser.add_argument("--database", default=str(DEFAULT_DATABASE_FILE))
        command_parser.add_argument(
            "--summary-only",
            action="store_true",
            help="只输出校验和操作数量，不展开每条预览。",
        )

    preview_parser = subparsers.add_parser(
        "preview", help="只读校验并生成导入预览。"
    )
    add_common_arguments(preview_parser)

    apply_parser = subparsers.add_parser(
        "apply", help="显式确认后，以事务幂等写入。"
    )
    add_common_arguments(apply_parser)
    apply_parser.add_argument(
        "--confirm-seed-id",
        required=True,
        help="必须与种子 seed_id 完全一致，防止误写。",
    )
    return parser


def _print_report(report: CatalogImportReport, summary_only: bool) -> None:
    print(
        json.dumps(
            report.to_dict(include_operations=not summary_only),
            ensure_ascii=False,
            indent=2,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        seed = load_json_document(args.seed, "名册种子")
        source_registry = load_json_document(
            args.source_registry, "来源注册表"
        )

        if args.command == "preview":
            database_file = Path(args.database)
            if not database_file.exists():
                raise CatalogSchemaError(
                    "预览不会创建数据库；请先运行 python -m orbitai.migrations up"
                )
            with get_connection(database_file) as connection:
                report = preview_catalog_import(
                    connection, seed, source_registry
                )
            _print_report(report, args.summary_only)
            return 0 if report.can_apply else 2

        if args.confirm_seed_id != seed.get("seed_id"):
            parser.error("--confirm-seed-id 必须与种子 seed_id 完全一致")
        init_db(args.database)
        with get_connection(args.database) as connection:
            report = apply_catalog_seed(connection, seed, source_registry)
        _print_report(report, args.summary_only)
        return 0
    except CatalogImportBlocked as exc:
        _print_report(exc.report, args.summary_only)
        return 2
    except (CatalogDocumentError, CatalogSchemaError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
