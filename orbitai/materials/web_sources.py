"""V4.2 官方网页来源的只读发现与正文解析。"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import ssl
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable
from urllib.error import HTTPError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import certifi
from bs4 import BeautifulSoup, Tag

from orbitai.core.config import (
    FIRECRAWL_API_KEY,
    FIRECRAWL_CRAWL_POLL_SECONDS,
    FIRECRAWL_CRAWL_TIMEOUT_SECONDS,
    FIRECRAWL_RETRY_DELAY_SECONDS,
    FIRECRAWL_RETRY_TIMES,
    FIRECRAWL_TIMEOUT_SECONDS,
)


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_RETRY_TIMES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1
DEFAULT_REQUEST_DELAY_SECONDS = 0.25
DEFAULT_PREVIEW_LIMIT = 2
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"
FIRECRAWL_CRAWL_URL = "https://api.firecrawl.dev/v2/crawl"
SPACEXAI_DIRECT_TIMEOUT_SECONDS = 8

_SPACE_PATTERN = re.compile(r"\s+")
_DATE_PATTERNS = (
    re.compile(
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{1,2},\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
        r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
        r"Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b"),
    re.compile(r"\b\d{4}年\d{1,2}月\d{1,2}日\b"),
)


class WebsiteFetchError(RuntimeError):
    """官网页面无法安全读取。"""


class FirecrawlFetchError(WebsiteFetchError):
    """Firecrawl 后备读取失败。"""


@dataclass(frozen=True)
class WebsiteSourceRule:
    """一家公司官网入口的独立发现与正文规则。"""

    id: str
    organization_id: str
    name: str
    listing_url: str
    allowed_hosts: tuple[str, ...]
    article_path_pattern: str
    content_selectors: tuple[str, ...]
    minimum_body_chars: int = 240

    def accepts_article_url(self, url: str) -> bool:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and hostname in self.allowed_hosts
            and re.fullmatch(
                self.article_path_pattern,
                parsed.path,
                flags=re.IGNORECASE,
            )
            is not None
        )


WEBSITE_SOURCE_RULES: dict[str, WebsiteSourceRule] = {
    "anthropic": WebsiteSourceRule(
        id="anthropic",
        organization_id="anthropic",
        name="Anthropic Newsroom",
        listing_url="https://www.anthropic.com/news",
        allowed_hosts=("www.anthropic.com", "anthropic.com"),
        article_path_pattern=r"/news/[^/]+/?",
        content_selectors=(
            "article",
            "main [data-pagefind-body]",
            "main",
        ),
    ),
    "meta_ai": WebsiteSourceRule(
        id="meta_ai",
        organization_id="meta_ai",
        name="Meta AI Blog",
        listing_url="https://ai.meta.com/blog/",
        allowed_hosts=("ai.meta.com",),
        article_path_pattern=r"/blog/[^/]+/?",
        content_selectors=(
            "article",
            "main",
            "body",
        ),
    ),
    "deepseek": WebsiteSourceRule(
        id="deepseek",
        organization_id="deepseek",
        name="DeepSeek News",
        listing_url="https://api-docs.deepseek.com/zh-cn/news/",
        allowed_hosts=("api-docs.deepseek.com",),
        article_path_pattern=r"(?:/zh-cn)?/news/[^/]+/?",
        content_selectors=(
            "article",
            ".theme-doc-markdown",
            "main",
        ),
        minimum_body_chars=180,
    ),
    "spacexai": WebsiteSourceRule(
        id="spacexai",
        organization_id="spacexai",
        name="SpaceXAI News",
        listing_url="https://x.ai/news",
        allowed_hosts=("x.ai", "www.x.ai"),
        article_path_pattern=r"/news/[^/]+/?",
        content_selectors=(
            "article",
            "main",
        ),
    ),
}


@dataclass(frozen=True)
class DiscoveredArticle:
    url: str
    title_hint: str = ""
    published_hint: str = ""


@dataclass(frozen=True)
class FetchedWebsitePage:
    html: str
    provider: str


@dataclass
class WebsiteArticlePreview:
    source_id: str
    source_name: str
    organization_id: str
    url: str
    title: str
    published: str
    content_text: str
    status: str
    fetch_provider: str = ""
    issues: list[str] = field(default_factory=list)

    @property
    def content_length(self) -> int:
        return len(self.content_text)

    def to_dict(self, *, include_content: bool = False) -> dict:
        result = asdict(self)
        result["content_length"] = self.content_length
        if not include_content:
            result.pop("content_text", None)
            result["content_preview"] = _truncate(self.content_text, 240)
        return result


@dataclass
class WebsiteSourcePreview:
    source_id: str
    source_name: str
    listing_url: str
    discovered_count: int
    listing_fetch_provider: str = ""
    items: list[WebsiteArticlePreview] = field(default_factory=list)
    error: str = ""

    @property
    def ready_count(self) -> int:
        return sum(item.status == "ready" for item in self.items)

    @property
    def ok(self) -> bool:
        return not self.error and self.discovered_count > 0

    def to_dict(self, *, include_content: bool = False) -> dict:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "listing_url": self.listing_url,
            "listing_fetch_provider": self.listing_fetch_provider,
            "ok": self.ok,
            "error": self.error,
            "discovered_count": self.discovered_count,
            "fetched_count": len(self.items),
            "ready_count": self.ready_count,
            "items": [
                item.to_dict(include_content=include_content)
                for item in self.items
            ],
        }


def _normalize_text(value: str | None) -> str:
    return _SPACE_PATTERN.sub(" ", value or "").strip()


def _truncate(value: str, limit: int) -> str:
    normalized = _normalize_text(value)
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def canonicalize_url(base_url: str, href: str) -> str:
    """把页面内链接整理成不含查询参数和片段的规范 URL。"""
    absolute = urljoin(base_url, href.strip())
    parsed = urlsplit(absolute)
    hostname = (parsed.hostname or "").lower()
    netloc = hostname
    if parsed.port:
        netloc = f"{hostname}:{parsed.port}"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path or "/",
            "",
            "",
        )
    )


def _find_date_in_text(value: str) -> str:
    normalized = _normalize_text(value)
    for pattern in _DATE_PATTERNS:
        matched = pattern.search(normalized)
        if matched:
            return matched.group(0)
    return ""


def _date_hint_near_anchor(anchor: Tag) -> str:
    for parent in (anchor, *list(anchor.parents)[:4]):
        if not isinstance(parent, Tag):
            continue
        time_tag = parent.find("time")
        if time_tag is not None:
            value = time_tag.get("datetime") or time_tag.get_text(
                " ",
                strip=True,
            )
            if _normalize_text(value):
                return _normalize_text(value)
        text = parent.get_text(" ", strip=True)
        if len(text) <= 1200:
            matched = _find_date_in_text(text)
            if matched:
                return matched
    return ""


def discover_article_candidates(
    rule: WebsiteSourceRule,
    listing_html: str,
) -> list[DiscoveredArticle]:
    """从公司新闻列表中发现符合白名单路径的文章链接。"""
    soup = BeautifulSoup(listing_html, "html.parser")
    candidates: dict[str, DiscoveredArticle] = {}

    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not isinstance(href, str) or not href.strip():
            continue

        url = canonicalize_url(rule.listing_url, href)
        if not rule.accepts_article_url(url):
            continue

        title_hint = _normalize_text(anchor.get_text(" ", strip=True))
        published_hint = _date_hint_near_anchor(anchor)
        existing = candidates.get(url)

        if existing is None:
            candidates[url] = DiscoveredArticle(
                url=url,
                title_hint=title_hint,
                published_hint=published_hint,
            )
            continue

        candidates[url] = DiscoveredArticle(
            url=url,
            title_hint=existing.title_hint or title_hint,
            published_hint=existing.published_hint or published_hint,
        )

    return list(candidates.values())


def _walk_json(value) -> Iterable[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _article_json_ld(soup: BeautifulSoup) -> dict:
    supported_types = {
        "article",
        "blogposting",
        "newsarticle",
        "report",
        "techarticle",
    }
    fallback: dict = {}

    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue

        for item in _walk_json(value):
            item_type = item.get("@type", "")
            values = item_type if isinstance(item_type, list) else [item_type]
            normalized_types = {
                str(entry).lower()
                for entry in values
            }
            if normalized_types & supported_types:
                return item
            if not fallback and (
                item.get("headline")
                or item.get("datePublished")
                or item.get("articleBody")
            ):
                fallback = item

    return fallback


def _meta_content(
    soup: BeautifulSoup,
    *,
    attribute: str,
    value: str,
) -> str:
    tag = soup.find(
        "meta",
        attrs={attribute: re.compile(f"^{re.escape(value)}$", re.IGNORECASE)},
    )
    if tag is None:
        return ""
    content = tag.get("content")
    return _normalize_text(content if isinstance(content, str) else "")


def _extract_title(
    soup: BeautifulSoup,
    json_ld: dict,
    title_hint: str,
) -> str:
    headline = json_ld.get("headline")
    if isinstance(headline, str) and _normalize_text(headline):
        return _normalize_text(headline)

    for attribute, value in (
        ("property", "og:title"),
        ("name", "twitter:title"),
    ):
        title = _meta_content(
            soup,
            attribute=attribute,
            value=value,
        )
        if title:
            return title

    heading = soup.find("h1")
    if heading is not None:
        title = _normalize_text(heading.get_text(" ", strip=True))
        if title:
            return title

    if title_hint:
        return _normalize_text(title_hint)

    if soup.title is not None:
        return _normalize_text(soup.title.get_text(" ", strip=True))

    return ""


def _extract_published(
    soup: BeautifulSoup,
    json_ld: dict,
    published_hint: str,
) -> str:
    date_published = json_ld.get("datePublished")
    if isinstance(date_published, str) and _normalize_text(date_published):
        return _normalize_text(date_published)

    for attribute, value in (
        ("property", "article:published_time"),
        ("name", "date"),
        ("name", "datePublished"),
        ("name", "parsely-pub-date"),
        ("name", "sailthru.date"),
    ):
        published = _meta_content(
            soup,
            attribute=attribute,
            value=value,
        )
        if published:
            return published

    for time_tag in soup.find_all("time"):
        value = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        if _normalize_text(value):
            return _normalize_text(value)

    if published_hint:
        return _normalize_text(published_hint)

    visible_text = soup.get_text(" ", strip=True)
    return _find_date_in_text(visible_text[:6000])


def _clean_content_node(node: Tag) -> str:
    for unwanted in node.select(
        "script, style, noscript, nav, footer, header, form, "
        "button, svg, canvas, iframe"
    ):
        unwanted.decompose()

    blocks = []
    for block in node.select("h2, h3, h4, p, li, blockquote, pre"):
        text = _normalize_text(block.get_text(" ", strip=True))
        if not text or (blocks and blocks[-1] == text):
            continue
        blocks.append(text)

    if not blocks:
        return _normalize_text(node.get_text(" ", strip=True))

    return "\n\n".join(blocks)


def _extract_content(
    soup: BeautifulSoup,
    json_ld: dict,
    rule: WebsiteSourceRule,
) -> str:
    longest = ""

    for selector in rule.content_selectors:
        if selector == "body":
            continue
        for node in soup.select(selector):
            content = _clean_content_node(node)
            if len(content) > len(longest):
                longest = content
            if len(content) >= rule.minimum_body_chars:
                return content

    heading = soup.find("h1")
    if heading is not None:
        for parent in heading.parents:
            if not isinstance(parent, Tag) or parent.name in {
                "body",
                "html",
            }:
                break
            if len(parent.find_all("p")) < 3:
                continue
            content = _clean_content_node(parent)
            if len(content) > len(longest):
                longest = content
            if len(content) >= rule.minimum_body_chars:
                return content

    if "body" in rule.content_selectors and soup.body is not None:
        content = _clean_content_node(soup.body)
        if len(content) > len(longest):
            longest = content
        if len(content) >= rule.minimum_body_chars:
            return content

    article_body = json_ld.get("articleBody")
    if isinstance(article_body, str):
        normalized = _normalize_text(article_body)
        if len(normalized) > len(longest):
            longest = normalized

    return longest


def parse_article_preview(
    rule: WebsiteSourceRule,
    candidate: DiscoveredArticle,
    article_html: str,
) -> WebsiteArticlePreview:
    """把一篇官网详情页解析成只读预览，不创建材料或数据库记录。"""
    soup = BeautifulSoup(article_html, "html.parser")
    json_ld = _article_json_ld(soup)
    title = _extract_title(soup, json_ld, candidate.title_hint)
    published = _extract_published(
        soup,
        json_ld,
        candidate.published_hint,
    )
    content = _extract_content(soup, json_ld, rule)

    issues = []
    if not title:
        issues.append("missing_title")
    if not published:
        issues.append("missing_published_date")
    if len(content) < rule.minimum_body_chars:
        issues.append("body_too_short")

    if "missing_title" in issues or "body_too_short" in issues:
        status = "failed"
    elif issues:
        status = "needs_review"
    else:
        status = "ready"

    return WebsiteArticlePreview(
        source_id=rule.id,
        source_name=rule.name,
        organization_id=rule.organization_id,
        url=candidate.url,
        title=title,
        published=published,
        content_text=content,
        status=status,
        issues=issues,
    )


def fetch_html(
    url: str,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    retry_times: int = DEFAULT_RETRY_TIMES,
    retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
) -> str:
    """使用固定身份、大小上限和有限重试读取公开 HTML。"""
    last_error: Exception | None = None
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    for attempt in range(1, retry_times + 1):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": (
                        "OrbitAI/4.2 "
                        "(read-only official website research preview)"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            with urlopen(
                request,
                timeout=timeout_seconds,
                context=ssl_context,
            ) as response:
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise WebsiteFetchError(
                        f"不支持的内容类型：{content_type}"
                    )

                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise WebsiteFetchError("页面超过 5 MiB 安全上限")

                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception as error:
            last_error = error
            if attempt < retry_times:
                time.sleep(retry_delay_seconds)

    raise WebsiteFetchError(
        f"读取失败（已尝试 {retry_times} 次）：{last_error}"
    )


def _accepts_spacexai_fetch_url(url: str) -> bool:
    rule = WEBSITE_SOURCE_RULES["spacexai"]
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() in rule.allowed_hosts
        and (path == "/news" or rule.accepts_article_url(url))
    )


def _firecrawl_error_for_status(status: int) -> FirecrawlFetchError:
    if status in {401, 403}:
        return FirecrawlFetchError("Firecrawl API 密钥无效或无访问权限")
    if status == 402:
        return FirecrawlFetchError("Firecrawl 账户额度不足")
    if status == 429:
        return FirecrawlFetchError("Firecrawl 请求触发限流")
    return FirecrawlFetchError(f"Firecrawl 返回 HTTP {status}")


def _html_visible_text_length(value: str) -> int:
    if not value.strip():
        return 0
    return len(
        _normalize_text(
            BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        )
    )


def _markdown_as_article_html(markdown: str, metadata: dict) -> str:
    lines = [line.strip() for line in markdown.splitlines()]
    title = ""
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                break
    if not title:
        metadata_title = metadata.get("title")
        if isinstance(metadata_title, str):
            title = _normalize_text(metadata_title)

    published = _find_date_in_text(markdown[:4000])
    head = ""
    if published:
        head = (
            '<meta property="article:published_time" '
            f'content="{html_lib.escape(published, quote=True)}">'
        )

    blocks = []
    for block in re.split(r"\n\s*\n", markdown):
        normalized = block.strip()
        if not normalized:
            continue
        blocks.append(
            f"<p>{html_lib.escape(normalized)}</p>"
        )

    return (
        f"<html><head>{head}</head><body><article>"
        f"<h1>{html_lib.escape(title)}</h1>"
        f"{''.join(blocks)}</article></body></html>"
    )


def _is_spacexai_error_shell(page_html: str) -> bool:
    text = _normalize_text(
        BeautifulSoup(page_html, "html.parser").get_text(" ", strip=True)
    ).lower()
    return (
        "something went wrong" in text
        and (
            "unexpected error occurred" in text
            or "try refreshing the page" in text
        )
    )


def _firecrawl_html_from_response(value: object, requested_url: str) -> str:
    if not isinstance(value, dict) or value.get("success") is not True:
        raise FirecrawlFetchError("Firecrawl 返回了失败响应")

    data = value.get("data")
    if not isinstance(data, dict):
        raise FirecrawlFetchError("Firecrawl 响应缺少 data")

    metadata_value = data.get("metadata")
    metadata = metadata_value if isinstance(metadata_value, dict) else {}
    if metadata:
        status_code = metadata.get("statusCode")
        if isinstance(status_code, int) and status_code >= 400:
            raise FirecrawlFetchError(
                f"SpaceXAI 页面返回 HTTP {status_code}"
            )
        for key in ("sourceURL", "url"):
            returned_url = metadata.get(key)
            if (
                isinstance(returned_url, str)
                and returned_url.strip()
                and not _accepts_spacexai_fetch_url(returned_url)
            ):
                raise FirecrawlFetchError(
                    f"Firecrawl 返回了白名单外地址：{returned_url}"
                )

    html_candidates = [
        value
        for value in (data.get("html"), data.get("rawHtml"))
        if isinstance(value, str) and value.strip()
    ]
    page_html = max(
        html_candidates,
        key=_html_visible_text_length,
        default="",
    )

    markdown = data.get("markdown")
    if (
        isinstance(markdown, str)
        and len(_normalize_text(markdown))
        > _html_visible_text_length(page_html)
    ):
        page_html = _markdown_as_article_html(markdown, metadata)

    safe_links = []
    links = data.get("links")
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, str):
                continue
            normalized = canonicalize_url(requested_url, link)
            if _accepts_spacexai_fetch_url(normalized):
                safe_links.append(normalized)

    if safe_links:
        anchors = "".join(
            f'<a href="{html_lib.escape(link, quote=True)}"></a>'
            for link in dict.fromkeys(safe_links)
        )
        page_html = (
            f"{page_html}<div data-orbitai-firecrawl-links>{anchors}</div>"
        )

    if not page_html.strip():
        raise FirecrawlFetchError("Firecrawl 响应没有可解析的 HTML")
    if _is_spacexai_error_shell(page_html):
        raise FirecrawlFetchError(
            "Firecrawl 取得的是 SpaceXAI 错误页，不是文章正文"
        )

    return page_html


def _resolve_firecrawl_api_key(api_key: str | None) -> str:
    resolved_api_key = FIRECRAWL_API_KEY if api_key is None else api_key
    if not resolved_api_key.strip():
        raise FirecrawlFetchError("未配置 FIRECRAWL_API_KEY")
    return resolved_api_key


def _request_firecrawl_json(
    endpoint: str,
    *,
    api_key: str,
    method: str,
    payload: dict | None = None,
    timeout_seconds: int = FIRECRAWL_TIMEOUT_SECONDS,
    retry_times: int = FIRECRAWL_RETRY_TIMES,
    retry_delay_seconds: int = FIRECRAWL_RETRY_DELAY_SECONDS,
) -> object:
    encoded_payload = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    last_error: Exception | None = None

    for attempt in range(1, retry_times + 1):
        request = Request(
            endpoint,
            data=encoded_payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "OrbitAI/4.2 (SpaceXAI read-only fallback)",
            },
            method=method,
        )
        try:
            with urlopen(
                request,
                timeout=timeout_seconds,
                context=ssl_context,
            ) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise FirecrawlFetchError(
                        "Firecrawl 响应超过 5 MiB 安全上限"
                    )
                try:
                    return json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise FirecrawlFetchError(
                        "Firecrawl 返回了无效 JSON"
                    ) from error
        except HTTPError as error:
            last_error = _firecrawl_error_for_status(error.code)
            should_retry = (
                error.code in {408, 429}
                or error.code >= 500
            )
            if not should_retry:
                raise last_error from error
        except FirecrawlFetchError:
            raise
        except Exception as error:
            last_error = error

        if attempt < retry_times:
            time.sleep(retry_delay_seconds)

    raise FirecrawlFetchError(
        f"Firecrawl 请求失败（已尝试 {retry_times} 次）：{last_error}"
    )


def fetch_firecrawl_scrape_html(
    url: str,
    *,
    api_key: str | None = None,
    timeout_seconds: int = FIRECRAWL_TIMEOUT_SECONDS,
    retry_times: int = FIRECRAWL_RETRY_TIMES,
    retry_delay_seconds: int = FIRECRAWL_RETRY_DELAY_SECONDS,
) -> str:
    """通过 Firecrawl Scrape 读取 SpaceXAI News 列表页。"""
    if not _accepts_spacexai_fetch_url(url):
        raise FirecrawlFetchError("Firecrawl 仅允许读取 SpaceXAI News 白名单")

    resolved_api_key = _resolve_firecrawl_api_key(api_key)
    is_listing_page = urlsplit(url).path.rstrip("/") == "/news"
    value = _request_firecrawl_json(
        FIRECRAWL_SCRAPE_URL,
        api_key=resolved_api_key,
        method="POST",
        payload={
            "url": url,
            "formats": ["markdown", "html", "rawHtml", "links"],
            "onlyMainContent": not is_listing_page,
            "onlyCleanContent": False,
            "maxAge": 60 * 60 * 1000,
            "waitFor": 0,
            "timeout": timeout_seconds * 1000,
            "blockAds": True,
            "proxy": "auto",
            "location": {
                "country": "US",
                "languages": ["en-US"],
            },
            "storeInCache": True,
        },
        timeout_seconds=timeout_seconds,
        retry_times=retry_times,
        retry_delay_seconds=retry_delay_seconds,
    )
    return _firecrawl_html_from_response(value, url)


def _spacexai_url_identity(url: str) -> tuple[str, str, str]:
    parsed = urlsplit(url)
    return (
        parsed.scheme.lower(),
        (parsed.hostname or "").lower(),
        parsed.path.rstrip("/") or "/",
    )


def _crawl_document_for_url(
    value: object,
    requested_url: str,
) -> dict | None:
    if not isinstance(value, dict):
        raise FirecrawlFetchError("Firecrawl Crawl 返回了无效响应")

    status = value.get("status")
    if status in {"failed", "cancelled"}:
        raise FirecrawlFetchError(
            f"Firecrawl Crawl 任务结束于异常状态：{status}"
        )
    if status in {"queued", "pending", "scraping"}:
        return None
    if status != "completed":
        raise FirecrawlFetchError(
            f"Firecrawl Crawl 返回未知状态：{status}"
        )

    documents = value.get("data")
    if not isinstance(documents, list):
        raise FirecrawlFetchError("Firecrawl Crawl 响应缺少 data")
    if len(documents) != 1:
        raise FirecrawlFetchError(
            "Firecrawl 定向 Crawl 必须且只能返回一个文档"
        )

    requested_identity = _spacexai_url_identity(requested_url)
    document = documents[0]
    if not isinstance(document, dict):
        raise FirecrawlFetchError("Firecrawl Crawl 返回了无效文档")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise FirecrawlFetchError("Firecrawl Crawl 文档缺少元数据")

    returned_urls = [
        value.strip()
        for key in ("sourceURL", "url")
        if isinstance((value := metadata.get(key)), str)
        and value.strip()
    ]
    if (
        returned_urls
        and all(
            _spacexai_url_identity(returned_url) == requested_identity
            for returned_url in returned_urls
        )
    ):
        return document

    raise FirecrawlFetchError(
        "Firecrawl Crawl 已完成，但没有返回请求的精确详情页"
    )


def fetch_firecrawl_crawl_html(
    url: str,
    *,
    api_key: str | None = None,
    timeout_seconds: int = FIRECRAWL_TIMEOUT_SECONDS,
    retry_times: int = FIRECRAWL_RETRY_TIMES,
    retry_delay_seconds: int = FIRECRAWL_RETRY_DELAY_SECONDS,
    poll_seconds: float = FIRECRAWL_CRAWL_POLL_SECONDS,
    crawl_timeout_seconds: int = FIRECRAWL_CRAWL_TIMEOUT_SECONDS,
) -> str:
    """对一个精确 SpaceXAI 详情 URL 启动 limit=1 的定向 Crawl。"""
    rule = WEBSITE_SOURCE_RULES["spacexai"]
    if not rule.accepts_article_url(url):
        raise FirecrawlFetchError(
            "Firecrawl Crawl 仅允许读取 SpaceXAI News 详情页"
        )
    if poll_seconds < 0 or crawl_timeout_seconds <= 0:
        raise FirecrawlFetchError("Firecrawl Crawl 轮询参数无效")

    resolved_api_key = _resolve_firecrawl_api_key(api_key)
    start_value = _request_firecrawl_json(
        FIRECRAWL_CRAWL_URL,
        api_key=resolved_api_key,
        method="POST",
        payload={
            "url": url,
            "maxDiscoveryDepth": 0,
            "sitemap": "skip",
            "ignoreQueryParameters": True,
            "limit": 1,
            "crawlEntireDomain": False,
            "allowExternalLinks": False,
            "allowSubdomains": False,
            "maxConcurrency": 1,
            "scrapeOptions": {
                "formats": ["markdown", "html", "rawHtml"],
                "onlyMainContent": True,
                "onlyCleanContent": False,
                "maxAge": 60 * 60 * 1000,
                "waitFor": 0,
                "timeout": timeout_seconds * 1000,
                "blockAds": True,
                "proxy": "auto",
                "location": {
                    "country": "US",
                    "languages": ["en-US"],
                },
                "storeInCache": True,
            },
        },
        timeout_seconds=timeout_seconds,
        retry_times=retry_times,
        retry_delay_seconds=retry_delay_seconds,
    )
    if (
        not isinstance(start_value, dict)
        or start_value.get("success") is not True
    ):
        raise FirecrawlFetchError("Firecrawl 未能创建 Crawl 任务")

    job_id = start_value.get("id")
    if (
        not isinstance(job_id, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{8,128}", job_id) is None
    ):
        raise FirecrawlFetchError("Firecrawl Crawl 响应缺少有效任务 ID")

    status_url = f"{FIRECRAWL_CRAWL_URL}/{quote(job_id, safe='')}"
    deadline = time.monotonic() + crawl_timeout_seconds

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FirecrawlFetchError(
                f"Firecrawl Crawl 在 {crawl_timeout_seconds} 秒内未完成"
            )
        poll_timeout_seconds = max(
            1,
            min(timeout_seconds, int(remaining)),
        )
        status_value = _request_firecrawl_json(
            status_url,
            api_key=resolved_api_key,
            method="GET",
            timeout_seconds=poll_timeout_seconds,
            retry_times=1,
            retry_delay_seconds=retry_delay_seconds,
        )
        document = _crawl_document_for_url(status_value, url)
        if document is not None:
            return _firecrawl_html_from_response(
                {
                    "success": True,
                    "data": document,
                },
                url,
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FirecrawlFetchError(
                f"Firecrawl Crawl 在 {crawl_timeout_seconds} 秒内未完成"
            )
        time.sleep(min(poll_seconds, remaining))


def fetch_firecrawl_html(
    url: str,
    **kwargs,
) -> str:
    """列表页使用 Scrape；精确详情页使用限额 Crawl。"""
    if urlsplit(url).path.rstrip("/") == "/news":
        return fetch_firecrawl_scrape_html(url, **kwargs)
    return fetch_firecrawl_crawl_html(url, **kwargs)


def fetch_source_page(
    rule: WebsiteSourceRule,
    url: str,
    *,
    direct_fetcher: Callable[[str], str] | None = None,
    firecrawl_fetcher: Callable[[str], str] | None = None,
) -> FetchedWebsitePage:
    """直连优先；仅 SpaceXAI 失败时启用 Firecrawl。"""
    if direct_fetcher is None:
        if rule.id == "spacexai":
            direct_fetcher = lambda target: fetch_html(
                target,
                timeout_seconds=SPACEXAI_DIRECT_TIMEOUT_SECONDS,
                retry_times=1,
            )
        else:
            direct_fetcher = fetch_html

    try:
        return FetchedWebsitePage(
            html=direct_fetcher(url),
            provider="direct",
        )
    except Exception as direct_error:
        if rule.id != "spacexai":
            raise

        active_firecrawl_fetcher = (
            fetch_firecrawl_html
            if firecrawl_fetcher is None
            else firecrawl_fetcher
        )
        if firecrawl_fetcher is not None:
            provider = "firecrawl"
        elif rule.accepts_article_url(url):
            provider = "firecrawl_crawl"
        else:
            provider = "firecrawl_scrape"

        try:
            return FetchedWebsitePage(
                html=active_firecrawl_fetcher(url),
                provider=provider,
            )
        except Exception as fallback_error:
            raise WebsiteFetchError(
                "SpaceXAI 官网直连失败；"
                f"Firecrawl 后备也失败：{fallback_error}"
            ) from direct_error


def preview_source(
    rule: WebsiteSourceRule,
    *,
    limit: int = DEFAULT_PREVIEW_LIMIT,
    fetcher: Callable[[str], str] | None = None,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
) -> WebsiteSourcePreview:
    """只读抓取一家公司的列表和少量详情页。"""
    def read_page(url: str) -> FetchedWebsitePage:
        if fetcher is not None:
            return FetchedWebsitePage(
                html=fetcher(url),
                provider="injected",
            )
        return fetch_source_page(rule, url)

    try:
        listing_page = read_page(rule.listing_url)
        candidates = discover_article_candidates(
            rule,
            listing_page.html,
        )
    except Exception as error:
        return WebsiteSourcePreview(
            source_id=rule.id,
            source_name=rule.name,
            listing_url=rule.listing_url,
            discovered_count=0,
            error=str(error),
        )

    report = WebsiteSourcePreview(
        source_id=rule.id,
        source_name=rule.name,
        listing_url=rule.listing_url,
        discovered_count=len(candidates),
        listing_fetch_provider=listing_page.provider,
    )

    for index, candidate in enumerate(candidates[:limit]):
        if index and request_delay_seconds > 0:
            time.sleep(request_delay_seconds)
        try:
            page = read_page(candidate.url)
            article = parse_article_preview(
                rule,
                candidate,
                page.html,
            )
            article.fetch_provider = page.provider
            report.items.append(article)
        except Exception as error:
            report.items.append(
                WebsiteArticlePreview(
                    source_id=rule.id,
                    source_name=rule.name,
                    organization_id=rule.organization_id,
                    url=candidate.url,
                    title=candidate.title_hint,
                    published=candidate.published_hint,
                    content_text="",
                    status="failed",
                    fetch_provider="",
                    issues=[f"fetch_failed: {error}"],
                )
            )

    if not candidates:
        report.error = "列表页没有发现符合白名单路径的文章链接"

    return report


def preview_sources(
    source_ids: Iterable[str] | None = None,
    *,
    limit: int = DEFAULT_PREVIEW_LIMIT,
    fetcher: Callable[[str], str] | None = None,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
) -> list[WebsiteSourcePreview]:
    selected_ids = list(source_ids or WEBSITE_SOURCE_RULES)
    return [
        preview_source(
            WEBSITE_SOURCE_RULES[source_id],
            limit=limit,
            fetcher=fetcher,
            request_delay_seconds=request_delay_seconds,
        )
        for source_id in selected_ids
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "只读试抓 Anthropic、Meta AI、DeepSeek 与 SpaceXAI 官方网页；"
            "不写数据库、不调用 AI。"
        )
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=tuple(WEBSITE_SOURCE_RULES),
        help="只试抓指定来源；可重复传入。默认抓取全部四家。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_PREVIEW_LIMIT,
        help="每家公司最多读取的详情页数量，默认 2，范围 1-10。",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出机器可读 JSON。",
    )
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="JSON 中包含完整正文；默认只包含 240 字预览。",
    )
    return parser


def _print_text_report(reports: list[WebsiteSourcePreview]) -> None:
    print("OrbitAI V4.2 官方网页只读试抓")
    print("边界：不写 SQLite，不调用 AI，不创建事件候选。")

    for report in reports:
        print(f"\n========== {report.source_name} ==========")
        print(f"列表：{report.listing_url}")
        if report.listing_fetch_provider:
            print(f"列表获取：{report.listing_fetch_provider}")
        print(f"发现：{report.discovered_count} 条")
        if report.error:
            print(f"状态：失败 - {report.error}")
            continue

        for item in report.items:
            print("-" * 60)
            print(f"状态：{item.status}")
            if item.fetch_provider:
                print(f"详情获取：{item.fetch_provider}")
            print(f"标题：{item.title or '未识别'}")
            print(f"日期：{item.published or '未识别'}")
            print(f"正文：{item.content_length} 字")
            print(f"链接：{item.url}")
            if item.issues:
                print(f"问题：{', '.join(item.issues)}")
            print(f"预览：{_truncate(item.content_text, 240)}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not 1 <= args.limit <= 10:
        parser.error("--limit 必须在 1 到 10 之间")

    reports = preview_sources(
        args.source,
        limit=args.limit,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "mode": "read_only_website_preview",
                    "writes_database": False,
                    "calls_ai": False,
                    "reports": [
                        report.to_dict(
                            include_content=args.include_content,
                        )
                        for report in reports
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _print_text_report(reports)

    return 0 if all(report.ok and report.ready_count for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
