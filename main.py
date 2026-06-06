from orbitai.repository import (
    get_all_articles,
    get_existing_links_from_db,
    insert_articles,
    get_unprocessed_articles,
    update_article_ai,
)
from orbitai.rss_fetcher import load_sources, fetch_rss
from orbitai.ai_processor import process_ai_items
from orbitai.html_generator import (
    generate_html,
    generate_featured_html,
    generate_daily_html,
)


def process_new_rss():
    existing_items = get_all_articles()
    existing_links = get_existing_links_from_db()

    print(f"\n当前 SQLite 已保存信息数量：{len(existing_items)}")
    print("✅ 当前主数据源：SQLite orbitai.db")

    sources = load_sources()
    all_new_items = []

    if sources:
        for source in sources:
            new_items = fetch_rss(source, existing_links)
            all_new_items.extend(new_items)
    else:
        print("\n⚠️ 没有可用信息源，本次只检查已有数据库内容。")

    if all_new_items:
        result = insert_articles(all_new_items)
        print("\n✅ RSS 新内容已写入 SQLite")
        print(f"本次抓取新内容：{len(all_new_items)} 条")
        print(f"成功写入：{result['inserted']} 条")
        print(f"跳过重复/无效：{result['skipped']} 条")
    else:
        print("\n✅ 没有发现新的 RSS 内容。")


def process_unprocessed_ai(batch_size=10):
    """
    获取未处理文章，调用 DeepSeek AI 处理，并写回 SQLite。
    """
    articles = get_unprocessed_articles(limit=batch_size)
    if not articles:
        print("✅ 没有未处理的文章。")
        return

    processed_articles = process_ai_items(articles)  # DeepSeek 调用

    success_count = 0
    fail_count = 0

    for item in processed_articles:
        updated = update_article_ai(item)
        if updated:
            success_count += 1
        else:
            fail_count += 1

    print(f"✅ 本轮 AI 处理完成：成功 {success_count} 条，失败 {fail_count} 条")


def main():
    print("🚀 OrbitAI V3.3.6 - RSS + AI 写回 SQLite")

    # 1️⃣ RSS 写入 SQLite
    process_new_rss()

    # 2️⃣ AI 处理写回 SQLite
    process_unprocessed_ai(batch_size=10)

    # 3️⃣ HTML 更新
    updated_items = get_all_articles()
    generate_html(updated_items)
    generate_featured_html(updated_items)
    generate_daily_html(updated_items)

    print(f"\n当前 SQLite 总信息数量：{len(updated_items)}")
    print("✅ V3.3.6 运行结束。")


if __name__ == "__main__":
    main()