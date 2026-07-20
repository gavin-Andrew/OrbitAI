"""V4.1 名册人工修改、冲突检测、事务保存与修改记录。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from orbitai.catalog.import_service import normalize_identity_name
from orbitai.catalog.repository import CatalogRepository
from orbitai.core.database import get_connection, init_db


class CatalogEditValidationError(ValueError):
    """用户提交的名册修改不符合安全编辑规则。"""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("；".join(errors))


class CatalogEditConflict(RuntimeError):
    """页面读取后数据库已经变化，拒绝覆盖较新的内容。"""

    def __init__(self, current: dict[str, Any]):
        self.current = current
        super().__init__("记录已经被其他操作修改，请刷新后重新预览。")


class CatalogEditNotFound(LookupError):
    """用户请求编辑的名册对象不存在。"""


ENTITY_CONFIG = {
    "organization": {
        "label": "组织",
        "table": "organizations",
        "alias_table": "organization_aliases",
        "alias_owner_field": "organization_id",
        "fields": (
            "name",
            "organization_type",
            "homepage_url",
            "description",
            "status",
        ),
        "statuses": ("active", "inactive", "acquired", "closed", "archived"),
    },
    "person": {
        "label": "人物",
        "table": "people",
        "alias_table": "person_aliases",
        "alias_owner_field": "person_id",
        "fields": ("name", "description", "status"),
        "statuses": ("active", "inactive", "archived"),
    },
}

ORGANIZATION_TYPES = (
    "ai_company",
    "corporate_ai_lab",
    "company",
    "nonprofit",
    "research_institute",
    "university",
    "government",
    "other",
)

ORGANIZATION_TYPE_LABELS = {
    "ai_company": "AI 企业",
    "corporate_ai_lab": "企业 AI 研究机构",
    "company": "企业",
    "nonprofit": "非营利机构",
    "research_institute": "研究机构",
    "university": "高校",
    "government": "政府机构",
    "other": "其他组织",
}

STATUS_LABELS = {
    "active": "活动",
    "inactive": "暂不活动",
    "acquired": "已被收购",
    "closed": "已关闭",
    "archived": "已归档",
}

FIELD_LABELS = {
    "name": "规范名称",
    "organization_type": "组织类型",
    "homepage_url": "官方网站",
    "description": "简介",
    "status": "状态",
    "aliases": "别名",
}


def _revision_payload(state: dict[str, Any]) -> dict[str, Any]:
    """选出真正影响并发判断的稳定字段。"""

    return {
        key: value
        for key, value in state.items()
        if key not in {"revision", "type_label", "status_label"}
    }


def _calculate_revision(state: dict[str, Any]) -> str:
    serialized = json.dumps(
        _revision_payload(state),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _load_entity_state(
    repository: CatalogRepository,
    entity_type: str,
    entity_id: str,
) -> dict[str, Any]:
    config = ENTITY_CONFIG.get(entity_type)
    if config is None:
        raise CatalogEditValidationError([f"不支持的对象类型：{entity_type}"])

    row = repository.get_entity_for_edit(entity_type, entity_id)
    if row is None:
        raise CatalogEditNotFound(f"名册对象不存在：{entity_type}:{entity_id}")

    state = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        **{field_name: row[field_name] for field_name in config["fields"]},
        "aliases": repository.list_entity_aliases_for_edit(
            entity_type,
            entity_id,
        ),
        "updated_at": row["updated_at"],
    }
    state["revision"] = _calculate_revision(state)
    state["type_label"] = config["label"]
    state["status_label"] = STATUS_LABELS.get(state["status"], state["status"])
    return state


def _validate_text(
    value: Any,
    label: str,
    *,
    required: bool,
    max_length: int,
    errors: list[str],
) -> str:
    if not isinstance(value, str):
        errors.append(f"{label}必须是文本。")
        return ""
    normalized = value.strip()
    if required and not normalized:
        errors.append(f"{label}不能为空。")
    if len(normalized) > max_length:
        errors.append(f"{label}不能超过 {max_length} 个字符。")
    return normalized


def _validate_aliases(value: Any, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append("别名必须是文本列表。")
        return []

    aliases = []
    for index, alias in enumerate(value):
        normalized = _validate_text(
            alias,
            f"第 {index + 1} 个别名",
            required=True,
            max_length=200,
            errors=errors,
        )
        if normalized:
            aliases.append(normalized)
    return sorted(aliases, key=lambda item: item.casefold())


def _validate_homepage(value: Any, errors: list[str]) -> str | None:
    if value in (None, ""):
        return None
    homepage = _validate_text(
        value,
        "官方网站",
        required=False,
        max_length=2000,
        errors=errors,
    )
    parsed = urlparse(homepage)
    if homepage and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
        errors.append("官方网站必须是完整的 http 或 https 地址。")
    return homepage or None


def _validate_identity_namespace(
    repository: CatalogRepository,
    entity_type: str,
    entity_id: str,
    name: str,
    aliases: list[str],
    errors: list[str],
) -> None:
    """阻止规范名称或别名与另一个稳定身份发生碰撞。"""

    config = ENTITY_CONFIG[entity_type]
    proposed_names = [("规范名称", name)] + [
        (f"别名“{alias}”", alias) for alias in aliases
    ]
    proposed_index: dict[str, str] = {}
    for label, value in proposed_names:
        key = normalize_identity_name(value)
        previous = proposed_index.get(key)
        if previous is not None:
            errors.append(f"{label}与本对象的{previous}重复。")
        else:
            proposed_index[key] = label

    owners = repository.fetch_table(config["table"])
    alias_rows = repository.fetch_table(config["alias_table"])
    owner_names = {row["id"]: row["name"] for row in owners}
    occupied: dict[str, tuple[str, str]] = {}
    for row in owners:
        if row["id"] != entity_id:
            occupied[normalize_identity_name(row["name"])] = (
                row["id"],
                row["name"],
            )
    for row in alias_rows:
        owner_id = row[config["alias_owner_field"]]
        if owner_id != entity_id:
            occupied[normalize_identity_name(row["alias"])] = (
                owner_id,
                owner_names.get(owner_id, owner_id),
            )

    for label, value in proposed_names:
        conflict = occupied.get(normalize_identity_name(value))
        if conflict is not None:
            errors.append(
                f"{label}已经属于另一个{config['label']}："
                f"{conflict[1]}（{conflict[0]}）。"
            )


def _prepare_edit(
    repository: CatalogRepository,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CatalogEditValidationError(["请求内容必须是对象。"])

    entity_type = payload.get("entity_type")
    entity_id = payload.get("entity_id")
    expected_revision = payload.get("expected_revision")
    if entity_type not in ENTITY_CONFIG:
        raise CatalogEditValidationError(["请选择组织或人物。"])
    if not isinstance(entity_id, str) or not entity_id:
        raise CatalogEditValidationError(["缺少稳定对象 ID。"])
    if not isinstance(expected_revision, str) or not expected_revision:
        raise CatalogEditValidationError(["缺少页面读取版本，请刷新后重试。"])

    current = _load_entity_state(repository, entity_type, entity_id)
    if expected_revision != current["revision"]:
        raise CatalogEditConflict(current)

    config = ENTITY_CONFIG[entity_type]
    values = payload.get("values")
    if not isinstance(values, dict):
        raise CatalogEditValidationError(["缺少待修改字段。"])

    required_fields = set(config["fields"]) | {"aliases"}
    missing = sorted(required_fields - set(values))
    unexpected = sorted(set(values) - required_fields)
    errors = []
    if missing:
        errors.append("缺少字段：" + "、".join(missing) + "。")
    if unexpected:
        errors.append("出现不允许修改的字段：" + "、".join(unexpected) + "。")

    name = _validate_text(
        values.get("name"),
        "规范名称",
        required=True,
        max_length=200,
        errors=errors,
    )
    description = _validate_text(
        values.get("description"),
        "简介",
        required=False,
        max_length=10000,
        errors=errors,
    )
    aliases = _validate_aliases(values.get("aliases"), errors)
    status = values.get("status")
    if status not in config["statuses"]:
        errors.append("对象状态不在允许范围内。")

    proposed = {
        **current,
        "name": name,
        "description": description,
        "status": status,
        "aliases": aliases,
    }
    if entity_type == "organization":
        organization_type = values.get("organization_type")
        if organization_type not in ORGANIZATION_TYPES:
            errors.append("组织类型不在允许范围内。")
        proposed["organization_type"] = organization_type
        proposed["homepage_url"] = _validate_homepage(
            values.get("homepage_url"),
            errors,
        )

    if name:
        _validate_identity_namespace(
            repository,
            entity_type,
            entity_id,
            name,
            aliases,
            errors,
        )
    if errors:
        raise CatalogEditValidationError(errors)

    changes = {}
    for field_name in (*config["fields"], "aliases"):
        if current[field_name] != proposed[field_name]:
            changes[field_name] = {
                "label": FIELD_LABELS[field_name],
                "before": current[field_name],
                "after": proposed[field_name],
            }

    action = "update"
    if current["status"] != "archived" and proposed["status"] == "archived":
        action = "archive"
    elif current["status"] == "archived" and proposed["status"] != "archived":
        action = "restore"

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "expected_revision": expected_revision,
        "current": current,
        "proposed": proposed,
        "changes": changes,
        "action": action,
    }


def _parse_change_log(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    logs = []
    for row in rows:
        changes = json.loads(row.pop("changed_fields_json"))
        before = json.loads(row.pop("before_json"))
        after = json.loads(row.pop("after_json"))
        logs.append(
            {
                **row,
                "changes": changes,
                "before": before,
                "after": after,
                "entity_type_label": ENTITY_CONFIG[row["entity_type"]]["label"],
            }
        )
    return logs


def load_catalog_management_data(
    database_file: str | Path | None = None,
) -> dict[str, Any]:
    """读取独立管理页所需的对象快照、选项与最近修改记录。"""

    init_db(database_file, allow_create=False)
    with get_connection(database_file) as connection:
        repository = CatalogRepository(connection)
        organizations = [
            _load_entity_state(repository, "organization", row["id"])
            for row in repository.fetch_table("organizations")
        ]
        people = [
            _load_entity_state(repository, "person", row["id"])
            for row in repository.fetch_table("people")
        ]
        change_log = _parse_change_log(repository.list_catalog_change_log())

    organizations.sort(key=lambda item: item["name"].casefold())
    people.sort(key=lambda item: item["name"].casefold())
    return {
        "entities": organizations + people,
        "organization_count": len(organizations),
        "person_count": len(people),
        "change_log": change_log,
        "options": {
            "organization_types": [
                {"value": value, "label": ORGANIZATION_TYPE_LABELS[value]}
                for value in ORGANIZATION_TYPES
            ],
            "statuses": {
                entity_type: [
                    {"value": value, "label": STATUS_LABELS[value]}
                    for value in config["statuses"]
                ]
                for entity_type, config in ENTITY_CONFIG.items()
            },
        },
    }


def preview_catalog_edit(
    payload: dict[str, Any],
    database_file: str | Path | None = None,
) -> dict[str, Any]:
    """只计算差异与冲突，不修改数据库。"""

    init_db(database_file, allow_create=False)
    with get_connection(database_file) as connection:
        prepared = _prepare_edit(CatalogRepository(connection), payload)
    return {
        **prepared,
        "has_changes": bool(prepared["changes"]),
    }


def save_catalog_edit(
    payload: dict[str, Any],
    database_file: str | Path | None = None,
) -> dict[str, Any]:
    """重新检查冲突，并在同一 SQLite 事务中保存业务数据和修改记录。"""

    reason_errors: list[str] = []
    change_reason = _validate_text(
        payload.get("change_reason") if isinstance(payload, dict) else None,
        "修改原因",
        required=True,
        max_length=500,
        errors=reason_errors,
    )
    if len(change_reason) < 3:
        reason_errors.append("修改原因至少需要 3 个字符。")
    if reason_errors:
        raise CatalogEditValidationError(reason_errors)

    init_db(database_file, allow_create=False)
    with get_connection(database_file) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            repository = CatalogRepository(connection)
            prepared = _prepare_edit(repository, payload)
            if not prepared["changes"]:
                raise CatalogEditValidationError(["没有检测到需要保存的修改。"])

            entity_type = prepared["entity_type"]
            entity_id = prepared["entity_id"]
            config = ENTITY_CONFIG[entity_type]
            proposed = prepared["proposed"]
            scalar_values = {
                field_name: proposed[field_name]
                for field_name in config["fields"]
            }
            updated_at = datetime.now(timezone.utc).isoformat()
            repository.update_entity_for_edit(
                entity_type,
                entity_id,
                scalar_values,
                updated_at,
            )
            if "aliases" in prepared["changes"]:
                repository.replace_entity_aliases(
                    entity_type,
                    entity_id,
                    proposed["aliases"],
                )

            after = _load_entity_state(repository, entity_type, entity_id)
            log_id = repository.insert_catalog_change_log(
                entity_type=entity_type,
                entity_id=entity_id,
                action=prepared["action"],
                changes=prepared["changes"],
                before=prepared["current"],
                after=after,
                change_reason=change_reason,
                actor="local_user",
                expected_revision=prepared["expected_revision"],
                result_revision=after["revision"],
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return {
        "ok": True,
        "message": "名册修改和修改记录已在同一事务中保存。",
        "log_id": log_id,
        "action": prepared["action"],
        "changes": prepared["changes"],
        "entity": after,
    }


__all__ = [
    "CatalogEditConflict",
    "CatalogEditNotFound",
    "CatalogEditValidationError",
    "load_catalog_management_data",
    "preview_catalog_edit",
    "save_catalog_edit",
]
