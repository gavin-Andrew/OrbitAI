"""产业档案页面路由。"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from orbitai.catalog_service import load_industry_catalog
from orbitai.repository import get_status_summary
from orbitai.web.templating import templates


router = APIRouter()


@router.get("/industries/{industry_slug}")
def industry_catalog_page(request: Request, industry_slug: str):
    """显示一个产业的四大分组和完整赛道目录。"""

    catalog = load_industry_catalog(industry_slug)
    if catalog is None:
        raise HTTPException(status_code=404, detail="未找到该产业目录")

    status = {
        **get_status_summary(),
        "version": "V4.1-C",
    }

    return templates.TemplateResponse(
        request=request,
        name="dossier/industry_catalog.html",
        context={
            "request": request,
            "page_title": catalog["industry"]["name"],
            "page_subtitle": "从四大目录分组进入 26 个 AI 产业赛道",
            "active_page": "industry_catalog",
            "catalog": catalog,
            "status": status,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
