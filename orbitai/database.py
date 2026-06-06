import sqlite3

from orbitai.config import DATABASE_FILE


def get_connection():
    """
    获取 SQLite 数据库连接。
    row_factory 让查询结果可以像字典一样读取字段。
    """
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """
    初始化数据库。
    V3.3.3 阶段主要保证 articles 表存在。
    """
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            title_cn TEXT,
            source TEXT,
            link TEXT UNIQUE,
            published TEXT,
            fetched_at TEXT,
            summary_original TEXT,
            summary_cn TEXT,
            category_rule TEXT,
            ai_category TEXT,
            tags TEXT,
            scores TEXT,
            final_score REAL,
            processed INTEGER DEFAULT 0,
            processed_at TEXT,
            error TEXT,
            error_type TEXT,
            failed_at TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        """)

        connection.commit()