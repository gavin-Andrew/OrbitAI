"""旧静态生成与展示辅助函数导入路径的兼容包装。"""

from orbitai.web.static_snapshots import *  # noqa: F401,F403
from orbitai.web.view_helpers import (
    get_display_category,
    get_display_summary,
    get_display_title,
    get_today_items,
    parse_item_date,
)
