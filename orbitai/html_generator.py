from datetime import datetime
from html import escape

from orbitai.config import (
    HTML_FILE,
    FEATURED_FILE,
    FEATURED_SCORE_THRESHOLD,
    FEATURED_MAX_ITEMS,
)
from orbitai.ai_processor import item_is_ai_complete
from orbitai.scoring import sort_items_by_score, get_featured_items
from orbitai.text_utils import clean_html, truncate_text


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
    优先显示 AI 中文标题。
    """
    ai = item.get("ai", {})
    title_cn = ai.get("title_cn", "")

    if title_cn:
        return title_cn

    return item.get("title", "无标题")


def get_display_summary(item):
    """
    页面展示摘要。
    优先显示 AI 中文摘要。
    """
    ai = item.get("ai", {})
    ai_summary = ai.get("summary", "")

    if ai_summary:
        return ai_summary

    return item.get("summary_original", "")


def get_display_category(item):
    """
    页面展示分类。
    优先使用 AI 分类；如果没有 AI 分类，则回退到规则分类。
    """
    ai = item.get("ai", {})
    ai_category = ai.get("category", "")

    if ai_category:
        return ai_category

    return item.get("category_rule", "其他")


def generate_html(
    items,
    output_file=HTML_FILE,
    page_title="OrbitAI",
    page_subtitle="Personal AI Information Radar",
    stat_label="总信息数",
    sort_by_score=False,
):
    """
    根据 data.json 里的数据生成本地 HTML 页面。
    支持生成：
    - index.html：全部信息页
    - featured.html：精选信息页
    """
    if sort_by_score:
        sorted_items = sort_items_by_score(items)
    else:
        sorted_items = sort_items(items)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sources = sorted({item.get("source", "未知来源") for item in sorted_items})
    categories = sorted({get_display_category(item) for item in sorted_items})

    all_tags = set()
    for item in sorted_items:
        tags = item.get("ai", {}).get("tags", [])
        if isinstance(tags, list):
            all_tags.update(str(tag) for tag in tags if str(tag).strip())

    tags = sorted(all_tags)

    ai_processed_count = sum(
        1 for item in sorted_items
        if item_is_ai_complete(item)
    )

    source_options = "\n".join(
        f'<option value="{escape(source)}">{escape(source)}</option>'
        for source in sources
    )

    category_options = "\n".join(
        f'<option value="{escape(category)}">{escape(category)}</option>'
        for category in categories
    )

    tag_options = "\n".join(
        f'<option value="{escape(tag)}">{escape(tag)}</option>'
        for tag in tags
    )

    if output_file == FEATURED_FILE:
        nav_html = """
            <nav class="nav">
                <a class="nav-link" href="index.html">全部信息</a>
                <a class="nav-link active" href="featured.html">精选信息</a>
            </nav>
        """
    else:
        nav_html = """
            <nav class="nav">
                <a class="nav-link active" href="index.html">全部信息</a>
                <a class="nav-link" href="featured.html">精选信息</a>
            </nav>
        """

    article_cards = []

    for item in sorted_items:
        title_raw = item.get("title", "无标题")
        display_title_raw = get_display_title(item)
        source_raw = item.get("source", "未知来源")
        category_raw = get_display_category(item)
        final_score_raw = item.get("ai", {}).get("final_score")
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

        score_html = ""

        if final_score_raw is not None:
            try:
                score_text = str(round(float(final_score_raw), 1))
                score_html = f'<span class="score">综合分：{escape(score_text)}</span>'
            except (TypeError, ValueError):
                score_html = ""

        tags_text = " ".join(tags)
        tags_data = escape("||".join(tags))

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
        <article class="card" data-source="{source}" data-category="{category}" data-tags="{tags_data}" data-search="{search_text}">
            <div class="meta">
                <span class="source">{source}</span>
                <span class="category">{category}</span>
                {score_html}
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
    <title>{page_title}</title>
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

        .nav {{
            display: flex;
            gap: 10px;
            margin: -12px 0 24px;
        }}

        .nav-link {{
            display: inline-block;
            padding: 8px 14px;
            border-radius: 999px;
            background: white;
            color: #2563eb;
            font-size: 14px;
            font-weight: 700;
            text-decoration: none;
            border: 1px solid #dbeafe;
        }}

        .nav-link:hover {{
            background: #eff6ff;
        }}

        .nav-link.active {{
            background: #2563eb;
            color: white;
            border-color: #2563eb;
        }}

        .controls {{
            display: grid;
            grid-template-columns: 1fr 160px 160px 160px;
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

        .score {{
            padding: 2px 8px;
            border-radius: 999px;
            background: #ecfdf5;
            color: #047857;
            font-size: 13px;
            font-weight: 700;
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
            <h1>{page_title}</h1>
            <p>{page_subtitle}</p>
            <div class="stats">
                <span class="stat">{stat_label}：{len(sorted_items)}</span>
                <span class="stat">AI 已处理：{ai_processed_count}</span>
                <span class="stat">生成时间：{generated_at}</span>
            </div>
        </section>

        {nav_html}

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

            <select id="tagFilter">
                <option value="all">全部标签</option>
                {tag_options}
            </select>

            <div id="resultCount" class="result-count"></div>
        </section>

        <section class="feed">
            {cards_html}
        </section>

        <footer class="footer">
            Generated locally by OrbitAI V2.5
        </footer>
    </main>
<script>
    const searchInput = document.getElementById("searchInput");
    const sourceFilter = document.getElementById("sourceFilter");
    const categoryFilter = document.getElementById("categoryFilter");
    const tagFilter = document.getElementById("tagFilter");
    const resultCount = document.getElementById("resultCount");
    const cards = Array.from(document.querySelectorAll(".card"));

    function updateCards() {{
        const searchValue = searchInput.value.trim().toLowerCase();
        const selectedSource = sourceFilter.value;
        const selectedCategory = categoryFilter.value;
        const selectedTag = tagFilter.value;

        let visibleCount = 0;

        cards.forEach((card) => {{
            const cardSource = card.dataset.source;
            const cardCategory = card.dataset.category;
            const cardTags = card.dataset.tags || "";
            const cardSearch = card.dataset.search;

            const matchesSearch = !searchValue || cardSearch.includes(searchValue);
            const matchesSource = selectedSource === "all" || cardSource === selectedSource;
            const matchesCategory = selectedCategory === "all" || cardCategory === selectedCategory;
            const matchesTag = selectedTag === "all" || cardTags.split("||").includes(selectedTag);

            const shouldShow = matchesSearch && matchesSource && matchesCategory && matchesTag;

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
    tagFilter.addEventListener("change", updateCards);

    updateCards();
</script>
</body>
</html>
"""

    with output_file.open("w", encoding="utf-8") as file:
        file.write(html_content)

    print(f"\n✅ {output_file} 已生成。")


def generate_featured_html(items):
    """
    生成 V2.4 精选页 featured.html。
    精选页复用主页样式，但只展示综合分较高的信息。
    """
    featured_items = get_featured_items(items)

    generate_html(
        featured_items,
        output_file=FEATURED_FILE,
        page_title="OrbitAI Featured",
        page_subtitle=f"精选 AI 信息｜阈值 {FEATURED_SCORE_THRESHOLD}，最多 {FEATURED_MAX_ITEMS} 条",
        stat_label="精选信息数",
        sort_by_score=True,
    )