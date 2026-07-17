"""兼容旧导入与 CLI；活动迁移实现位于 :mod:`orbitai.core.migrations`。"""

from orbitai.core.migrations import *  # noqa: F401,F403
from orbitai.core.migrations import main


if __name__ == "__main__":
    main()
