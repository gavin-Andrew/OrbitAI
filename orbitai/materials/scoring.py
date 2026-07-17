"""材料综合评分与精选排序。"""

from orbitai.core.config import (
    AI_SCORE_KEYS,
    FINAL_SCORE_WEIGHTS,
    FEATURED_SCORE_THRESHOLD,
    FEATURED_MIN_ITEMS,
    FEATURED_MAX_ITEMS,
)


def normalize_score(value, default=50):
    """
    把 AI 返回的单个评分清洗成 0 到 100 之间的数字。
    """
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = float(default)

    if score < 0:
        score = 0.0

    if score > 100:
        score = 100.0

    return round(score, 1)


def normalize_ai_scores(scores):
    """
    校验并清洗 AI 返回的多维评分。
    确保 scores 一定包含 V2.3/V2.5 需要的五个维度。
    """
    if not isinstance(scores, dict):
        scores = {}

    normalized_scores = {}

    for key in AI_SCORE_KEYS:
        normalized_scores[key] = normalize_score(scores.get(key), default=50)

    return normalized_scores


def calculate_final_score(scores):
    """
    根据多维评分计算综合分。
    综合分由代码计算，不直接相信 AI 输出。
    """
    normalized_scores = normalize_ai_scores(scores)

    final_score = 0.0

    for key, weight in FINAL_SCORE_WEIGHTS.items():
        final_score += normalized_scores[key] * weight

    return round(final_score, 1)


def get_item_final_score(item):
    """
    获取单条信息的综合分。
    如果没有合法 final_score，就返回 0。
    """
    try:
        return float(item.get("ai", {}).get("final_score", 0))
    except (TypeError, ValueError):
        return 0.0


def sort_items_by_score(items):
    """
    按综合分从高到低排序。
    精选页使用这个排序。
    """
    return sorted(
        items,
        key=get_item_final_score,
        reverse=True,
    )


def get_featured_items(items):
    """
    从全部信息中筛选精选信息。

    规则：
    1. 优先选择 final_score >= FEATURED_SCORE_THRESHOLD 的信息；
    2. 如果数量少于 FEATURED_MIN_ITEMS，则用综合分最高的前几条兜底；
    3. 最多展示 FEATURED_MAX_ITEMS 条。
    """
    scored_items = [
        item for item in items
        if get_item_final_score(item) > 0
    ]

    sorted_by_score = sort_items_by_score(scored_items)

    featured_items = [
        item for item in sorted_by_score
        if get_item_final_score(item) >= FEATURED_SCORE_THRESHOLD
    ]

    if len(featured_items) < FEATURED_MIN_ITEMS:
        featured_items = sorted_by_score[:FEATURED_MIN_ITEMS]

    return featured_items[:FEATURED_MAX_ITEMS]
