"""集中创建 Jinja2 模板环境。"""

from fastapi.templating import Jinja2Templates

from orbitai.core.config import TEMPLATES_DIR


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals.update(
    date_precision_labels={"day": "具体日期", "month": "精确到月", "quarter": "精确到季度",
                           "year": "精确到年", "range": "日期范围", "unknown": "时间待核实"},
    evidence_role_labels={"official": "官方材料", "independent": "独立报道", "expert": "专家观点",
                          "user_feedback": "用户反馈", "background": "背景材料"},
    origin_labels={"ai": "AI 辅助整理", "user": "用户录入", "import": "导入"},
)


__all__ = ["templates"]
