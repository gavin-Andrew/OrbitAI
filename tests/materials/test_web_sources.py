"""V4.2 官方网页只读试抓测试。"""

import json
import unittest
from unittest.mock import patch

from orbitai.materials.web_sources import (
    DiscoveredArticle,
    FirecrawlFetchError,
    WEBSITE_SOURCE_RULES,
    _crawl_document_for_url,
    _firecrawl_html_from_response,
    discover_article_candidates,
    fetch_firecrawl_crawl_html,
    fetch_firecrawl_html,
    fetch_source_page,
    parse_article_preview,
    preview_source,
)


ARTICLE_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta property="og:title" content="{title}">
    <meta property="article:published_time" content="2026-07-25">
  </head>
  <body>
    <nav>导航内容不应进入正文</nav>
    <main>
      <article>
        <h1>{title}</h1>
        <p>{paragraph}</p>
        <p>{paragraph}</p>
      </article>
    </main>
    <footer>页脚内容不应进入正文</footer>
  </body>
</html>
"""


class WebsiteSourceTests(unittest.TestCase):
    def test_all_four_sources_have_independent_official_path_rules(self):
        self.assertEqual(
            set(WEBSITE_SOURCE_RULES),
            {"anthropic", "meta_ai", "deepseek", "spacexai"},
        )
        accepted_urls = {
            "anthropic": "https://www.anthropic.com/news/claude-example",
            "meta_ai": "https://ai.meta.com/blog/llama-example/",
            "deepseek": (
                "https://api-docs.deepseek.com/zh-cn/news/news-example/"
            ),
            "spacexai": "https://x.ai/news/grok-example",
        }

        for source_id, url in accepted_urls.items():
            with self.subTest(source_id=source_id):
                self.assertTrue(
                    WEBSITE_SOURCE_RULES[source_id].accepts_article_url(url)
                )

        self.assertFalse(
            WEBSITE_SOURCE_RULES["anthropic"].accepts_article_url(
                "https://github.com/anthropics/claude-code/releases/tag/v1"
            )
        )
        self.assertFalse(
            WEBSITE_SOURCE_RULES["deepseek"].accepts_article_url(
                "https://api-docs.deepseek.com/zh-cn/updates/"
            )
        )
        self.assertTrue(
            WEBSITE_SOURCE_RULES["deepseek"].accepts_article_url(
                "https://api-docs.deepseek.com/news/news-example"
            )
        )

    def test_discovery_enforces_host_path_and_deduplicates(self):
        rule = WEBSITE_SOURCE_RULES["anthropic"]
        html = """
        <main>
          <article>
            <time datetime="2026-07-24">Jul 24, 2026</time>
            <a href="/news/claude-example">Claude Example</a>
          </article>
          <a href="https://www.anthropic.com/news/claude-example">
            重复链接
          </a>
          <a href="/research/not-news">研究页</a>
          <a href="https://evil.example/news/fake">外部链接</a>
        </main>
        """

        candidates = discover_article_candidates(rule, html)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].url,
            "https://www.anthropic.com/news/claude-example",
        )
        self.assertEqual(candidates[0].title_hint, "Claude Example")
        self.assertEqual(candidates[0].published_hint, "2026-07-24")

    def test_each_source_parses_title_date_and_readable_body(self):
        accepted_urls = {
            "anthropic": "https://www.anthropic.com/news/claude-example",
            "meta_ai": "https://ai.meta.com/blog/llama-example/",
            "deepseek": (
                "https://api-docs.deepseek.com/zh-cn/news/news-example/"
            ),
            "spacexai": "https://x.ai/news/grok-example",
        }
        paragraph = "这是一段用于验证正文提取规则的官方文章内容。" * 20

        for source_id, url in accepted_urls.items():
            rule = WEBSITE_SOURCE_RULES[source_id]
            article = parse_article_preview(
                rule,
                DiscoveredArticle(url=url),
                ARTICLE_TEMPLATE.format(
                    title=f"{rule.name} 测试文章",
                    paragraph=paragraph,
                ),
            )

            with self.subTest(source_id=source_id):
                self.assertEqual(article.status, "ready")
                self.assertEqual(article.published, "2026-07-25")
                self.assertIn("测试文章", article.title)
                self.assertGreaterEqual(
                    article.content_length,
                    rule.minimum_body_chars,
                )
                self.assertNotIn("导航内容", article.content_text)
                self.assertNotIn("页脚内容", article.content_text)

    def test_missing_date_is_held_for_review(self):
        rule = WEBSITE_SOURCE_RULES["deepseek"]
        paragraph = "有效正文内容。" * 100
        html = f"""
        <html><body><article>
          <h1>没有发布日期的文章</h1>
          <p>{paragraph}</p>
        </article></body></html>
        """

        article = parse_article_preview(
            rule,
            DiscoveredArticle(
                url=(
                    "https://api-docs.deepseek.com/"
                    "zh-cn/news/news-example/"
                )
            ),
            html,
        )

        self.assertEqual(article.status, "needs_review")
        self.assertIn("missing_published_date", article.issues)

    def test_preview_is_injected_and_does_not_require_database(self):
        rule = WEBSITE_SOURCE_RULES["spacexai"]
        article_url = "https://x.ai/news/grok-example"
        paragraph = "可供计算机读取的官方正文。" * 40
        responses = {
            rule.listing_url: (
                '<main><time datetime="2026-07-25"></time>'
                f'<a href="{article_url}">Grok Example</a></main>'
            ),
            article_url: ARTICLE_TEMPLATE.format(
                title="Grok Example",
                paragraph=paragraph,
            ),
        }
        requested_urls = []

        def fetcher(url):
            requested_urls.append(url)
            return responses[url]

        report = preview_source(
            rule,
            limit=1,
            fetcher=fetcher,
            request_delay_seconds=0,
        )

        self.assertTrue(report.ok)
        self.assertEqual(report.ready_count, 1)
        self.assertEqual(requested_urls, [rule.listing_url, article_url])
        self.assertEqual(report.items[0].status, "ready")
        self.assertEqual(report.listing_fetch_provider, "injected")
        self.assertEqual(report.items[0].fetch_provider, "injected")

    def test_spacexai_uses_firecrawl_only_after_direct_failure(self):
        rule = WEBSITE_SOURCE_RULES["spacexai"]
        calls = []

        def direct_fetcher(url):
            calls.append(("direct", url))
            raise RuntimeError("HTTP 403")

        def firecrawl_fetcher(url):
            calls.append(("firecrawl", url))
            return "<html><main>SpaceXAI News</main></html>"

        page = fetch_source_page(
            rule,
            rule.listing_url,
            direct_fetcher=direct_fetcher,
            firecrawl_fetcher=firecrawl_fetcher,
        )

        self.assertEqual(page.provider, "firecrawl")
        self.assertIn("SpaceXAI", page.html)
        self.assertEqual(
            calls,
            [
                ("direct", rule.listing_url),
                ("firecrawl", rule.listing_url),
            ],
        )

    def test_other_sources_never_fall_back_to_firecrawl(self):
        rule = WEBSITE_SOURCE_RULES["anthropic"]
        fallback_calls = []

        def direct_fetcher(_url):
            raise RuntimeError("temporary failure")

        def firecrawl_fetcher(url):
            fallback_calls.append(url)
            return "<html></html>"

        with self.assertRaisesRegex(RuntimeError, "temporary failure"):
            fetch_source_page(
                rule,
                rule.listing_url,
                direct_fetcher=direct_fetcher,
                firecrawl_fetcher=firecrawl_fetcher,
            )

        self.assertEqual(fallback_calls, [])

    def test_firecrawl_refuses_missing_key_and_non_xai_url(self):
        with self.assertRaisesRegex(
            FirecrawlFetchError,
            "未配置 FIRECRAWL_API_KEY",
        ):
            fetch_firecrawl_html(
                "https://x.ai/news",
                api_key="",
            )

        with self.assertRaisesRegex(
            FirecrawlFetchError,
            "仅允许读取 SpaceXAI News",
        ):
            fetch_firecrawl_html(
                "https://example.com/news",
                api_key="test-key",
            )

    def test_firecrawl_sends_bearer_key_and_parses_html_and_links(self):
        response_body = (
            b'{"success":true,"data":{'
            b'"html":"<main>News</main>",'
            b'"links":["https://x.ai/news/grok-example"],'
            b'"metadata":{"sourceURL":"https://x.ai/news"}}}'
        )

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return response_body

        with patch(
            "orbitai.materials.web_sources.urlopen",
            return_value=FakeResponse(),
        ) as mocked_urlopen:
            page_html = fetch_firecrawl_html(
                "https://x.ai/news",
                api_key="test-secret",
                retry_times=1,
            )

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer test-secret",
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("<main>News</main>", page_html)
        self.assertIn("https://x.ai/news/grok-example", page_html)

    def test_targeted_crawl_limits_scope_and_accepts_exact_url_only(self):
        target_url = "https://x.ai/news/grok-example"
        article_markdown = (
            "# Grok Example\n\n"
            "Jul 25, 2026\n\n"
            + "这是通过精确目标页 Crawl 取得的正文。" * 40
        )
        responses = [
            {
                "success": True,
                "id": "crawl_job_12345678",
            },
            {
                "status": "scraping",
                "data": [],
            },
            {
                "status": "completed",
                "data": [
                    {
                        "markdown": article_markdown,
                        "metadata": {
                            "sourceURL": target_url,
                            "url": target_url,
                        },
                    },
                ],
            },
        ]

        class FakeResponse:
            def __init__(self, value):
                self.body = json.dumps(value).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return self.body

        with patch(
            "orbitai.materials.web_sources.urlopen",
            side_effect=[FakeResponse(value) for value in responses],
        ) as mocked_urlopen:
            page_html = fetch_firecrawl_crawl_html(
                target_url,
                api_key="test-secret",
                retry_times=1,
                poll_seconds=0,
                crawl_timeout_seconds=5,
            )

        self.assertIn("Grok Example", page_html)
        self.assertIn("精确目标页 Crawl", page_html)

        start_request = mocked_urlopen.call_args_list[0].args[0]
        start_payload = json.loads(start_request.data.decode("utf-8"))
        self.assertEqual(start_request.get_method(), "POST")
        self.assertEqual(start_payload["url"], target_url)
        self.assertEqual(start_payload["limit"], 1)
        self.assertEqual(start_payload["maxDiscoveryDepth"], 0)
        self.assertEqual(start_payload["maxConcurrency"], 1)
        self.assertEqual(start_payload["sitemap"], "skip")
        self.assertNotIn("includePaths", start_payload)
        self.assertFalse(start_payload["crawlEntireDomain"])
        self.assertFalse(start_payload["allowExternalLinks"])
        self.assertFalse(start_payload["allowSubdomains"])

        poll_requests = [
            call.args[0]
            for call in mocked_urlopen.call_args_list[1:]
        ]
        self.assertTrue(
            all(request.get_method() == "GET" for request in poll_requests)
        )
        self.assertTrue(
            all(
                request.full_url.endswith("/crawl_job_12345678")
                for request in poll_requests
            )
        )

    def test_completed_crawl_without_exact_target_fails_closed(self):
        with self.assertRaisesRegex(
            FirecrawlFetchError,
            "没有返回请求的精确详情页",
        ):
            _crawl_document_for_url(
                {
                    "status": "completed",
                    "data": [
                        {
                            "markdown": "# 目录或其他详情页",
                            "metadata": {
                                "sourceURL": (
                                    "https://x.ai/news/other-page"
                                ),
                            },
                        },
                    ],
                },
                "https://x.ai/news/grok-example",
            )

    def test_completed_crawl_with_multiple_documents_fails_closed(self):
        with self.assertRaisesRegex(
            FirecrawlFetchError,
            "必须且只能返回一个文档",
        ):
            _crawl_document_for_url(
                {
                    "status": "completed",
                    "data": [
                        {
                            "metadata": {
                                "sourceURL": (
                                    "https://x.ai/news/grok-example"
                                ),
                            },
                        },
                        {
                            "metadata": {
                                "sourceURL": (
                                    "https://x.ai/news/other-page"
                                ),
                            },
                        },
                    ],
                },
                "https://x.ai/news/grok-example",
            )

    def test_completed_crawl_rejects_conflicting_metadata_urls(self):
        with self.assertRaisesRegex(
            FirecrawlFetchError,
            "没有返回请求的精确详情页",
        ):
            _crawl_document_for_url(
                {
                    "status": "completed",
                    "data": [
                        {
                            "metadata": {
                                "sourceURL": (
                                    "https://x.ai/news/grok-example"
                                ),
                                "url": "https://x.ai/news/other-page",
                            },
                        },
                    ],
                },
                "https://x.ai/news/grok-example",
            )

    def test_targeted_crawl_refuses_listing_page(self):
        with self.assertRaisesRegex(
            FirecrawlFetchError,
            "仅允许读取 SpaceXAI News 详情页",
        ):
            fetch_firecrawl_crawl_html(
                "https://x.ai/news",
                api_key="test-secret",
            )

    def test_firecrawl_prefers_markdown_over_error_shell_html(self):
        markdown = (
            "# Introducing Grok Example\n\n"
            "Jul 25, 2026\n\n"
            + "正文内容足以供现有解析器读取。" * 40
        )

        page_html = _firecrawl_html_from_response(
            {
                "success": True,
                "data": {
                    "html": "<main><h1>Something went wrong</h1></main>",
                    "markdown": markdown,
                    "metadata": {
                        "sourceURL": (
                            "https://x.ai/news/grok-example"
                        ),
                    },
                },
            },
            "https://x.ai/news/grok-example",
        )
        article = parse_article_preview(
            WEBSITE_SOURCE_RULES["spacexai"],
            DiscoveredArticle(
                url="https://x.ai/news/grok-example",
            ),
            page_html,
        )

        self.assertEqual(article.status, "ready")
        self.assertEqual(article.title, "Introducing Grok Example")
        self.assertEqual(article.published, "Jul 25, 2026")

    def test_firecrawl_rejects_spacexai_error_shell(self):
        with self.assertRaisesRegex(
            FirecrawlFetchError,
            "错误页",
        ):
            _firecrawl_html_from_response(
                {
                    "success": True,
                    "data": {
                        "html": (
                            "<main><h1>Something went wrong</h1>"
                            "<p>An unexpected error occurred. "
                            "Try refreshing the page.</p></main>"
                        ),
                        "metadata": {
                            "sourceURL": (
                                "https://x.ai/news/grok-example"
                            ),
                        },
                    },
                },
                "https://x.ai/news/grok-example",
            )


if __name__ == "__main__":
    unittest.main()
