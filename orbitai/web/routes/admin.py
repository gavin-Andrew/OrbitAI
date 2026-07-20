"""本地管理页面与操作路由。"""

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse

from main import run_ai_only, run_fetch_only
from orbitai.catalog.edit_service import (
    CatalogEditConflict,
    CatalogEditNotFound,
    CatalogEditValidationError,
    load_catalog_management_data,
    preview_catalog_edit,
    save_catalog_edit,
)
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


@router.get("/admin/catalog")
def admin_catalog_page(request: Request):
    """独立的 V4.1 名册最小管理入口。"""

    editor_data = load_catalog_management_data()
    return templates.TemplateResponse(
        request=request,
        name="admin/catalog_editor.html",
        context={
            "request": request,
            "page_title": "OrbitAI 名册管理",
            "editor_data": editor_data,
        },
    )


def _catalog_edit_error_response(error: Exception) -> JSONResponse:
    """把编辑服务错误转换成页面可以明确处理的 HTTP 响应。"""

    if isinstance(error, CatalogEditConflict):
        return JSONResponse(
            status_code=409,
            content=jsonable_encoder({
                "ok": False,
                "error_type": "conflict",
                "message": str(error),
                "current": error.current,
            }),
        )
    if isinstance(error, CatalogEditValidationError):
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({
                "ok": False,
                "error_type": "validation",
                "message": "修改内容未通过校验。",
                "errors": error.errors,
            }),
        )
    if isinstance(error, CatalogEditNotFound):
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error_type": "not_found",
                "message": str(error),
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error_type": "server_error",
            "message": "保存过程中发生错误，事务已经回滚。",
        },
    )


@router.post("/admin/catalog/preview")
async def admin_catalog_preview(request: Request):
    """只预览修改差异，同时检查身份和版本冲突。"""

    try:
        payload = await request.json()
        result = preview_catalog_edit(payload)
        return JSONResponse(
            content=jsonable_encoder({"ok": True, "preview": result})
        )
    except Exception as error:
        return _catalog_edit_error_response(error)


@router.post("/admin/catalog/save")
async def admin_catalog_save(request: Request):
    """重新检查冲突，并以单一事务保存修改及其记录。"""

    try:
        payload = await request.json()
        return JSONResponse(content=jsonable_encoder(save_catalog_edit(payload)))
    except Exception as error:
        return _catalog_edit_error_response(error)


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
