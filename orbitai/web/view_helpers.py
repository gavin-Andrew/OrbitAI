"""动态页面共享的文章展示与模板上下文辅助函数。"""

from datetime import datetime

from fastapi import Request

from orbitai.materials.ai_processor import item_is_ai_complete
from orbitai.materials.repository import get_all_articles, get_status_summary
from orbitai.materials.scoring import get_featured_items
from orbitai.text_utils import clean_html, truncate_text


def get_display_title(item: dict) -> str:
    """优先返回 AI 中文标题，缺失时回退到原始标题。"""

    title_cn = item.get("ai", {}).get("title_cn", "")
    if title_cn:
        return title_cn
    return item.get("title", "无标题")


def get_display_summary(item: dict) -> str:
    """优先返回 AI 中文摘要，缺失时回退到原始摘要。"""

    ai_summary = item.get("ai", {}).get("summary", "")
    if ai_summary:
        return ai_summary
    return item.get("summary_original", "")


def get_display_category(item: dict) -> str:
    """优先返回 AI 分类，缺失时回退到规则分类。"""

    ai_category = item.get("ai", {}).get("category", "")
    if ai_category:
        return ai_category
    return item.get("category_rule", "其他")


def parse_item_date(item: dict):
    """从抓取时间解析本地日期。"""

    fetched_at = str(item.get("fetched_at", "")).strip()
    if not fetched_at:
        return None

    try:
        parsed_time = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        return parsed_time.astimezone().date()
    except ValueError:
        return None


def get_today_items(items: list[dict]) -> list[dict]:
    """筛选今天抓取的文章。"""

    today = datetime.now().astimezone().date()
    return [item for item in items if parse_item_date(item) == today]


def load_articles_from_db() -> list[dict]:
    """从 SQLite 读取页面和 API 使用的文章。"""

    return get_all_articles()


def sort_items_by_time(items: list[dict]) -> list[dict]:
    """按抓取时间倒序排列。"""

    return sorted(
        items,
        key=lambda item: item.get("fetched_at", ""),
        reverse=True,
    )


