import json
import ssl
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

import certifi
import feedparser

from orbitai.config import (
    SOURCES_FILE,
    RSS_MAX_ITEMS_PER_SOURCE,
    RSS_RETRY_TIMES,
    RSS_RETRY_DELAY_SECONDS,
    RSS_TIMEOUT_SECONDS,
)
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

def parse_rss_with_retry(
    url,
    retry_times=RSS_RETRY_TIMES,
    retry_delay_seconds=RSS_RETRY_DELAY_SECONDS,
    timeout_seconds=RSS_TIMEOUT_SECONDS,
):
    """
    带重试机制地读取 RSS。

    为什么不直接 feedparser.parse(url)：
    - 网络请求可能偶发失败；
    - 部分 RSS 源对没有 User-Agent 的请求不稳定；
    - feed.bozo 为 True 时，有时仍然能解析出 entries。
    """
    last_error = None

    headers = {
        "User-Agent": (
            "OrbitAI/2.7 "
            "(Personal AI Information Radar; RSS Reader)"
        )
    }

    for attempt in range(1, retry_times + 1):
        try:
            print(f"尝试读取 RSS：第 {attempt}/{retry_times} 次")

            request = Request(
                url,
                headers=headers,
            )

            ssl_context = ssl.create_default_context(cafile=certifi.where())

            with urlopen(
                request,
                timeout=timeout_seconds,
                context=ssl_context,
            ) as response:
                feed_content = response.read()

            feed = feedparser.parse(feed_content)

            if feed.bozo:
                last_error = feed.bozo_exception

                if feed.entries:
                    print("⚠️ RSS 存在解析警告，但已读取到内容，继续处理。")
                    print(f"警告信息：{last_error}\n")
                    return feed

                print(f"⚠️ RSS 解析失败：{last_error}")

            else:
                return feed

        except URLError as error:
            last_error = error
            print(f"⚠️ RSS 连接失败：{error}")

        except Exception as error:
            last_error = error
            print(f"⚠️ RSS 读取异常：{error}")

        if attempt < retry_times:
            print(f"等待 {retry_delay_seconds} 秒后重试...\n")
            time.sleep(retry_delay_seconds)

    print("❌ RSS 多次读取失败。")
    print(f"最后错误信息：{last_error}\n")
    return None

def fetch_rss(source, existing_links):
    """
    抓取单个 RSS 信息源，返回新抓到的信息列表。
    """
    name = source["name"]
    url = source["url"]

    print(f"\n========== {name} ==========\n")
    print(f"RSS 地址：{url}\n")

    feed = parse_rss_with_retry(url)

    if feed is None:
        print("⚠️ 这个 RSS 源多次读取失败，本次先跳过。\n")
        return []

    if not feed.entries:
        print("⚠️ 没有读取到内容。\n")
        return []

    new_items = []

    for entry in feed.entries[:RSS_MAX_ITEMS_PER_SOURCE]:
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