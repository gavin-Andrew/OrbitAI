from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from orbitai.repository import get_all_articles, get_status_summary
from orbitai.ai_processor import item_is_ai_complete
from orbitai.scoring import get_featured_items, sort_items_by_score
from orbitai.html_generator import (
    get_today_items,
    get_display_title,
    get_display_summary,
    get_display_category,
)
from orbitai.text_utils import clean_html, truncate_text
from main import (
    run_fetch_only,
    run_ai_only,
    run_regenerate_static,
)


app = FastAPI(
    title="OrbitAI",
    description="OrbitAI V3.6 - Local Web Interaction Enhanced",
    version="3.6.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


def build_admin_response(result: dict):
    """
    V3.6：统一包装后台操作结果。
    """
    status = get_status_summary()

    return JSONResponse(
        content=jsonable_encoder({
            "ok": result.get("ok", False),
            "message": result.get("message", ""),
            "result": result,
            "status": status,
        })
    )


def build_admin_error_response(error: Exception):
    """
    V3.6：统一包装后台操作异常。
    """
    status = get_status_summary()

    return JSONResponse(
        status_code=500,
        content=jsonable_encoder({
            "ok": False,
            "message": "操作失败",
            "result": None,
            "status": status,
            "error": str(error),
        })
    )

def load_articles_from_db() -> list[dict]:
    """
    V3.3.3：从 SQLite 读取文章。
    后续如果需要缓存或异常兜底，也可以集中在这里处理。
    """
    return get_all_articles()


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

def is_ai_processed_for_display(item: dict) -> bool:
    """
    页面统计用：判断一条信息是否已经完成 AI 处理。

    这里优先相信数据库里的 processed 标记；
    如果旧数据没有 processed，但已经有 final_score，也视为已处理。
    """
    ai = item.get("ai", {})

    if not isinstance(ai, dict):
        return False

    if ai.get("processed") is True:
        return True

    if ai.get("processed") == 1:
        return True

    final_score = ai.get("final_score")

    if final_score is None:
        return False

    try:
        return float(final_score) > 0
    except (TypeError, ValueError):
        return False

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


def get_score_level(item: dict) -> str:
    """
    根据综合分生成页面展示用等级。
    """
    score = get_ai_final_score(item)

    if score >= 85:
        return "高价值"
    if score >= 75:
        return "精选"
    if score > 0:
        return "普通"

    return "未评分"


def is_high_score_item(item: dict) -> bool:
    """
    判断是否为高分内容。
    V3.2 前端快捷筛选使用。
    """
    return get_ai_final_score(item) >= 75


def is_today_item(item: dict) -> bool:
    """
    判断是否为今日新增内容。
    V3.2 前端快捷筛选使用。
    """
    return item in get_today_items([item])


def get_item_time_value(item: dict) -> str:
    """
    给前端排序使用的时间值。
    优先使用 fetched_at，其次使用 published。
    """
    return str(item.get("fetched_at") or item.get("published") or "")


def get_original_title(item: dict) -> str:
    """
    返回原始英文标题，详情展开区使用。
    """
    return str(item.get("title", "")).strip()


def get_original_summary(item: dict) -> str:
    """
    返回原始摘要，详情展开区使用。
    """
    return truncate_text(clean_html(item.get("summary_original", "")), 600)


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

    high_score_count = sum(1 for item in items if is_high_score_item(item))

    latest_fetched_at = ""
    if items:
        latest_fetched_at = max(str(item.get("fetched_at", "")) for item in items)

    return {
        "version": "V3.6",
        "mode": "Local Web Interaction Enhanced",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": total_count,
        "ai_processed_count": ai_processed_count,
        "ai_unprocessed_count": total_count - ai_processed_count,
        "featured_count": featured_count,
        "today_count": today_count,
        "high_score_count": high_score_count,
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
    """
    构造模板渲染需要的通用上下文。
    """
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


@app.get("/")
def home(request: Request):
    """
    首页。
    V3.1 开始改为 Jinja2 模板动态渲染。
    """
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
    items = sort_items_by_score(get_featured_items(load_articles_from_db()))

    # 当前页面已处理数量
    current_ai_processed_count = sum(
    1 for item in items
    if is_ai_processed_for_display(item)
)

    context = build_template_context(
        request=request,
        items=items,
        page_title="OrbitAI Featured",
        page_subtitle="精选 AI 信息｜按综合分排序",
        stat_label="精选信息数",
        active_page="featured",
    )

    # 覆盖 context 中的 current_ai_processed_count
    context["current_ai_processed_count"] = current_ai_processed_count

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
    items = sort_items_by_score(get_today_items(load_articles_from_db()))

    current_ai_processed_count = sum(
    1 for item in items
    if is_ai_processed_for_display(item)
    )

    grouped_sections = []

    for item in items:
        category = get_display_category(item)
        section = next(
            (existing_section for existing_section in grouped_sections if existing_section["category"] == category),
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
        name="daily.html",
        context=context,
    )


@app.get("/daily.html")
def daily_html_page(request: Request):
    """
    兼容旧静态 HTML 导航链接。
    """
    return daily_page(request)

@app.get("/status")
def status_page(request: Request):
    """
    V3.4 状态页。
    将 /api/status 的 JSON 状态可视化展示。
    """
    status = get_status_summary()

    return templates.TemplateResponse(
        request=request,
        name="status.html",
        context={
            "request": request,
            "page_title": "OrbitAI Status",
            "page_subtitle": "系统运行状态与错误管理",
            "active_page": "status",
            "status": status,
            "get_display_title": get_display_title,
            "get_display_category": get_display_category,
            "get_display_score": get_display_score,
            "get_short_summary": get_short_summary,
        },
    )

@app.post("/admin/fetch")
def admin_fetch():
    """
    V3.5：网页端手动抓取 RSS。
    只执行 RSS 抓取和 SQLite 写入，不调用 AI。
    """
    try:
        result = run_fetch_only()
        return build_admin_response(result)
    except Exception as error:
        return build_admin_error_response(error)


@app.post("/admin/process-ai")
def admin_process_ai(batch_size: int = 10):
    """
    V3.5：网页端手动处理 AI。
    默认处理 10 条未处理文章。
    """
    try:
        batch_size = max(1, min(batch_size, 50))
        result = run_ai_only(batch_size=batch_size)
        return build_admin_response(result)
    except Exception as error:
        return build_admin_error_response(error)


@app.post("/admin/regenerate")
def admin_regenerate():
    """
    V3.5：网页端手动重新生成静态 HTML。
    用于兼容 index.html / featured.html / daily.html。
    """
    try:
        result = run_regenerate_static()
        return build_admin_response(result)
    except Exception as error:
        return build_admin_error_response(error)

@app.get("/api/items")
def api_items():
    """
    返回全部信息 JSON。
    """
    items = sort_items_by_time(load_articles_from_db())

    return JSONResponse(content=jsonable_encoder(items))


@app.get("/api/featured")
def api_featured():
    """
    返回精选信息 JSON。
    """
    items = load_articles_from_db()
    featured_items = get_featured_items(items)

    return JSONResponse(content=jsonable_encoder(featured_items))


@app.get("/api/daily")
def api_daily():
    """
    返回今日新增信息 JSON。
    """
    items = load_articles_from_db()
    today_items = sort_items_by_score(get_today_items(items))

    return JSONResponse(content=jsonable_encoder(today_items))


@app.get("/api/status")
def api_status():
    """
    返回当前 OrbitAI V3.6 状态。
    """
    status = get_status_summary()

    return JSONResponse(content=jsonable_encoder(status))


@app.get("/api/top")
def api_top(limit: int = 10):
    """
    返回综合分最高的信息。
    默认返回前 10 条。
    """
    items = load_articles_from_db()
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
        "version": "V3.6",
    }