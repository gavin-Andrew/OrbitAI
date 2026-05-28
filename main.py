from orbitai.data_utils import (
    load_existing_data,
    save_data,
    get_existing_links,
)

from orbitai.rss_fetcher import load_sources, fetch_rss
from orbitai.ai_processor import process_ai_items
from orbitai.html_generator import generate_html, generate_featured_html


def main():
    print("🚀 OrbitAI V2.5 - AI 分类与关键词提取")

    existing_items = load_existing_data()
    existing_links = get_existing_links(existing_items)

    print(f"\n当前已保存信息数量：{len(existing_items)}")
    print("✅ 旧数据已按 V2.x 结构检查 / 迁移。")

    sources = load_sources()

    all_new_items = []

    if sources:
        for source in sources:
            new_items = fetch_rss(source, existing_links)
            all_new_items.extend(new_items)
    else:
        print("\n⚠️ 没有可用信息源，本次只处理已有数据。")

    updated_items = all_new_items + existing_items

    updated_items = process_ai_items(updated_items)

    save_data(updated_items)

    if all_new_items:
        print("\n✅ data.json 已更新")
        print(f"本次新增：{len(all_new_items)} 条")
        print(f"当前总数：{len(updated_items)} 条")
    else:
        print("\n✅ 没有发现新内容。")
        print("✅ data.json 已保存为 V2.5 数据结构。")

    generate_html(updated_items)
    generate_featured_html(updated_items)

    print("\n✅ V2.5 运行结束。")


if __name__ == "__main__":
    main()