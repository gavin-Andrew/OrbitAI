"""Explicit, previewed intake of original excerpts and validated website text.

This module never migrates a database, creates events, or invokes AI. Website
fetching is an explicit operation separate from database preview and save.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import ssl
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

import certifi

from orbitai.core.config import DATABASE_FILE
from orbitai.materials import web_sources


class DocumentConflict(ValueError):
    """The source or document changed after preview, or a URL already exists."""


_FETCH_SECRET = secrets.token_bytes(32)
_FIELDS = ("source_id", "title", "url", "published_at", "content_text", "document_type")


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _fetch_signature(payload):
    return hmac.new(_FETCH_SECRET, _digest({key: payload[key] for key in _FIELDS}).encode(),
                    hashlib.sha256).hexdigest()


@contextmanager
def _connect(database_file=None, *, write=False):
    path = Path(database_file or DATABASE_FILE).resolve()
    conn = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def _text(payload, key, *, required=False, limit=500):
    value = payload.get(key, "") or ""
    if not isinstance(value, str):
        raise ValueError(f"{key} 必须为文本")
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise ValueError(f"{key} 不能为空或超过长度上限")
    return value


def _url(value, *, official=False):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ({"https"} if official else {"http", "https"})
                or not parsed.hostname or parsed.username or parsed.password
                or any(c.isspace() or ord(c) < 32 for c in value)):
            raise ValueError()
        port = parsed.port
        if official and port not in (None, 443):
            raise ValueError()
    except ValueError:
        raise ValueError("原始 URL 必须为有效的 HTTP(S) 地址，不能包含账号或异常端口") from None
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if port and not ((parsed.scheme == "https" and port == 443)
                     or (parsed.scheme == "http" and port == 80)):
        host += f":{port}"
    # Website rules discard query strings; manual URLs preserve meaningful query IDs.
    return urlunsplit((parsed.scheme, host, parsed.path or "/",
                       "" if official else parsed.query, ""))


def _normalize(payload):
    if not isinstance(payload, dict):
        raise ValueError("材料必须为对象")
    kind = _text(payload, "document_type") or "manual_excerpt"
    if kind not in {"manual_excerpt", "web_article"}:
        raise ValueError("只支持人工原始摘录或校验通过的官网正文")
    result = {
        "source_id": _text(payload, "source_id", required=True, limit=200),
        "title": _text(payload, "title", required=True, limit=1000),
        "url": _url(_text(payload, "url", required=True, limit=4000), official=kind == "web_article"),
        # Preserve the publication date exactly as provided; unknown stays empty.
        "published_at": _text(payload, "published_at", limit=120),
        "content_text": _text(payload, "content_text", required=True, limit=500000),
        "document_type": kind,
    }
    if kind == "web_article":
        token = _text(payload, "fetch_token", required=True, limit=100)
        if not hmac.compare_digest(token, _fetch_signature(result)):
            raise ValueError("官网正文已修改或抓取凭证失效，请重新读取，或改用人工原始摘录")
        result["fetch_token"] = token
    return result


def _document_url_identity(value):
    canonical = _url(value)
    if any(rule.accepts_article_url(canonical)
           for rule in web_sources.WEBSITE_SOURCE_RULES.values()):
        return _url(canonical, official=True)
    return canonical


def _preview(conn, payload):
    normalized = _normalize(payload)
    source = conn.execute("SELECT * FROM sources WHERE id=?", (normalized["source_id"],)).fetchone()
    if source is None or source["tier"] == "archived":
        raise ValueError("来源不存在或已归档，请先选用有效来源")
    # Compare normalized identities as older RSS snapshots may have fragments.
    identity = _document_url_identity(normalized["url"])
    for existing in conn.execute("SELECT id,url FROM documents WHERE url IS NOT NULL"):
        try:
            existing_url = _document_url_identity(existing["url"])
        except ValueError:
            existing_url = existing["url"]
        if existing_url == identity:
            raise DocumentConflict(f"该 URL 已有材料 {existing['id']}，请复用已有材料；不会覆盖原文")
    after = {key: normalized[key] for key in _FIELDS}
    after["origin"] = "import" if after["document_type"] == "web_article" else "user"
    warnings = ["保存材料不会创建事件，也不代表事实已确认。"]
    if after["document_type"] == "manual_excerpt":
        warnings.append("人工原始摘录不是全文；请粘贴来源原文，不使用 AI 摘要替代。")
    if not after["published_at"]:
        warnings.append("发布日期未知，保留为空。")
    return {"payload": normalized, "after": after, "source": dict(source),
            "warnings": warnings, "preview_token": _digest({"after": after, "source": dict(source)})}


def list_documents(database_file=None):
    with _connect(database_file) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT d.*,s.name AS source_name FROM documents d LEFT JOIN sources s ON s.id=d.source_id "
            "ORDER BY d.created_at DESC,d.id")]


def preview_document(payload, database_file=None):
    with _connect(database_file) as conn:
        return _preview(conn, payload)


def save_document(payload, preview_token, database_file=None):
    if not isinstance(preview_token, str) or not preview_token:
        raise DocumentConflict("请先预览材料")
    with _connect(database_file, write=True) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            preview = _preview(conn, payload)
            if not hmac.compare_digest(preview_token, preview["preview_token"]):
                raise DocumentConflict("材料或来源在预览后变化，请重新预览")
            document_id = "document_" + uuid.uuid4().hex
            after = preview["after"]
            conn.execute(
                "INSERT INTO documents (id,source_id,title,url,published_at,content_text,document_type,origin) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (document_id, after["source_id"], after["title"], after["url"],
                 after["published_at"] or None, after["content_text"], after["document_type"], after["origin"]))
            conn.commit()
            return document_id
        except Exception:
            conn.rollback()
            raise


def _read_official(rule, url):
    """Only follow redirects inside the same source's allowed article boundary."""
    class OfficialRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            target = _url(newurl, official=True)
            if not rule.accepts_article_url(target):
                raise ValueError("官网重定向超出允许的文章范围，请人工补充原文")
            return super().redirect_request(req, fp, code, msg, headers, target)

    opener = build_opener(HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())),
                          OfficialRedirect())
    request = Request(url, headers={"User-Agent": "OrbitAI/4.2 (official material intake)",
                                    "Accept": "text/html,application/xhtml+xml"})
    with opener.open(request, timeout=20) as response:
        final_url = _url(response.geturl(), official=True)
        if not rule.accepts_article_url(final_url):
            raise ValueError("返回地址不属于官网文章白名单")
        if response.headers.get_content_type() not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("官网未返回 HTML 正文")
        raw = response.read(web_sources.MAX_RESPONSE_BYTES + 1)
        if len(raw) > web_sources.MAX_RESPONSE_BYTES:
            raise ValueError("官网正文超过 5 MiB 上限")
        return final_url, raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def fetch_website_document(source_id, url):
    """Explicitly fetch one approved article; no database, AI or paid fallback."""
    if source_id not in {"anthropic", "meta_ai", "deepseek"}:
        raise ValueError("正式直连仅支持 Anthropic、Meta AI、DeepSeek；其他来源请人工补充原始摘录")
    rule = web_sources.WEBSITE_SOURCE_RULES[source_id]
    target = _url(url, official=True)
    if not rule.accepts_article_url(target):
        raise ValueError("URL 不在该来源的官网文章白名单内")
    try:
        final_url, html = _read_official(rule, target)
        article = web_sources.parse_article_preview(rule, web_sources.DiscoveredArticle(final_url), html)
    except Exception as exc:
        raise ValueError(f"官网读取失败，请人工补充原始摘录：{exc}") from exc
    if article.status != "ready":
        raise ValueError("官网正文未通过质量检查：" + ", ".join(article.issues) + "；请人工补充原始摘录")
    payload = {"source_id": source_id, "title": article.title.strip(), "url": final_url,
               "published_at": article.published.strip(), "content_text": article.content_text.strip(),
               "document_type": "web_article"}
    payload["fetch_token"] = _fetch_signature(payload)
    return payload
