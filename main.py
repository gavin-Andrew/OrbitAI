from orbitai.materials.repository import (
    get_all_articles,
    get_existing_links_from_db,
    insert_articles,
    get_unprocessed_articles,
    update_article_ai,
)
from orbitai.materials.rss import load_sources, fetch_rss
from orbitai.materials.ai_processor import process_ai_items


def run_fetch_only():
    """
    只执行 RSS 抓取，并把新内容写入 SQLite。

    这个函数后续可供：
    - main.py 命令行流程调用
    - FastAPI 的 POST /admin/fetch 调用
    """
    existing_items = get_all_articles()
    existing_links = get_existing_links_from_db()

    print(f"\n当前 SQLite 已保存信息数量：{len(existing_items)}")
    print("当前主数据源：SQLite var/orbitai.db")

    sources = load_sources()
    all_new_items = []

    if sources:
        for source in sources:
            new_items = fetch_rss(source, existing_links)
            all_new_items.extend(new_items)
    else:
        print("\n没有可用信息源，本次只检查已有数据库内容。")

    if all_new_items:
        result = insert_articles(all_new_items)

        print("\nRSS 新内容已写入 SQLite")
        print(f"本次抓取新内容：{len(all_new_items)} 条")
        print(f"成功写入：{result['inserted']} 条")
        print(f"跳过重复/无效：{result['skipped']} 条")

        return {
            "ok": True,
            "message": "RSS 抓取完成",
            "total_before": len(existing_items),
            "fetched_count": len(all_new_items),
            "inserted_count": result["inserted"],
            "skipped_count": result["skipped"],
            "source_count": len(sources),
            "error": None,
        }

    print("\n没有发现新的 RSS 内容。")

    return {
        "ok": True,
        "message": "没有发现新的 RSS 内容",
        "total_before": len(existing_items),
        "fetched_count": 0,
        "inserted_count": 0,
        "skipped_count": 0,
        "source_count": len(sources) if sources else 0,
        "error": None,
    }


def run_ai_only(batch_size=10):
    """
    只处理未完成 AI 的文章，并写回 SQLite。

    这个函数后续可供：
    - main.py 命令行流程调用
    - FastAPI 的 POST /admin/process-ai 调用
    """
    articles = get_unprocessed_articles(limit=batch_size)

    if not articles:
        print("没有未处理的文章。")

        return {
            "ok": True,
            "message": "没有未处理的文章",
            "requested_count": 0,
            "processed_count": 0,
            "success_count": 0,
            "fail_count": 0,
            "error": None,
        }

    processed_articles = process_ai_items(articles)

    success_count = 0
    fail_count = 0

    for item in processed_articles:
        updated = update_article_ai(item)
        if updated:
            success_count += 1
        else:
            fail_count += 1

    print(f"本轮 AI 处理完成：成功 {success_count} 条，失败 {fail_count} 条")

    return {
        "ok": True,
        "message": "AI 处理完成",
        "requested_count": len(articles),
        "processed_count": len(processed_articles),
        "success_count": success_count,
        "fail_count": fail_count,
        "error": None,
    }


def run_full_pipeline(batch_size=10):
    """
    执行完整更新流程：

    1. RSS 抓取并写入 SQLite
    2. AI 处理并写回 SQLite
    动态 Web 页面直接读取 SQLite；本流程不再生成静态 HTML 快照。
    """
    print("OrbitAI - RSS + AI + SQLite 材料更新流程")

    fetch_result = run_fetch_only()
    ai_result = run_ai_only(batch_size=batch_size)

    print("材料更新流程运行结束。")

    return {
        "ok": True,
        "message": "材料更新流程运行结束",
        "fetch": fetch_result,
        "ai": ai_result,
        "error": None,
    }


def main():
    """
    命令行入口。

    运行：
    python main.py
    """
    run_full_pipeline(batch_size=10)


if __name__ == "__main__":
    main()
