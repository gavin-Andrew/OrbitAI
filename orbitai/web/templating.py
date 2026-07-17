"""集中创建 Jinja2 模板环境。"""

from fastapi.templating import Jinja2Templates

from orbitai.core.config import TEMPLATES_DIR


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


__all__ = ["templates"]
