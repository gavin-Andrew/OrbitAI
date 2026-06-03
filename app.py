from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from orbitai.data_utils import load_existing_data
from orbitai.ai_processor import item_is_ai_complete
from orbitai.scoring import get_featured_items, sort_items_by_score
from orbitai.html_generator import (
    get_today_items,
    get_display_title,
    get_display_summary,
    get_display_category,
)
from orbitai.text_utils import clean_html, truncate_text


app = FastAPI(
    title="OrbitAI",
    description="OrbitAI V3.1 - Local FastAPI Service with Jinja2 Templates",
    version="3.1.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


def sort_items_by_time(items: list[dict]) -> list[dict]:
    """
    按 fetched_at 倒序排列，首页使用。
    """
    return sorted(
        items,
        key=lambda item: item.get("fetched_at", ""),
        reverse=True,
    )


def get_ai_final_score(item: dict) -> float:
    """
    安全读取单条信息的 final_score。
    """
    try:
        return float(item.get("ai", {}).get("final_score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def get_item_tags(item: dict) -> list[str]:
    """
    安全读取标签列表。
    """
    tags = item.get("ai", {}).get("tags", [])

    if not isinstance(tags, list):
        return []

    return [
        str(tag).strip()
        for tag in tags
        if str(tag).strip()
    ]


def get_display_score(item: dict) -> str:
    """
    页面展示用综合分。
    """
    score = item.get("ai", {}).get("final_score")

    if score is None:
        return ""

    try:
        return str(round(float(score), 1))
    except (TypeError, ValueError):
        return ""


def get_short_summary(item: dict, max_length: int = 240) -> str:
    """
    页面展示用摘要。
    """
    return truncate_text(clean_html(get_display_summary(item)), max_length)


def build_search_text(item: dict) -> str:
    """
    构造前端搜索用文本。
    """
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
    """
    构造来源、分类、标签筛选选项。
    """
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

    tags = sorted(all_tags)

    return {
        "sources": sources,
        "categories": categories,
        "tags": tags,
    }


def build_status(items: list[dict]) -> dict:
    """
    生成 OrbitAI 当前运行状态摘要。
    """
    total_count = len(items)
    ai_processed_count = sum(1 for item in items if item_is_ai_complete(item))
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

    for item in items:
        source = str(item.get("source", "未知来源")).strip() or "未知来源"
        sources[source] = sources.get(source, 0) + 1

    categories = {}

    for item in items:
        category = get_display_category(item)
        categories[category] = categories.get(category, 0) + 1

    return {
        "version": "V3.1",
        "mode": "Local FastAPI Service with Jinja2 Templates",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": total_count,
        "ai_processed_count": ai_processed_count,
        "ai_unprocessed_count": total_count - ai_processed_count,
        "featured_count": featured_count,
        "today_count": today_count,
        "ai_failed_count": len(ai_failed_items),
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
    """
    构造模板渲染需要的通用上下文。
    """
    filter_options = build_filter_options(items)
    ai_processed_count = sum(1 for item in items if item_is_ai_complete(item))

    return {
        "request": request,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "stat_label": stat_label,
        "active_page": active_page,
        "items": items,
        "total_count": len(items),
        "ai_processed_count": ai_processed_count,
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
    }


@app.get("/")
def home(request: Request):
    """
    首页。
    V3.1 开始改为 Jinja2 模板动态渲染。
    """
    items = sort_items_by_time(load_existing_data())

    context = build_template_context(
        request=request,
        items=items,
        page_title="OrbitAI",
        page_subtitle="Personal AI Information Radar",
        stat_label="总信息数",
        active_page="index",
    )

    return templates.TemplateResponse(
        request=request,
        name="feed.html",
        context=context,
    )


@app.get("/index.html")
def index_html_page(request: Request):
    """
    兼容旧静态 HTML 导航链接。
    """
    return home(request)


@app.get("/featured")
def featured_page(request: Request):
    """
    精选信息页。
    V3.1 使用模板动态渲染。
    """
    items = sort_items_by_score(get_featured_items(load_existing_data()))

    context = build_template_context(
        request=request,
        items=items,
        page_title="OrbitAI Featured",
        page_subtitle="精选 AI 信息｜按综合分排序",
        stat_label="精选信息数",
        active_page="featured",
    )

    return templates.TemplateResponse(
        request=request,
        name="feed.html",
        context=context,
    )


@app.get("/featured.html")
def featured_html_page(request: Request):
    """
    兼容旧静态 HTML 导航链接。
    """
    return featured_page(request)


@app.get("/daily")
def daily_page(request: Request):
    """
    每日简报页。
    V3.1 使用模板动态渲染。
    """
    items = sort_items_by_score(get_today_items(load_existing_data()))

    grouped_sections = []

    for item in items:
        category = get_display_category(item)

        section = next(
            (
                existing_section
                for existing_section in grouped_sections
                if existing_section["category"] == category
            ),
            None,
        )

        if section is None:
            section = {
                "category": category,
                "items": [],
            }
            grouped_sections.append(section)

        section["items"].append(item)

    context = build_template_context(
        request=request,
        items=items,
        page_title="OrbitAI Daily",
        page_subtitle="每日 AI 信息简报",
        stat_label="今日新增",
        active_page="daily",
    )

    context["grouped_sections"] = grouped_sections

    return templates.TemplateResponse(
        request=request,
        name="daily.html",
        context=context,
    )


@app.get("/daily.html")
def daily_html_page(request: Request):
    """
    兼容旧静态 HTML 导航链接。
    """
    return daily_page(request)


@app.get("/api/items")
def api_items():
    """
    返回全部信息 JSON。
    """
    items = sort_items_by_time(load_existing_data())

    return JSONResponse(content=jsonable_encoder(items))


@app.get("/api/featured")
def api_featured():
    """
    返回精选信息 JSON。
    """
    items = load_existing_data()
    featured_items = get_featured_items(items)

    return JSONResponse(content=jsonable_encoder(featured_items))


@app.get("/api/daily")
def api_daily():
    """
    返回今日新增信息 JSON。
    """
    items = load_existing_data()
    today_items = sort_items_by_score(get_today_items(items))

    return JSONResponse(content=jsonable_encoder(today_items))


@app.get("/api/status")
def api_status():
    """
    返回当前 OrbitAI 状态。
    """
    items = load_existing_data()
    status = build_status(items)

    return JSONResponse(content=jsonable_encoder(status))


@app.get("/api/top")
def api_top(limit: int = 10):
    """
    返回综合分最高的信息。
    默认返回前 10 条。
    """
    items = load_existing_data()
    sorted_items = sort_items_by_score(items)

    limit = max(1, min(limit, 50))

    return JSONResponse(content=jsonable_encoder(sorted_items[:limit]))


@app.get("/health")
def health_check():
    """
    健康检查接口。
    """
    return {
        "status": "ok",
        "service": "OrbitAI",
        "version": "V3.1",
    }
