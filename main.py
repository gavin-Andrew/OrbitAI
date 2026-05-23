import json
from datetime import datetime, timezone
from pathlib import Path

import feedparser


SOURCES = [
    {
        "name": "OpenAI News",
        "url": "https://openai.com/news/rss.xml",
    },
    {
        "name": "Google DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
    },
    {
        "name": "Google AI Blog",
        "url": "https://feeds.feedburner.com/blogspot/gJZg",
    },
]


DATA_FILE = Path("data.json")


def load_existing_data():
    """
    读取已经存在的 data.json。
    如果 data.json 不存在，就返回空列表。
    """
    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        print("⚠️ data.json 格式不是列表，已暂时忽略旧数据。")
        return []

    except json.JSONDecodeError:
        print("⚠️ data.json 不是有效 JSON，已暂时忽略旧数据。")
        return []


def save_data(items):
    """
    把信息保存到 data.json。
    ensure_ascii=False 可以保证中文正常显示。
    indent=2 可以让 JSON 文件更易读。
    """
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(items, file, ensure_ascii=False, indent=2)


def get_existing_links(items):
    """
    用 link 作为去重依据。
    已经保存过的链接，下次就不重复保存。
    """
    return {item.get("link") for item in items if item.get("link")}


def fetch_rss(source, existing_links):
    """
    抓取单个 RSS 信息源，返回新抓到的信息列表。
    """
    name = source["name"]
    url = source["url"]

    print(f"\n========== {name} ==========\n")
    print(f"RSS 地址：{url}\n")

    feed = feedparser.parse(url)

    if feed.bozo:
        print("⚠️ 这个 RSS 源可能读取失败，先跳过。")
        print(f"错误信息：{feed.bozo_exception}\n")
        return []

    if not feed.entries:
        print("⚠️ 没有读取到内容。\n")
        return []

    new_items = []

    for entry in feed.entries[:5]:
        title = entry.get("title", "无标题")
        link = entry.get("link", "")
        published = entry.get("published", "无发布时间")
        summary = entry.get("summary", "")

        if not link:
            print(f"⚠️ 跳过无链接内容：{title}")
            continue

        if link in existing_links:
            print(f"已存在，跳过：{title}")
            continue

        item = {
            "title": title,
            "source": name,
            "link": link,
            "published": published,
            "summary": summary,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        new_items.append(item)
        existing_links.add(link)

        print(f"新增：{title}")
        print(f"时间：{published}")
        print(f"链接：{link}")
        print("-" * 60)

    return new_items


def main():
    print("🚀 OrbitAI V1.1 - RSS 抓取并保存到 data.json")

    existing_items = load_existing_data()
    existing_links = get_existing_links(existing_items)

    print(f"\n当前已保存信息数量：{len(existing_items)}")

    all_new_items = []

    for source in SOURCES:
        new_items = fetch_rss(source, existing_links)
        all_new_items.extend(new_items)

    if all_new_items:
        updated_items = all_new_items + existing_items
        save_data(updated_items)

        print("\n✅ data.json 已更新")
        print(f"本次新增：{len(all_new_items)} 条")
        print(f"当前总数：{len(updated_items)} 条")
    else:
        print("\n✅ 没有发现新内容，data.json 无需更新。")

    print("\n✅ V1.1 运行结束。")


if __name__ == "__main__":
    main()