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


def fetch_rss(source):
    """
    抓取单个 RSS 信息源，并打印最新内容。
    """
    name = source["name"]
    url = source["url"]

    print(f"\n========== {name} ==========\n")
    print(f"RSS 地址：{url}\n")

    feed = feedparser.parse(url)

    if feed.bozo:
        print("⚠️ 这个 RSS 源可能读取失败，先跳过。")
        print(f"错误信息：{feed.bozo_exception}\n")
        return

    if not feed.entries:
        print("⚠️ 没有读取到内容。\n")
        return

    for entry in feed.entries[:5]:
        title = entry.get("title", "无标题")
        link = entry.get("link", "无链接")
        published = entry.get("published", "无发布时间")

        print(f"标题：{title}")
        print(f"时间：{published}")
        print(f"链接：{link}")
        print("-" * 60)


def main():
    print("🚀 OrbitAI V1.0 - RSS 信息抓取测试")

    for source in SOURCES:
        fetch_rss(source)

    print("\n✅ V1.0 运行结束：RSS 抓取与终端打印测试完成。")


if __name__ == "__main__":
    main()