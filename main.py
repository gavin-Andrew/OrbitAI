import json
import re
from datetime import datetime, timezone
from html import escape
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
HTML_FILE = Path("index.html")


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


def clean_html(raw_text):
    """
    RSS 里的 summary 有时会带 HTML 标签。
    这里做一个简单清理，让网页展示更干净。
    """
    if not raw_text:
        return ""

    text = re.sub(r"<[^>]+>", "", raw_text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    return text.strip()

def truncate_text(text, max_length=220):
    """
    把过长的摘要截断，避免网页卡片太长。
    """
    if not text:
        return ""

    text = " ".join(text.split())

    if len(text) <= max_length:
        return text

    return text[:max_length].rstrip() + "..."

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
        summary = clean_html(entry.get("summary", ""))

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


def sort_items(items):
    """
    优先按照 fetched_at 倒序排列。
    新抓取的内容显示在前面。
    """
    return sorted(
        items,
        key=lambda item: item.get("fetched_at", ""),
        reverse=True,
    )


def generate_html(items):
    """
    根据 data.json 里的数据生成本地 index.html。
    """
    sorted_items = sort_items(items)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    article_cards = []

    for item in sorted_items:
        title = escape(item.get("title", "无标题"))
        source = escape(item.get("source", "未知来源"))
        link = escape(item.get("link", "#"))
        published = escape(item.get("published", "无发布时间"))
        summary = escape(truncate_text(clean_html(item.get("summary", "")), 240))

        if summary:
            summary_html = f"<p class='summary'>{summary}</p>"
        else:
            summary_html = "<p class='summary empty'>暂无摘要</p>"

        card = f"""
        <article class="card">
            <div class="meta">
                <span class="source">{source}</span>
                <span class="time">{published}</span>
            </div>
            <h2>
                <a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a>
            </h2>
            {summary_html}
            <a class="button" href="{link}" target="_blank" rel="noopener noreferrer">打开原文</a>
        </article>
        """

        article_cards.append(card)

    cards_html = "\n".join(article_cards)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OrbitAI</title>
    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
            background: #f4f7fb;
            color: #1f2937;
            line-height: 1.6;
        }}

        .page {{
            max-width: 980px;
            margin: 0 auto;
            padding: 40px 20px;
        }}

        .header {{
            margin-bottom: 32px;
            padding: 28px;
            border-radius: 24px;
            background: linear-gradient(135deg, #0f172a, #1d4ed8);
            color: white;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18);
        }}

        .header h1 {{
            margin: 0 0 8px;
            font-size: 40px;
            letter-spacing: -0.04em;
        }}

        .header p {{
            margin: 0;
            opacity: 0.9;
        }}

        .stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 20px;
        }}

        .stat {{
            padding: 8px 14px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.14);
            font-size: 14px;
        }}

        .card {{
            margin-bottom: 18px;
            padding: 24px;
            border: 1px solid #e5e7eb;
            border-radius: 20px;
            background: white;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }}

        .meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 10px;
            font-size: 14px;
            color: #6b7280;
        }}

        .source {{
            font-weight: 700;
            color: #2563eb;
        }}

        h2 {{
            margin: 0 0 12px;
            font-size: 22px;
            line-height: 1.35;
        }}

        h2 a {{
            color: #111827;
            text-decoration: none;
        }}

        h2 a:hover {{
            color: #2563eb;
        }}

        .summary {{
            margin: 0 0 18px;
            color: #4b5563;
            overflow-wrap: anywhere;
            word-break: break-word;
        }}

        .summary.empty {{
            color: #9ca3af;
        }}

        .button {{
            display: inline-block;
            padding: 8px 14px;
            border-radius: 999px;
            background: #eff6ff;
            color: #2563eb;
            font-weight: 600;
            text-decoration: none;
            font-size: 14px;
        }}

        .button:hover {{
            background: #dbeafe;
        }}

        .footer {{
            margin-top: 32px;
            text-align: center;
            color: #9ca3af;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <main class="page">
        <section class="header">
            <h1>OrbitAI</h1>
            <p>Personal AI Information Radar</p>
            <div class="stats">
                <span class="stat">总信息数：{len(sorted_items)}</span>
                <span class="stat">生成时间：{generated_at}</span>
            </div>
        </section>

        <section class="feed">
            {cards_html}
        </section>

        <footer class="footer">
            Generated locally by OrbitAI V1.2
        </footer>
    </main>
</body>
</html>
"""

    with HTML_FILE.open("w", encoding="utf-8") as file:
        file.write(html_content)

    print(f"\n✅ {HTML_FILE} 已生成。")


def main():
    print("🚀 OrbitAI V1.2 - RSS 抓取、保存 data.json，并生成 index.html")

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
        updated_items = existing_items
        print("\n✅ 没有发现新内容，data.json 无需更新。")

    generate_html(updated_items)

    print("\n✅ V1.2 运行结束。")


if __name__ == "__main__":
    main()