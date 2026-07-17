"""本地管理页面与操作路由。"""

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse

from main import run_ai_only, run_fetch_only, run_regenerate_static
from orbitai.materials.repository import get_status_summary
from orbitai.web.templating import templates
from orbitai.web.view_helpers import (
    get_display_category,
    get_display_score,
    get_display_title,
    get_short_summary,
)


router = APIRouter()


def build_admin_response(result: dict) -> JSONResponse:
    """统一包装后台操作结果。"""

    return JSONResponse(
        content=jsonable_encoder({
            "ok": result.get("ok", False),
            "message": result.get("message", ""),
            "result": result,
            "status": get_status_summary(),
        })
    )


def build_admin_error_response(error: Exception) -> JSONResponse:
    """统一包装后台操作异常。"""

    return JSONResponse(
        status_code=500,
        content=jsonable_encoder({
            "ok": False,
            "message": "操作失败",
            "result": None,
            "status": get_status_summary(),
            "error": str(error),
        }),
    )


def render_status_page(request: Request):
    """渲染系统状态与错误管理页。"""

    return templates.TemplateResponse(
        request=request,
        name="admin/status.html",
        context={
            "request": request,
            "page_title": "OrbitAI Status",
            "page_subtitle": "系统运行状态与错误管理",
            "active_page": "status",
            "status": get_status_summary(),
            "get_display_title": get_display_title,
            "get_display_category": get_display_category,
            "get_display_score": get_display_score,
            "get_short_summary": get_short_summary,
        },
    )


@router.get("/status")
def status_page():
    """把旧状态页地址重定向到管理模块。"""

    return RedirectResponse(url="/admin/status", status_code=307)


@router.get("/admin/status")
def admin_status_page(request: Request):
    """管理模块的状态页规范地址。"""

    return render_status_page(request)


@router.post("/admin/fetch")
def admin_fetch():
    """手动抓取 RSS 并写入 SQLite，不调用 AI。"""

    try:
        return build_admin_response(run_fetch_only())
    except Exception as error:
        return build_admin_error_response(error)


@router.post("/admin/process-ai")
def admin_process_ai(batch_size: int = 10):
    """手动处理一批尚未完成 AI 处理的文章。"""

    try:
        batch_size = max(1, min(batch_size, 50))
        return build_admin_response(run_ai_only(batch_size=batch_size))
    except Exception as error:
        return build_admin_error_response(error)


@router.post("/admin/regenerate")
def admin_regenerate():
    """重新生成兼容用静态 HTML 快照。"""

    try:
        return build_admin_response(run_regenerate_static())
    except Exception as error:
        return build_admin_error_response(error)
