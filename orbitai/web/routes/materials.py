"""信息材料页面路由。"""

from fastapi import APIRouter, Request

from orbitai.html_generator import get_display_category, get_today_items
from orbitai.scoring import get_featured_items, sort_items_by_score
from orbitai.web.templating import templates
from orbitai.web.view_helpers import (
    build_template_context,
    is_ai_processed_for_display,
    load_articles_from_db,
    sort_items_by_time,
)


router = APIRouter()


@router.get("/")
def home(request: Request):
    """保留现有信息流首页。"""

    items = sort_items_by_time(load_articles_from_db())
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
        name="materials/feed.html",
        context=context,
    )


@router.get("/materials")
def materials_home(request: Request):
    """信息材料模块的新入口。"""

    return home(request)


@router.get("/index.html")
def index_html_page(request: Request):
    """兼容旧静态首页地址。"""

    return home(request)


@router.get("/featured")
def featured_page(request: Request):
    """显示按综合分排序的精选信息。"""

    items = sort_items_by_score(get_featured_items(load_articles_from_db()))
    current_ai_processed_count = sum(
        1 for item in items if is_ai_processed_for_display(item)
    )
    context = build_template_context(
        request=request,
        items=items,
        page_title="OrbitAI Featured",
        page_subtitle="精选 AI 信息｜按综合分排序",
        stat_label="精选信息数",
        active_page="featured",
    )
    context["current_ai_processed_count"] = current_ai_processed_count

    return templates.TemplateResponse(
        request=request,
        name="materials/feed.html",
        context=context,
    )


@router.get("/materials/featured")
def materials_featured_page(request: Request):
    """精选信息模块的新地址。"""

    return featured_page(request)


@router.get("/featured.html")
def featured_html_page(request: Request):
    """兼容旧静态精选页地址。"""

    return featured_page(request)


@router.get("/daily")
def daily_page(request: Request):
    """显示按分类组织的每日信息简报。"""

    items = sort_items_by_score(get_today_items(load_articles_from_db()))
    current_ai_processed_count = sum(
        1 for item in items if is_ai_processed_for_display(item)
    )
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
            section = {"category": category, "items": []}
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
    context["current_ai_processed_count"] = current_ai_processed_count

    return templates.TemplateResponse(
        request=request,
        name="materials/daily.html",
        context=context,
    )


@router.get("/materials/daily")
def materials_daily_page(request: Request):
    """每日简报模块的新地址。"""

    return daily_page(request)


@router.get("/daily.html")
def daily_html_page(request: Request):
    """兼容旧静态每日简报地址。"""

    return daily_page(request)
