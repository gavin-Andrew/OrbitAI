from datetime import datetime, timezone

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
        "error_type": "",
        "failed_at": "",
        "retry_count": 0,
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
