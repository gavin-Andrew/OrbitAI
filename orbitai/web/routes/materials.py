"""信息材料页面路由。"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

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


def render_materials_home(request: Request):
    """渲染信息材料首页。"""

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


@router.get("/")
def home():
    """临时重定向到当前 AI 产业目录规范地址。"""

    return RedirectResponse(
        url="/industries/artificial-intelligence",
        status_code=307,
    )


@router.get("/materials")
def materials_home(request: Request):
    """信息材料模块的规范入口。"""

    return render_materials_home(request)


@router.get("/index.html")
def index_html_page():
    """把旧静态首页地址重定向到材料模块。"""

    return RedirectResponse(url="/materials", status_code=307)


def render_featured_page(request: Request):
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
    """精选信息模块的规范地址。"""

    return render_featured_page(request)


@router.get("/featured")
def legacy_featured_page():
    """把旧精选页地址重定向到材料模块。"""

    return RedirectResponse(url="/materials/featured", status_code=307)


@router.get("/featured.html")
def featured_html_page():
    """把旧静态精选页地址重定向到材料模块。"""

    return RedirectResponse(url="/materials/featured", status_code=307)


def render_daily_page(request: Request):
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
    """每日简报模块的规范地址。"""

    return render_daily_page(request)


@router.get("/daily")
def legacy_daily_page():
    """把旧每日简报地址重定向到材料模块。"""

    return RedirectResponse(url="/materials/daily", status_code=307)


@router.get("/daily.html")
def daily_html_page():
    """把旧静态每日简报地址重定向到材料模块。"""

    return RedirectResponse(url="/materials/daily", status_code=307)
