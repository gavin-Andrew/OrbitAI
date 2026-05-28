import json

import feedparser

from orbitai.config import SOURCES_FILE
from orbitai.data_utils import create_new_item
from orbitai.text_utils import clean_html


def load_sources():
    """
    从 sources.json 读取 RSS 信息源。
    只返回 enabled 为 true 的信源。
    """
    if not SOURCES_FILE.exists():
        print("⚠️ 未找到 sources.json，无法读取信息源。")
        return []

    try:
        with SOURCES_FILE.open("r", encoding="utf-8") as file:
            sources = json.load(file)

        if not isinstance(sources, list):
            print("⚠️ sources.json 格式错误：最外层应该是列表。")
            return []

        enabled_sources = []

        for source in sources:
            name = source.get("name")
            url = source.get("url")
            enabled = source.get("enabled", True)

            if not enabled:
                continue

            if not name or not url:
                print(f"⚠️ 跳过无效信源：{source}")
                continue

            enabled_sources.append({
                "name": name,
                "url": url,
            })

        return enabled_sources

    except json.JSONDecodeError:
        print("⚠️ sources.json 不是有效 JSON，请检查格式。")
        return []


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
        summary_original = clean_html(entry.get("summary", ""))

        if not link:
            print(f"⚠️ 跳过无链接内容：{title}")
            continue

        if link in existing_links:
            print(f"已存在，跳过：{title}")
            continue

        item = create_new_item(
            title=title,
            source=name,
            link=link,
            published=published,
            summary_original=summary_original,
        )

        new_items.append(item)
        existing_links.add(link)

        print(f"新增：{title}")
        print(f"时间：{published}")
        print(f"链接：{link}")
        print("-" * 60)

    return new_items