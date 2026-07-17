"""OrbitAI FastAPI 兼容启动入口。"""

from orbitai.web.app import app, create_app


__all__ = ["app", "create_app"]
