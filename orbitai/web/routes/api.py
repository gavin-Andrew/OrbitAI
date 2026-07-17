"""本地 JSON API 与健康检查路由。"""

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from orbitai.materials.repository import get_status_summary
from orbitai.materials.scoring import get_featured_items, sort_items_by_score
from orbitai.web.view_helpers import (
    get_today_items,
    load_articles_from_db,
    sort_items_by_time,
)


router = APIRouter()


@router.get("/api/items")
def api_items():
    """返回全部信息。"""

    items = sort_items_by_time(load_articles_from_db())
    return JSONResponse(content=jsonable_encoder(items))


@router.get("/api/featured")
def api_featured():
    """返回精选信息。"""

    items = get_featured_items(load_articles_from_db())
    return JSONResponse(content=jsonable_encoder(items))


@router.get("/api/daily")
def api_daily():
    """返回今日新增信息。"""

    items = sort_items_by_score(get_today_items(load_articles_from_db()))
    return JSONResponse(content=jsonable_encoder(items))


@router.get("/api/status")
def api_status():
    """返回当前 OrbitAI 状态。"""

    return JSONResponse(content=jsonable_encoder(get_status_summary()))


@router.get("/api/top")
def api_top(limit: int = 10):
    """返回综合分最高的信息，最多 50 条。"""

    items = sort_items_by_score(load_articles_from_db())
    limit = max(1, min(limit, 50))
    return JSONResponse(content=jsonable_encoder(items[:limit]))


@router.get("/health")
def health_check():
    """返回轻量健康检查结果。"""

    return {
        "status": "ok",
        "service": "OrbitAI",
        "version": "V3.6",
    }
