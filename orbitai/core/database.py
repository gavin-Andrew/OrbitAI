import sqlite3
from pathlib import Path

from orbitai.core.config import DATABASE_FILE
from orbitai.core.migrations import apply_migrations


__all__ = ["DATABASE_FILE", "apply_migrations", "get_connection", "init_db"]


def get_connection(database_file: str | Path | None = None):
    """
    获取 SQLite 数据库连接。
    row_factory 让查询结果可以像字典一样读取字段。
    """
    connection = sqlite3.connect(database_file or DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(database_file: str | Path | None = None) -> list[str]:
    """
    初始化数据库并应用尚未执行的迁移。

    返回本次实际应用的迁移版本；现有调用方可以继续忽略返回值。
    """
    with get_connection(database_file) as connection:
        return apply_migrations(connection)
