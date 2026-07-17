"""等待阶段 5 清退的旧 data.json 兼容读写。"""

import json

from orbitai.core.config import DATA_FILE
from orbitai.materials.fields import migrate_item_to_v2


def load_existing_data():
    """
    读取已经存在的 data.json。
    如果 data.json 是旧结构，就自动迁移到 V2.x 结构。
    """
    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            print("⚠️ data.json 格式不是列表，已暂时忽略旧数据。")
            return []

        migrated_data = []

        for item in data:
            if isinstance(item, dict):
                migrated_data.append(migrate_item_to_v2(item))

        return migrated_data

    except json.JSONDecodeError:
        print("⚠️ data.json 不是有效 JSON，已暂时忽略旧数据。")
        return []


def save_data(items):
    """
    把信息保存到 data.json。
    ensure_ascii=False 可以保证中文正常显示。
    indent=2 可以让 JSON 文件更易读。
    """
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(items, file, ensure_ascii=False, indent=2)


def get_existing_links(items):
    """
    用 link 作为去重依据。
    已经保存过的链接，下次就不重复保存。
    """
    return {item.get("link") for item in items if item.get("link")}
