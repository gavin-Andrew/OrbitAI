"""OrbitAI FastAPI 应用组装。"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from orbitai.core.config import STATIC_DIR
from orbitai.web.routes import admin, api, dossier, materials


def create_app() -> FastAPI:
    """创建并组装 FastAPI 应用。"""

    application = FastAPI(
        title="OrbitAI",
        description="OrbitAI - 本地优先的个人产业认知系统",
        version="4.1.0",
    )
    application.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )
    application.include_router(materials.router)
    application.include_router(dossier.router)
    application.include_router(admin.router)
    application.include_router(api.router)
    return application


app = create_app()


__all__ = ["app", "create_app"]
