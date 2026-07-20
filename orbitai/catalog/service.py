from pathlib import Path
from typing import Any

from orbitai.catalog.repository import CatalogRepository
from orbitai.core.database import get_connection, init_db


# 四大分组的名称、解释和顺序属于页面展示规则。
# 赛道实际属于哪一组，仍然以数据库中的 segment_kind 为准。
SEGMENT_GROUP_PRESENTATION = (
    {
        "id": "core_capability",
        "name": "核心能力",
        "description": "直接形成模型智能能力的模型、推理、智能体与世界模型赛道。",
    },
    {
        "id": "infrastructure",
        "name": "基础设施",
        "description": "支撑模型训练、部署和运行的数据、芯片、算力与能源等基础条件。",
    },
    {
        "id": "product_application",
        "name": "产品与应用",
        "description": "将 AI 能力转化为工具、终端、机器人和行业应用的产品层。",
    },
    {
        "id": "external_environment",
        "name": "外部环境",
        "description": "影响 AI 产业发展的政策、安全、资本、人才、社区与采用环境。",
    },
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


def _group_values(
    rows: list[dict[str, Any]],
    key_name: str,
    value_name: str | None = None,
) -> dict[str, list[Any]]:
    """把查询结果按实体 ID 归组，避免模板自己处理数据库关系。"""

    grouped: dict[str, list[Any]] = {}
    for row in rows:
        value: Any = row[value_name] if value_name else row
        grouped.setdefault(row[key_name], []).append(value)
    return grouped


def load_industry_catalog(
    industry_slug: str,
    database_file: str | Path | None = None,
) -> dict[str, Any] | None:
    """读取并整理一张产业目录页面所需的全部数据。"""

    init_db(database_file, allow_create=False)

    with get_connection(database_file) as connection:
        repository = CatalogRepository(connection)
        industry = repository.get_industry_by_slug(industry_slug)
        if industry is None:
            return None

        segments = repository.list_industry_segments(industry["id"])
        segments_by_kind: dict[str, list[dict[str, Any]]] = {
            group["id"]: [] for group in SEGMENT_GROUP_PRESENTATION
        }
        built_segments = []

        for segment in segments:
            participant_count = (
                int(segment["organization_count"])
                + int(segment["person_count"])
            )
            segment["participant_count"] = participant_count
            segment["is_built"] = participant_count > 0

            if segment["is_built"]:
                segment["organizations"] = (
                    repository.list_segment_organizations(segment["id"])
                )
                segment["people"] = repository.list_segment_people(
                    segment["id"]
                )
                built_segments.append(segment)
            else:
                segment["organizations"] = []
                segment["people"] = []

            group_segments = segments_by_kind.get(segment["segment_kind"])
            if group_segments is None:
                raise ValueError(
                    "数据库中出现页面尚未认识的赛道分组："
                    f"{segment['segment_kind']}"
                )
            group_segments.append(segment)

        groups = []
        for presentation in SEGMENT_GROUP_PRESENTATION:
            group_segments = segments_by_kind[presentation["id"]]
            groups.append(
                {
                    **presentation,
                    "segments": group_segments,
                    "segment_count": len(group_segments),
                    "built_count": sum(
                        1 for item in group_segments if item["is_built"]
                    ),
                }
            )

    return {
        "industry": industry,
        "groups": groups,
        "group_count": len(groups),
        "segment_count": len(segments),
        "built_count": len(built_segments),
        "pending_count": len(segments) - len(built_segments),
        "built_segments": built_segments,
    }


def load_organization_directory(
    database_file: str | Path | None = None,
) -> dict[str, Any]:
    """读取企业与机构档案总入口所需的真实名册数据。"""

    init_db(database_file, allow_create=False)
    with get_connection(database_file) as connection:
        repository = CatalogRepository(connection)
        organizations = repository.list_active_organizations()
        aliases = _group_values(
            repository.list_organization_aliases(),
            "organization_id",
            "alias",
        )

    for organization in organizations:
        organization["aliases"] = aliases.get(organization["id"], [])
        organization["type_label"] = ORGANIZATION_TYPE_LABELS.get(
            organization["organization_type"],
            "其他组织",
        )

    return {
        "organizations": organizations,
        "organization_count": len(organizations),
    }


def load_person_directory(
    database_file: str | Path | None = None,
) -> dict[str, Any]:
    """读取人物档案总入口所需的真实名册与当前任职数据。"""

    init_db(database_file, allow_create=False)
    with get_connection(database_file) as connection:
        repository = CatalogRepository(connection)
        people = repository.list_active_people()
        aliases = _group_values(
            repository.list_person_aliases(),
            "person_id",
            "alias",
        )
        roles = _group_values(
            repository.list_current_person_roles(),
            "person_id",
        )

    for person in people:
        person["aliases"] = aliases.get(person["id"], [])
        person["current_roles"] = roles.get(person["id"], [])

    return {
        "people": people,
        "person_count": len(people),
    }


def load_segment_profile(
    segment_slug: str,
    database_file: str | Path | None = None,
) -> dict[str, Any] | None:
    """读取一张赛道页骨架；尚无事件时只展示已经确认的名册。"""

    init_db(database_file, allow_create=False)
    with get_connection(database_file) as connection:
        repository = CatalogRepository(connection)
        segment = repository.get_segment_by_slug(segment_slug)
        if segment is None:
            return None

        organizations = repository.list_segment_organizations(segment["id"])
        people = repository.list_segment_people(segment["id"])
        organization_aliases = _group_values(
            repository.list_organization_aliases(),
            "organization_id",
            "alias",
        )
        person_aliases = _group_values(
            repository.list_person_aliases(),
            "person_id",
            "alias",
        )

    for organization in organizations:
        organization["aliases"] = organization_aliases.get(
            organization["id"], []
        )
        organization["type_label"] = ORGANIZATION_TYPE_LABELS.get(
            organization["organization_type"],
            "其他组织",
        )
    for person in people:
        person["aliases"] = person_aliases.get(person["id"], [])

    participant_count = len(organizations) + len(people)
    segment["is_built"] = participant_count > 0
    segment["group_name"] = next(
        (
            item["name"]
            for item in SEGMENT_GROUP_PRESENTATION
            if item["id"] == segment["segment_kind"]
        ),
        segment["segment_kind"],
    )
    return {
        "segment": segment,
        "organizations": organizations,
        "people": people,
        "participant_count": participant_count,
    }
