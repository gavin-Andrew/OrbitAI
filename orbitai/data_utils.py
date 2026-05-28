import json
from datetime import datetime, timezone

from orbitai.config import DATA_FILE
from orbitai.text_utils import clean_html


def classify_item(title, summary):
    """
    用简单关键词规则给信息做基础分类。
    后续 AI 分类会优先于规则分类展示。
    """
    text = f"{title} {summary}".lower()

    if any(keyword in text for keyword in ["model", "gpt", "claude", "llm", "language model", "gemini"]):
        return "模型"

    if any(keyword in text for keyword in ["paper", "research", "study", "benchmark", "evaluation"]):
        return "论文/研究"

    if any(keyword in text for keyword in ["product", "app", "release", "launch", "codex", "code"]):
        return "产品"

    if any(keyword in text for keyword in ["company", "funding", "startup", "enterprise", "business"]):
        return "行业"

    return "其他"


def create_empty_ai_fields():
    """
    创建 AI 预留字段。
    """
    return {
        "title_cn": "",
        "summary": "",
        "category": "",
        "tags": [],
        "scores": {
            "importance": None,
            "novelty": None,
            "practical_value": None,
            "learning_value": None,
            "source_authority": None,
        },
        "final_score": None,
        "processed": False,
        "processed_at": "",
        "error": "",
    }


def migrate_item_to_v2(item):
    """
    把旧版数据迁移到 V2.x 数据结构。

    旧字段：
    - summary
    - category

    新字段：
    - summary_original
    - category_rule
    - ai
    """
    title = item.get("title", "无标题")
    summary_original = item.get("summary_original", item.get("summary", ""))
    category_rule = item.get("category_rule", item.get("category", ""))

    if not category_rule:
        category_rule = classify_item(title, summary_original)

    migrated_item = {
        "title": title,
        "source": item.get("source", "未知来源"),
        "link": item.get("link", ""),
        "published": item.get("published", "无发布时间"),
        "summary_original": summary_original,
        "category_rule": category_rule,
        "fetched_at": item.get("fetched_at", datetime.now(timezone.utc).isoformat()),
    }

    existing_ai = item.get("ai")

    if isinstance(existing_ai, dict):
        ai_fields = create_empty_ai_fields()

        for key, value in existing_ai.items():
            if key in ai_fields:
                ai_fields[key] = value

        if not isinstance(ai_fields.get("tags"), list):
            ai_fields["tags"] = []

        if not isinstance(ai_fields.get("scores"), dict):
            ai_fields["scores"] = create_empty_ai_fields()["scores"]

        default_scores = create_empty_ai_fields()["scores"]

        for score_key, default_value in default_scores.items():
            ai_fields["scores"].setdefault(score_key, default_value)

        migrated_item["ai"] = ai_fields
    else:
        migrated_item["ai"] = create_empty_ai_fields()

    return migrated_item


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


def create_new_item(title, source, link, published, summary_original):
    """
    创建一条 V2.x 标准结构的新信息。
    """
    return {
        "title": title,
        "source": source,
        "link": link,
        "published": published,
        "summary_original": clean_html(summary_original),
        "category_rule": classify_item(title, summary_original),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ai": create_empty_ai_fields(),
    }