def get_ai_final_score(item: dict) -> float:
    """安全读取单条信息的综合分。"""

    try:
        return float(item.get("ai", {}).get("final_score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def is_ai_processed_for_display(item: dict) -> bool:
    """判断文章是否已经完成可展示的 AI 处理。"""

    ai = item.get("ai", {})
    if not isinstance(ai, dict):
        return False
    if ai.get("processed") is True or ai.get("processed") == 1:
        return True

    final_score = ai.get("final_score")
    if final_score is None:
        return False
    try:
        return float(final_score) > 0
    except (TypeError, ValueError):
        return False


def get_item_tags(item: dict) -> list[str]:
    """安全读取标签列表。"""

    tags = item.get("ai", {}).get("tags", [])
    if not isinstance(tags, list):
        return []
    return [
        str(tag).strip()
        for tag in tags
        if str(tag).strip()
    ]


def get_display_score(item: dict) -> str:
    """返回页面展示用综合分。"""

    score = item.get("ai", {}).get("final_score")
    if score is None:
        return ""
    try:
        return str(round(float(score), 1))
    except (TypeError, ValueError):
        return ""


def get_score_level(item: dict) -> str:
    """根据综合分返回页面等级。"""

    score = get_ai_final_score(item)
    if score >= 85:
        return "高价值"
    if score >= 75:
        return "精选"
    if score > 0:
        return "普通"
    return "未评分"


def is_high_score_item(item: dict) -> bool:
    """判断文章是否达到现有高分筛选阈值。"""

    return get_ai_final_score(item) >= 75


def is_today_item(item: dict) -> bool:
    """判断文章是否属于今天新增。"""

    return item in get_today_items([item])


def get_item_time_value(item: dict) -> str:
    """返回前端排序使用的时间值。"""

    return str(item.get("fetched_at") or item.get("published") or "")


def get_original_title(item: dict) -> str:
    """返回原始标题。"""

    return str(item.get("title", "")).strip()


def get_original_summary(item: dict) -> str:
    """返回清洗和截断后的原始摘要。"""

    return truncate_text(clean_html(item.get("summary_original", "")), 600)


def get_short_summary(item: dict, max_length: int = 240) -> str:
    """返回页面展示摘要。"""

    return truncate_text(clean_html(get_display_summary(item)), max_length)


def build_search_text(item: dict) -> str:
    """构造前端搜索使用的规范化文本。"""

    tags = " ".join(get_item_tags(item))
    text = (
        f"{item.get('title', '')} "
        f"{get_display_title(item)} "
        f"{item.get('source', '')} "
        f"{item.get('category_rule', '')} "
        f"{get_display_category(item)} "
        f"{get_short_summary(item, 260)} "
        f"{tags}"
    )
    return text.lower()


def build_filter_options(items: list[dict]) -> dict:
    """构造来源、分类和标签筛选选项。"""

    sources = sorted({
        str(item.get("source", "未知来源")).strip() or "未知来源"
        for item in items
    })
    categories = sorted({
        get_display_category(item)
        for item in items
    })
    all_tags = set()
    for item in items:
        all_tags.update(get_item_tags(item))

    return {
        "sources": sources,
        "categories": categories,
        "tags": sorted(all_tags),
    }


def build_status(items: list[dict]) -> dict:
    """保留原动态页面状态汇总辅助函数。"""

    total_count = len(items)
    ai_processed_count = sum(
        1 for item in items if item_is_ai_complete(item)
    )
    featured_count = len(get_featured_items(items))
    today_count = len(get_today_items(items))
    ai_failed_items = []

    for item in items:
        ai = item.get("ai", {})
        if not isinstance(ai, dict):
            continue
        error = str(ai.get("error", "")).strip()
        error_type = str(ai.get("error_type", "")).strip()
        if error or error_type:
            ai_failed_items.append(item)

    sources = {}
    categories = {}
    for item in items:
        source = str(item.get("source", "未知来源")).strip() or "未知来源"
        sources[source] = sources.get(source, 0) + 1
        category = get_display_category(item)
        categories[category] = categories.get(category, 0) + 1

    scored_items = [
        item for item in items
        if get_ai_final_score(item) > 0
    ]
    avg_score = 0.0
    top_score = 0.0
    if scored_items:
        scores = [get_ai_final_score(item) for item in scored_items]
        avg_score = round(sum(scores) / len(scores), 1)
        top_score = round(max(scores), 1)

    latest_fetched_at = ""
    if items:
        latest_fetched_at = max(
            str(item.get("fetched_at", "")) for item in items
        )

    return {
        "version": "V3.6",
        "mode": "Local Web Interaction Enhanced",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": total_count,
        "ai_processed_count": ai_processed_count,
        "ai_unprocessed_count": total_count - ai_processed_count,
        "featured_count": featured_count,
        "today_count": today_count,
        "high_score_count": sum(
            1 for item in items if is_high_score_item(item)
        ),
        "ai_failed_count": len(ai_failed_items),
        "source_count": len(sources),
        "category_count": len(categories),
        "avg_score": avg_score,
        "top_score": top_score,
        "latest_fetched_at": latest_fetched_at,
        "sources": sources,
        "categories": categories,
    }


def build_template_context(
    request: Request,
    items: list[dict],
    page_title: str,
    page_subtitle: str,
    stat_label: str,
    active_page: str,
) -> dict:
    """构造材料页面共用的 Jinja2 上下文。"""

    filter_options = build_filter_options(items)
    current_ai_processed_count = sum(
        1 for item in items
        if is_ai_processed_for_display(item)
    )
    status = get_status_summary()

    return {
        "request": request,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "stat_label": stat_label,
        "active_page": active_page,
        "items": items,
        "total_count": len(items),
        "ai_processed_count": current_ai_processed_count,
        "current_ai_processed_count": current_ai_processed_count,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": filter_options["sources"],
        "categories": filter_options["categories"],
        "tags": filter_options["tags"],
        "get_display_title": get_display_title,
        "get_display_category": get_display_category,
        "get_item_tags": get_item_tags,
        "get_display_score": get_display_score,
        "get_short_summary": get_short_summary,
        "build_search_text": build_search_text,
        "get_ai_final_score": get_ai_final_score,
        "get_score_level": get_score_level,
        "is_high_score_item": is_high_score_item,
        "is_today_item": is_today_item,
        "get_item_time_value": get_item_time_value,
        "get_original_title": get_original_title,
        "get_original_summary": get_original_summary,
        "status": status,
    }
