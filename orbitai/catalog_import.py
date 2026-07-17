"""旧名册导入路径与 CLI 的兼容包装。"""

from orbitai.catalog.import_service import *  # noqa: F401,F403
from orbitai.catalog.import_service import main


if __name__ == "__main__":
    raise SystemExit(main())
