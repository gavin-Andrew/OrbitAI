from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse

from orbitai.data_utils import load_existing_data
from orbitai.ai_processor import item_is_ai_complete
from orbitai.scoring import get_featured_items, sort_items_by_score
from orbitai.html_generator import (
    generate_html,
    generate_featured_html,
    generate_daily_html,
    get_today_items,
)


app = FastAPI(
    title="OrbitAI",
    description="OrbitAI V3.0 - Local FastAPI Service",
    version="3.0.0",
)


INDEX_FILE = Path("index.html")
FEATURED_FILE = Path("featured.html")
DAILY_FILE = Path("daily.html")


def read_html_file(file_path: Path) -> str:
    """
    读取已经生成好的 HTML 文件。
    如果文件不存在，返回一个简单提示页面。
    """
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")

    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>OrbitAI</title>
    </head>
    <body>
        <h1>OrbitAI</h1>
        <p>未找到 {file_path.name}。</p>
        <p>请先运行 <code>python main.py</code> 生成本地页面，或访问 API 查看数据。</p>
    </body>
    </html>
    """


def get_ai_final_score(item: dict) -> float:
    """
    安全读取单条信息的 final_score。
    """
    try:
        return float(item.get("ai", {}).get("final_score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def get_display_category(item: dict) -> str:
    """
    获取展示分类。
    优先使用 AI 分类，没有则回退到规则分类。
    """
    ai = item.get("ai", {})

    if isinstance(ai, dict):
        ai_category = str(ai.get("category", "")).strip()
        if ai_category:
            return ai_category

    return str(item.get("category_rule", "其他")).strip() or "其他"


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
        "version": "V3.0",
        "mode": "Local FastAPI Service",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": total_count,
        "ai_processed_count": ai_processed_count,
        "ai_unprocessed_count": total_count - ai_processed_count,
        "featured_count": featured_count,
        "today_count": today_count,
        "ai_failed_count": len(ai_failed_items),
        "sources": sources,
        "categories": categories,
        "pages": {
            "index_html_exists": INDEX_FILE.exists(),
            "featured_html_exists": FEATURED_FILE.exists(),
            "daily_html_exists": DAILY_FILE.exists(),
        },
    }


@app.get("/", response_class=HTMLResponse)
def home():
    """
    首页。
    V3.0 先复用 V2 生成的 index.html。
    如果 index.html 不存在，就临时生成一次。
    """
    items = load_existing_data()

    if items and not INDEX_FILE.exists():
        generate_html(items)

    return HTMLResponse(content=read_html_file(INDEX_FILE))

@app.get("/index.html", response_class=HTMLResponse)
def index_html_page():
    """
    兼容 V2 静态 HTML 导航链接。
    """
    return home()

@app.get("/featured", response_class=HTMLResponse)
def featured_page():
    """
    精选信息页。
    V3.0 先复用 V2 的 featured.html 生成逻辑。
    """
    items = load_existing_data()

    if items:
        generate_featured_html(items)

    return HTMLResponse(content=read_html_file(FEATURED_FILE))

@app.get("/featured.html", response_class=HTMLResponse)
def featured_html_page():
    """
    兼容 V2 静态 HTML 导航链接。
    """
    return featured_page()

@app.get("/daily", response_class=HTMLResponse)
def daily_page():
    """
    每日简报页。
    V3.0 先复用 V2 的 daily.html 生成逻辑。
    """
    items = load_existing_data()

    if items:
        generate_daily_html(items)

    return HTMLResponse(content=read_html_file(DAILY_FILE))

@app.get("/daily.html", response_class=HTMLResponse)
def daily_html_page():
    """
    兼容 V2 静态 HTML 导航链接。
    """
    return daily_page()

@app.get("/api/items")
def api_items():
    """
    返回全部信息 JSON。
    """
    items = load_existing_data()

    sorted_items = sorted(
        items,
        key=lambda item: item.get("fetched_at", ""),
        reverse=True,
    )

    return JSONResponse(content=jsonable_encoder(sorted_items))


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
    today_items = get_today_items(items)

    today_items = sorted(
        today_items,
        key=get_ai_final_score,
        reverse=True,
    )

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
    用来确认 FastAPI 服务是否正常启动。
    """
    return {
        "status": "ok",
        "service": "OrbitAI",
        "version": "V3.0",
    }