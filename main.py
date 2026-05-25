import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import feedparser

DATA_FILE = Path("data.json")
HTML_FILE = Path("index.html")
SOURCES_FILE = Path("sources.json")


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


def classify_item(title, summary):
    """
    用简单关键词规则给信息做基础分类。
    V2.0 仍然保留规则分类。
    真正的 AI 分类会在 V2.2 再加入。
    """
    text = f"{title} {summary}".lower()

    if any(keyword in text for keyword in ["model", "gpt", "claude", "llm", "language model", "gemini"]):
        return "模型"

    if any(keyword in text for keyword in ["paper", "research", "study", "benchmark", "evaluation"]):
        return "论文/研究"

    if any(keyword in text for keyword in ["product", "app", "release", "launch", "codex", "code"]):
        return "产品"

    if any(keyword in text for keyword in ["company", "funding", "startup", "enterprise", "business"]):
        return "行业"

    return "其他"


def create_empty_ai_fields():
    """
    创建 AI 预留字段。
    V2.0 只准备结构，不真正调用 AI。
    """
    return {
        "title_cn": "",
        "summary": "",
        "category": "",
        "tags": [],
        "scores": {
            "importance": None,
            "novelty": None,
            "practical_value": None,
            "learning_value": None,
            "source_authority": None,
        },
        "final_score": None,
        "processed": False,
        "processed_at": "",
        "error": "",
    }


def migrate_item_to_v2(item):
    """
    把旧版数据迁移到 V2.0 数据结构。

    旧字段：
    - summary
    - category

    新字段：
    - summary_original
    - category_rule
    - ai
    """
    title = item.get("title", "无标题")
    summary_original = item.get("summary_original", item.get("summary", ""))
    category_rule = item.get("category_rule", item.get("category", ""))

    if not category_rule:
        category_rule = classify_item(title, summary_original)

    migrated_item = {
        "title": title,
        "source": item.get("source", "未知来源"),
        "link": item.get("link", ""),
        "published": item.get("published", "无发布时间"),
        "summary_original": summary_original,
        "category_rule": category_rule,
        "fetched_at": item.get("fetched_at", datetime.now(timezone.utc).isoformat()),
    }

    existing_ai = item.get("ai")

    if isinstance(existing_ai, dict):
        ai_fields = create_empty_ai_fields()

        for key, value in existing_ai.items():
            if key in ai_fields:
                ai_fields[key] = value

        if not isinstance(ai_fields.get("tags"), list):
            ai_fields["tags"] = []

        if not isinstance(ai_fields.get("scores"), dict):
            ai_fields["scores"] = create_empty_ai_fields()["scores"]

        default_scores = create_empty_ai_fields()["scores"]

        for score_key, default_value in default_scores.items():
            ai_fields["scores"].setdefault(score_key, default_value)

        migrated_item["ai"] = ai_fields
    else:
        migrated_item["ai"] = create_empty_ai_fields()

    return migrated_item


def load_existing_data():
    """
    读取已经存在的 data.json。
    如果 data.json 是旧结构，就自动迁移到 V2.0 结构。
    """
    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            print("⚠️ data.json 格式不是列表，已暂时忽略旧数据。")
            return []

        migrated_data = []

        for item in data:
            if isinstance(item, dict):
                migrated_data.append(migrate_item_to_v2(item))

        return migrated_data

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


def create_new_item(title, source, link, published, summary_original):
    """
    创建一条 V2.0 标准结构的新信息。
    """
    return {
        "title": title,
        "source": source,
        "link": link,
        "published": published,
        "summary_original": summary_original,
        "category_rule": classify_item(title, summary_original),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ai": create_empty_ai_fields(),
    }


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


def get_display_title(item):
    """
    页面展示标题。
    V2.0 暂时没有 AI 中文标题，所以通常显示原始标题。
    V2.1 接入 AI 后，会优先显示 ai.title_cn。
    """
    ai = item.get("ai", {})
    title_cn = ai.get("title_cn", "")

    if title_cn:
        return title_cn

    return item.get("title", "无标题")


def get_display_summary(item):
    """
    页面展示摘要。
    V2.0 暂时没有 AI 摘要，所以显示 summary_original。
    V2.1 接入 AI 后，会优先显示 ai.summary。
    """
    ai = item.get("ai", {})
    ai_summary = ai.get("summary", "")

    if ai_summary:
        return ai_summary

    return item.get("summary_original", "")


def get_display_category(item):
    """
    页面展示分类。
    V2.0 暂时使用规则分类。
    V2.2 接入 AI 分类后，会优先显示 ai.category。
    """
    ai = item.get("ai", {})
    ai_category = ai.get("category", "")

    if ai_category:
        return ai_category

    return item.get("category_rule", "其他")


