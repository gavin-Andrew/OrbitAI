import json
from datetime import datetime

from orbitai.database import get_connection, init_db
from orbitai.data_utils import create_empty_ai_fields


def parse_tags(tags_text):
    """
    将数据库里保存的 tags 文本转换回列表。

    兼容两种格式：
    1. JSON 字符串：["OpenAI", "Codex"]
    2. 旧版分隔字符串：OpenAI||Codex
    """
    if not tags_text:
        return []

    if isinstance(tags_text, list):
        return tags_text

    tags_text = str(tags_text).strip()

    if not tags_text:
        return []

    try:
        parsed = json.loads(tags_text)
        if isinstance(parsed, list):
            return [
                str(tag).strip()
                for tag in parsed
                if str(tag).strip()
            ]
    except json.JSONDecodeError:
        pass

    return [
        tag.strip()
        for tag in tags_text.split("||")
        if tag.strip()
    ]


def parse_scores(scores_text):
    """
    将数据库里的 scores 文本转换回字典。
    如果旧数据库还没有 scores 字段或内容为空，就返回默认 AI scores 结构。
    """
    default_scores = create_empty_ai_fields()["scores"]

    if not scores_text:
        return default_scores

    if isinstance(scores_text, dict):
        return scores_text

    try:
        parsed = json.loads(str(scores_text))
        if isinstance(parsed, dict):
            scores = default_scores.copy()
            scores.update(parsed)
            return scores
    except json.JSONDecodeError:
        pass

    return default_scores


def row_get(row, key, default=None):
    """
    安全读取 sqlite3.Row 字段。
    兼容旧表结构里暂时不存在的字段。
    """
    if key in row.keys():
        return row[key]

    return default


def row_to_item(row):
    """
    将数据库中的一行文章转换为 OrbitAI 原来的 item dict 结构。

    这样 app.py、模板、scoring.py、html_generator.py 暂时都可以继续复用。
    """
    ai_fields = create_empty_ai_fields()

    ai_fields["title_cn"] = row_get(row, "title_cn", "") or ""
    ai_fields["summary"] = row_get(row, "summary_cn", "") or ""
    ai_fields["category"] = row_get(row, "ai_category", "") or ""
    ai_fields["tags"] = parse_tags(row_get(row, "tags", ""))
    ai_fields["scores"] = parse_scores(row_get(row, "scores", ""))

    final_score = row_get(row, "final_score", None)
    ai_fields["final_score"] = final_score

    ai_fields["processed"] = bool(row_get(row, "processed", 0))
    ai_fields["processed_at"] = row_get(row, "processed_at", "") or ""
    ai_fields["error"] = row_get(row, "error", "") or ""
    ai_fields["error_type"] = row_get(row, "error_type", "") or ""
    ai_fields["failed_at"] = row_get(row, "failed_at", "") or ""
    ai_fields["retry_count"] = int(row_get(row, "retry_count", 0) or 0)

    return {
        "title": row_get(row, "title", "") or "无标题",
        "source": row_get(row, "source", "") or "未知来源",
        "link": row_get(row, "link", "") or "",
        "published": row_get(row, "published", "") or "无发布时间",
        "summary_original": row_get(row, "summary_original", "") or "",
        "category_rule": row_get(row, "category_rule", "") or "其他",
        "fetched_at": row_get(row, "fetched_at", "") or "",
        "ai": ai_fields,
    }


def get_all_articles():
    """
    从 SQLite 读取全部文章。
    默认按 fetched_at 倒序返回。
    """
    init_db()

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("""
        SELECT *
        FROM articles
        ORDER BY fetched_at DESC
        """)

        rows = cursor.fetchall()

    return [row_to_item(row) for row in rows]


def get_article_count():
    """
    返回文章总数。
    """
    init_db()

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        result = cursor.fetchone()

    return int(result[0] or 0)

def get_article_columns() -> set[str]:
    """
    获取 articles 表当前已有字段。
    这样可以兼容 V3.3 早期创建的旧表结构。
    """
    init_db()

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("PRAGMA table_info(articles)")
        rows = cursor.fetchall()

    return {row["name"] for row in rows}


def get_existing_links_from_db() -> set[str]:
    """
    从 SQLite 中读取已经存在的文章链接。
    RSS 抓取时用 link 去重。
    """
    init_db()

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("""
        SELECT link
        FROM articles
        WHERE link IS NOT NULL AND link != ''
        """)

        rows = cursor.fetchall()

    return {
        str(row["link"]).strip()
        for row in rows
        if str(row["link"]).strip()
    }


