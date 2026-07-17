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