def generate_html(items):
    """
    根据 data.json 里的数据生成本地 index.html。
    V2.0 页面仍然是全部信息页，但已经兼容未来 AI 字段。
    """
    sorted_items = sort_items(items)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sources = sorted({item.get("source", "未知来源") for item in sorted_items})
    categories = sorted({get_display_category(item) for item in sorted_items})

    ai_processed_count = sum(
        1 for item in sorted_items
        if item.get("ai", {}).get("processed") is True
    )

    source_options = "\n".join(
        f'<option value="{escape(source)}">{escape(source)}</option>'
        for source in sources
    )

    category_options = "\n".join(
        f'<option value="{escape(category)}">{escape(category)}</option>'
        for category in categories
    )

    article_cards = []

    for item in sorted_items:
        title_raw = item.get("title", "无标题")
        display_title_raw = get_display_title(item)
        source_raw = item.get("source", "未知来源")
        category_raw = get_display_category(item)
        summary_raw = truncate_text(clean_html(get_display_summary(item)), 240)

        ai = item.get("ai", {})
        tags = ai.get("tags", [])

        if not isinstance(tags, list):
            tags = []

        title = escape(display_title_raw)
        source = escape(source_raw)
        category = escape(category_raw)
        link = escape(item.get("link", "#"))
        published = escape(item.get("published", "无发布时间"))
        summary = escape(summary_raw)

        tags_text = " ".join(tags)

        search_text = escape(
            f"{title_raw} {display_title_raw} {source_raw} "
            f"{item.get('category_rule', '')} {category_raw} "
            f"{summary_raw} {tags_text}".lower()
        )

        if summary:
            summary_html = f"<p class='summary'>{summary}</p>"
        else:
            summary_html = "<p class='summary empty'>暂无摘要</p>"

        if tags:
            tags_html = "<div class='tags'>" + "".join(
                f"<span class='tag'>{escape(tag)}</span>"
                for tag in tags
            ) + "</div>"
        else:
            tags_html = ""

        card = f"""
        <article class="card" data-source="{source}" data-category="{category}" data-search="{search_text}">
            <div class="meta">
                <span class="source">{source}</span>
                <span class="category">{category}</span>
                <span class="time">{published}</span>
            </div>
            <h2>
                <a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a>
            </h2>
            {summary_html}
            {tags_html}
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

        .controls {{
            display: grid;
            grid-template-columns: 1fr 180px 180px;
            gap: 12px;
            margin-bottom: 22px;
        }}

        .controls input,
        .controls select {{
            width: 100%;
            padding: 12px 14px;
            border: 1px solid #dbe3ef;
            border-radius: 14px;
            background: white;
            color: #111827;
            font-size: 15px;
            outline: none;
        }}

        .controls input:focus,
        .controls select:focus {{
            border-color: #2563eb;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
        }}

        .result-count {{
            grid-column: 1 / -1;
            color: #6b7280;
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

        .category {{
            padding: 2px 8px;
            border-radius: 999px;
            background: #f3f4f6;
            color: #4b5563;
            font-size: 13px;
            font-weight: 600;
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

        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 0 0 18px;
        }}

        .tag {{
            padding: 3px 9px;
            border-radius: 999px;
            background: #eef2ff;
            color: #4f46e5;
            font-size: 13px;
            font-weight: 600;
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

        @media (max-width: 720px) {{
            .controls {{
                grid-template-columns: 1fr;
            }}
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
                <span class="stat">AI 已处理：{ai_processed_count}</span>
                <span class="stat">生成时间：{generated_at}</span>
            </div>
        </section>

        <section class="controls">
            <input id="searchInput" type="text" placeholder="搜索标题、来源、摘要、标签..." />

            <select id="sourceFilter">
                <option value="all">全部来源</option>
                {source_options}
            </select>

            <select id="categoryFilter">
                <option value="all">全部分类</option>
                {category_options}
            </select>

            <div id="resultCount" class="result-count"></div>
        </section>

        <section class="feed">
            {cards_html}
        </section>

        <footer class="footer">
            Generated locally by OrbitAI V2.0
        </footer>
    </main>
<script>
    const searchInput = document.getElementById("searchInput");
    const sourceFilter = document.getElementById("sourceFilter");
    const categoryFilter = document.getElementById("categoryFilter");
    const resultCount = document.getElementById("resultCount");
    const cards = Array.from(document.querySelectorAll(".card"));

    function updateCards() {{
        const searchValue = searchInput.value.trim().toLowerCase();
        const selectedSource = sourceFilter.value;
        const selectedCategory = categoryFilter.value;

        let visibleCount = 0;

        cards.forEach((card) => {{
            const cardSource = card.dataset.source;
            const cardCategory = card.dataset.category;
            const cardSearch = card.dataset.search;

            const matchesSearch = !searchValue || cardSearch.includes(searchValue);
            const matchesSource = selectedSource === "all" || cardSource === selectedSource;
            const matchesCategory = selectedCategory === "all" || cardCategory === selectedCategory;

            const shouldShow = matchesSearch && matchesSource && matchesCategory;

            card.style.display = shouldShow ? "block" : "none";

            if (shouldShow) {{
                visibleCount += 1;
            }}
        }});

        resultCount.textContent = `当前显示：${{visibleCount}} / ${{cards.length}} 条`;
    }}

    searchInput.addEventListener("input", updateCards);
    sourceFilter.addEventListener("change", updateCards);
    categoryFilter.addEventListener("change", updateCards);

    updateCards();
</script>
</body>
</html>
"""

    with HTML_FILE.open("w", encoding="utf-8") as file:
        file.write(html_content)

    print(f"\n✅ {HTML_FILE} 已生成。")


def main():
    print("🚀 OrbitAI V2.0 - AI 接入前的数据结构准备版")

    existing_items = load_existing_data()
    existing_links = get_existing_links(existing_items)

    print(f"\n当前已保存信息数量：{len(existing_items)}")
    print("✅ 旧数据已按 V2.0 结构检查 / 迁移。")

    sources = load_sources()

    if not sources:
        print("\n⚠️ 没有可用信息源，程序结束。")
        save_data(existing_items)
        generate_html(existing_items)
        return

    all_new_items = []

    for source in sources:
        new_items = fetch_rss(source, existing_links)
        all_new_items.extend(new_items)

    updated_items = all_new_items + existing_items

    save_data(updated_items)

    if all_new_items:
        print("\n✅ data.json 已更新")
        print(f"本次新增：{len(all_new_items)} 条")
        print(f"当前总数：{len(updated_items)} 条")
    else:
        print("\n✅ 没有发现新内容。")
        print("✅ data.json 已保存为 V2.0 数据结构。")

    generate_html(updated_items)

    print("\n✅ V2.0 运行结束。")


if __name__ == "__main__":
    main()