def item_to_article_row(item: dict) -> dict:
    """
    将 RSS 抓取生成的 item dict 转成 articles 表可写入的字段。
    """
    now = datetime.now().isoformat()
    ai = item.get("ai", {})

    if not isinstance(ai, dict):
        ai = create_empty_ai_fields()

    tags = ai.get("tags", [])
    if isinstance(tags, list):
        tags_text = json.dumps(tags, ensure_ascii=False)
    else:
        tags_text = "[]"

    scores = ai.get("scores", {})
    if isinstance(scores, dict):
        scores_text = json.dumps(scores, ensure_ascii=False)
    else:
        scores_text = json.dumps(create_empty_ai_fields()["scores"], ensure_ascii=False)

    return {
        "title": item.get("title", "") or "无标题",
        "title_cn": ai.get("title_cn", "") or "",
        "source": item.get("source", "") or "未知来源",
        "link": item.get("link", "") or "",
        "published": item.get("published", "") or "无发布时间",
        "fetched_at": item.get("fetched_at", "") or now,
        "summary_original": item.get("summary_original", "") or "",
        "summary_cn": ai.get("summary", "") or "",
        "category_rule": item.get("category_rule", "") or "其他",
        "ai_category": ai.get("category", "") or "",
        "tags": tags_text,
        "scores": scores_text,
        "final_score": ai.get("final_score"),
        "processed": 1 if ai.get("processed") else 0,
        "processed_at": ai.get("processed_at", "") or "",
        "error": ai.get("error", "") or "",
        "error_type": ai.get("error_type", "") or "",
        "failed_at": ai.get("failed_at", "") or "",
        "retry_count": int(ai.get("retry_count", 0) or 0),
        "created_at": now,
        "updated_at": now,
    }


def insert_article(item: dict) -> bool:
    """
    向 SQLite 写入单条文章。
    返回 True 表示插入成功，False 表示跳过。
    """
    init_db()

    row = item_to_article_row(item)
    link = str(row.get("link", "")).strip()

    if not link:
        return False

    existing_columns = get_article_columns()

    # 只写入当前 articles 表实际存在的字段，兼容旧表结构。
    insert_data = {
        key: value
        for key, value in row.items()
        if key in existing_columns
    }

    if not insert_data:
        return False

    columns = list(insert_data.keys())
    placeholders = ", ".join(["?"] * len(columns))
    column_names = ", ".join(columns)
    values = [insert_data[column] for column in columns]

    sql = f"""
    INSERT OR IGNORE INTO articles ({column_names})
    VALUES ({placeholders})
    """

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(sql, values)
        connection.commit()

        return cursor.rowcount > 0


def insert_articles(items: list[dict]) -> dict:
    """
    批量写入文章到 SQLite。
    """
    inserted_count = 0
    skipped_count = 0

    for item in items:
        inserted = insert_article(item)

        if inserted:
            inserted_count += 1
        else:
            skipped_count += 1

    return {
        "inserted": inserted_count,
        "skipped": skipped_count,
        "total": len(items),
    }

def print_articles_preview(limit=10):
    """
    调试用：在终端打印前几条文章。
    """
    articles = get_all_articles()

    print(f"当前数据库文章总数：{len(articles)}")
    print(f"预览前 {min(limit, len(articles))} 条：")

    for item in articles[:limit]:
        ai = item.get("ai", {})
        print("-" * 60)
        print(f"标题：{ai.get('title_cn') or item.get('title')}")
        print(f"来源：{item.get('source')}")
        print(f"分数：{ai.get('final_score')}")
        print(f"链接：{item.get('link')}")

def get_unprocessed_articles(limit: int = 10) -> list[dict]:
    """
    获取未处理的文章列表。
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM articles
            WHERE processed = 0
            ORDER BY fetched_at ASC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
    return [row_to_item(row) for row in rows]


def update_article_ai(item: dict):
    """
    将 AI 处理结果写回 SQLite。
    """
    init_db()
    row = item_to_article_row(item)
    link = row.get("link")
    if not link:
        return False

    existing_columns = get_article_columns()
    update_data = {k: v for k, v in row.items() if k in existing_columns and k != "id"}

    set_clause = ", ".join([f"{k}=?" for k in update_data.keys()])
    values = list(update_data.values())
    values.append(link)  # WHERE link=?

    sql = f"UPDATE articles SET {set_clause} WHERE link=?"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()
        return cursor.rowcount > 0

if __name__ == "__main__":
    print_articles_preview()