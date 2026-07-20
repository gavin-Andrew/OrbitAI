"""产业档案阅读端页面路由。"""

from fastapi import APIRouter, HTTPException, Request

from orbitai.catalog.service import (
    load_industry_catalog,
    load_organization_directory,
    load_person_directory,
    load_segment_profile,
)
from orbitai.web.templating import templates


router = APIRouter()


@router.get("/industries/{industry_slug}")
def industry_catalog_page(request: Request, industry_slug: str):
    """显示一个产业的结构入口。"""

    catalog = load_industry_catalog(industry_slug)
    if catalog is None:
        raise HTTPException(status_code=404, detail="未找到该产业目录")

    return templates.TemplateResponse(
        request=request,
        name="dossier/industry_structure.html",
        context={
            "request": request,
            "page_title": f"{catalog['industry']['name']}结构",
            "page_subtitle": "从四大类别进入 AI 产业的 26 个细分赛道",
            "active_page": "industry_structure",
            "catalog": catalog,
        },
    )


@router.get("/organizations")
def organization_directory_page(request: Request):
    """显示企业与机构档案总入口。"""

    directory = load_organization_directory()
    return templates.TemplateResponse(
        request=request,
        name="dossier/organization_directory.html",
        context={
            "request": request,
            "page_title": "企业档案",
            "page_subtitle": "查看已进入 OrbitAI 名册的企业与研究机构",
            "active_page": "organizations",
            "directory": directory,
        },
    )


@router.get("/people")
def person_directory_page(request: Request):
    """显示人物档案总入口。"""

    directory = load_person_directory()
    return templates.TemplateResponse(
        request=request,
        name="dossier/person_directory.html",
        context={
            "request": request,
            "page_title": "人物档案",
            "page_subtitle": "查看已确认人物及其当前任职关系",
            "active_page": "people",
            "directory": directory,
        },
    )


@router.get("/segments/{segment_slug}")
def segment_profile_page(request: Request, segment_slug: str):
    """显示一个赛道的独立阅读页骨架。"""

    profile = load_segment_profile(segment_slug)
    if profile is None:
        raise HTTPException(status_code=404, detail="未找到该产业赛道")

    segment = profile["segment"]
    return templates.TemplateResponse(
        request=request,
        name="dossier/segment_profile.html",
        context={
            "request": request,
            "page_title": segment["name"],
            "page_subtitle": "赛道概览、参与者名册与后续事件时间线入口",
            "active_page": "industry_structure",
            "profile": profile,
        },
    )
