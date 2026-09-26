"""事件仓储与事务服务；消费原始材料快照，不使用 AI 摘要作证据。"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from orbitai.core.config import DATABASE_FILE


class EventConflict(ValueError):
    """预览后事件、材料或名册变化，需重新预览。"""


STATUSES = {"candidate", "confirmed", "disputed", "needs_evidence", "archived"}
ROLES = {"official", "independent", "expert", "user_feedback", "background"}
RELATIONS = {
    "organizations": ("event_organizations", "organization_id"),
    "segments": ("event_segments", "segment_id"),
    "people": ("event_people", "person_id"),
}
FIELDS = ("id", "title", "summary", "event_type_id", "status", "date_start",
          "date_end", "date_precision", "origin", "confirmed_by_user", "notes")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


@contextmanager
def _connect(database_file=None, *, write=False):
    path = Path(database_file or DATABASE_FILE).resolve()
    # mode=rw never creates a missing database; reading never migrates or writes.
    conn = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def _load(conn, event_id):
    row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    for name, (table, field) in RELATIONS.items():
        result[name] = [dict(r) for r in conn.execute(
            f"SELECT p.id,p.name FROM {table} r JOIN {name} p ON p.id=r.{field} "
            "WHERE r.event_id=? ORDER BY p.id", (event_id,))]
    result["documents"] = [dict(r) for r in conn.execute(
        "SELECT d.*,r.evidence_role,r.is_primary,r.notes FROM documents d "
        "JOIN event_documents r ON r.document_id=d.id WHERE r.event_id=? ORDER BY d.id",
        (event_id,))]
    has_log = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='event_change_log'"
    ).fetchone()
    result["history"] = ([dict(r) for r in conn.execute(
        "SELECT * FROM event_change_log WHERE event_id=? ORDER BY id DESC", (event_id,))]
        if has_log else [])
    result["revision"] = _hash(result)
    return result


def load_event(event_id, database_file=None):
    with _connect(database_file) as conn:
        return _load(conn, event_id)


def list_events(database_file=None, *, status=None, segment_id=None,
                organization_id=None, person_id=None):
    where, args = [], []
    if status is not None:
        if status not in STATUSES:
            raise ValueError("未知事件状态")
        where.append("e.status=?")
        args.append(status)
        if status == "confirmed":
            where.append("e.confirmed_by_user=1")
    for value, table, field in (
        (segment_id, "event_segments", "segment_id"),
        (organization_id, "event_organizations", "organization_id"),
        (person_id, "event_people", "person_id"),
    ):
        if value:
            where.append(f"EXISTS (SELECT 1 FROM {table} r WHERE r.event_id=e.id AND r.{field}=?)")
            args.append(value)
    sql = "SELECT e.* FROM events e" + (" WHERE " + " AND ".join(where) if where else "")
    # Unknown dates have a separate tail; no fake date is introduced for sorting.
    sql += " ORDER BY e.date_start IS NULL,e.date_start,e.id"
    with _connect(database_file) as conn:
        return [dict(row) for row in conn.execute(sql, args)]


def load_options(database_file=None):
    with _connect(database_file) as conn:
        result = {name: [dict(r) for r in conn.execute(f"SELECT id,name FROM {name} ORDER BY name")]
                  for name in (*RELATIONS, "event_types", "sources")}
        result["articles"] = [dict(r) for r in conn.execute(
            "SELECT id,title,source,published,summary_original FROM articles ORDER BY id DESC")]
        result["documents"] = [dict(r) for r in conn.execute(
            "SELECT * FROM documents WHERE article_id IS NULL ORDER BY created_at DESC,id")]
        return result


def _text(payload, key, *, required=False, limit=12000):
    value = payload.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{key} 必须是文本")
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise ValueError(f"{key} 不能为空或超长")
    return value


def _check_dates(start, end, precision):
    if precision == "unknown":
        if start or end:
            raise ValueError("未知日期不得填入推测日期")
        return
    patterns = {"day": r"\d{4}-\d{2}-\d{2}", "month": r"\d{4}-\d{2}",
                "quarter": r"\d{4}-Q[1-4]", "year": r"\d{4}", "range": r"\d{4}-\d{2}-\d{2}"}
    if precision not in patterns or not re.fullmatch(patterns[precision], start):
        raise ValueError("日期必须与精度匹配：日 YYYY-MM-DD、月 YYYY-MM、季度 YYYY-Q1、年 YYYY")
    try:
        if precision in ("day", "range"):
            date.fromisoformat(start)
        elif precision == "month":
            date.fromisoformat(start + "-01")
        else:
            date(int(start[:4]), 1, 1)
        if precision == "range":
            date.fromisoformat(end)
            if end < start:
                raise ValueError()
        elif end:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("日期无效；只有 range 精度可填写结束日期") from None


def _safe_url(value):
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("来源必须有可追溯的 HTTP(S) 原始链接")
    return value


def _prepare(conn, payload):
    if not isinstance(payload, dict):
        raise ValueError("事件内容必须是对象")
    p = dict(payload)
    event_id = _text(p, "id", limit=100) or "event_" + uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]+", event_id):
        raise ValueError("事件 ID 格式无效")
    before = _load(conn, event_id)
    revision = _text(p, "expected_revision")
    if (before and before["revision"] != revision) or (not before and revision):
        raise EventConflict("事件版本已变化，请重新打开并预览")
    after = {key: _text(p, key, required=key in ("title", "event_type_id"))
             for key in ("title", "summary", "event_type_id", "notes")}
    after["id"] = event_id
    after["status"] = _text(p, "status") or "candidate"
    if after["status"] not in STATUSES:
        raise ValueError("未知事件状态")
    if not conn.execute("SELECT 1 FROM event_types WHERE id=?", (after["event_type_id"],)).fetchone():
        raise ValueError("未知事件类型")
    after["date_precision"] = _text(p, "date_precision") or "unknown"
    start, end = _text(p, "date_start"), _text(p, "date_end")
    _check_dates(start, end, after["date_precision"])
    after.update(date_start=start or None, date_end=end or None)
    confirmation = p.get("confirmed_by_user", False)
    if not isinstance(confirmation, bool):
        raise ValueError("人工确认必须是布尔值")
    if after["status"] == "confirmed" and not confirmation:
        raise ValueError("确认事件需要人工核对并明确勾选确认")
    after["confirmed_by_user"] = int(after["status"] == "confirmed" and confirmation)
    after["origin"] = before["origin"] if before else (_text(p, "origin") or "user")
    if after["origin"] not in ("user", "ai", "import"):
        raise ValueError("未知事件创建来源")
    for name in RELATIONS:
        key = {"organizations": "organization_ids", "segments": "segment_ids", "people": "person_ids"}[name]
        ids = p.get(key, [])
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            raise ValueError(f"{key} 必须是 ID 列表")
        after[name] = []
        for item in sorted(set(ids)):
            row = conn.execute(f"SELECT id,name FROM {name} WHERE id=?", (item,)).fetchone()
            if row is None:
                raise ValueError(f"未知{name}：{item}")
            after[name].append(dict(row))
    if not after["segments"] or not (after["organizations"] or after["people"]):
        raise ValueError("事件至少关联一个赛道及一个组织或人物")
    materials = p.get("materials", [])
    if not isinstance(materials, list) or not materials:
        raise ValueError("每个事件至少关联一篇原始材料；可先补充材料再创建事件")
    documents, seen = [], set()
    if any(not isinstance(m, dict) for m in materials):
        raise ValueError("材料必须是对象")
    for material in materials:
        if "document_id" in material:
            if "article_id" in material:
                raise ValueError("每条材料只能指定一种身份")
            document_id = _text(material, "document_id", required=True, limit=100)
            old = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if old is None:
                raise ValueError("找不到已保存的原始材料")
            doc = dict(old)
            if doc["origin"] == "ai":
                raise ValueError("AI 生成文档不能充当原文证据")
            if material.get("source_id") and material["source_id"] != doc["source_id"]:
                raise ValueError("已保存文档的来源身份不得通过事件编辑改写")
            _safe_url(doc["url"] or "")
            if not doc["title"] or not (doc["content_text"] or "").strip():
                raise ValueError("材料缺少原文标题或原文内容")
            role = material.get("evidence_role", "background")
            if role not in ROLES:
                raise ValueError("未知证据角色")
            doc.update(evidence_role=role, notes=_text(material, "notes"))
            documents.append(doc)
            continue
        if type(material.get("article_id")) is not int:
            raise ValueError("材料 article_id 必须是整数")
        aid = material["article_id"]
        article = conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
        if article is None:
            raise ValueError(f"材料 #{aid} 不存在")
        old = conn.execute("SELECT * FROM documents WHERE article_id=?", (aid,)).fetchone()
        source_id = material.get("source_id") or None
        if source_id and not conn.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone():
            raise ValueError("来源身份不存在")
        role = material.get("evidence_role", "background")
        if role not in ROLES:
            raise ValueError("未知证据角色")
        if old:
            doc = dict(old)
            if doc["origin"] == "ai":
                raise ValueError("AI 生成文档不能充当本切片的 RSS 原文证据")
            if source_id is not None and source_id != doc["source_id"]:
                raise ValueError("已保存文档的来源身份不得通过事件编辑改写")
        else:
            if conn.execute("SELECT 1 FROM documents WHERE id=? OR url=?",
                            (f"article_{aid}", article["link"])).fetchone():
                raise ValueError(f"材料 #{aid} 的文档 ID 或 URL 已被其他文档占用，请先核对映射")
            doc = dict(id=f"article_{aid}", article_id=aid, source_id=source_id,
                       title=article["title"] or "", url=article["link"] or "",
                       published_at=article["published"], content_text=article["summary_original"] or "",
                       document_type="rss_excerpt", origin="import")
        _safe_url(doc["url"] or "")
        if not doc["title"] or not (doc["content_text"] or "").strip():
            raise ValueError(f"材料 #{aid} 缺少原文标题或原文摘录，不能用 AI 摘要补齐")
        doc.update(evidence_role=role, notes=_text(material, "notes"))
        documents.append(doc)
    after["documents"] = sorted(documents, key=lambda d: d["id"])
    for index, doc in enumerate(after["documents"]):
        if doc["id"] in seen:
            raise ValueError("同一事件不能重复关联同一材料")
        seen.add(doc["id"])
        doc["is_primary"] = int(index == 0)
    reason = _text(p, "change_reason", required=True, limit=2000)
    normalized = {k: after[k] for k in FIELDS}
    normalized["confirmed_by_user"] = bool(after["confirmed_by_user"])
    normalized.update(expected_revision=revision, change_reason=reason)
    for name, key in (("organizations", "organization_ids"), ("segments", "segment_ids"), ("people", "person_ids")):
        normalized[key] = [i["id"] for i in after[name]]
    normalized["materials"] = [dict(**({"article_id": d["article_id"]} if d["article_id"] is not None
                                       else {"document_id": d["id"]}), source_id=d["source_id"],
                                    evidence_role=d["evidence_role"], notes=d["notes"])
                               for d in after["documents"]]
    return {"payload": normalized, "before": before, "after": after, "revision": revision}


def preview_event(payload, database_file=None):
    with _connect(database_file) as conn:
        result = _prepare(conn, payload)
    result["preview_token"] = _hash(result)
    return result


def save_event(payload, preview_token, database_file=None):
    with _connect(database_file, write=True) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='event_change_log'").fetchone():
                raise ValueError("事件写入需要先显式执行迁移 0007；页面不会自动迁移")
            result = _prepare(conn, payload)
            if not isinstance(preview_token, str) or _hash(result) != preview_token:
                raise EventConflict("预览内容或来源材料已变化，请重新预览")
            after, before = result["after"], result["before"]
            event_id = after["id"]
            if before:
                keys = FIELDS[1:]
                conn.execute("UPDATE events SET " + ",".join(f"{k}=?" for k in keys) +
                             ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                             [after[k] for k in keys] + [event_id])
            else:
                conn.execute("INSERT INTO events (" + ",".join(FIELDS) + ") VALUES (" +
                             ",".join("?" for _ in FIELDS) + ")", [after[k] for k in FIELDS])
            for name, (table, field) in RELATIONS.items():
                conn.execute(f"DELETE FROM {table} WHERE event_id=?", (event_id,))
                conn.executemany(f"INSERT INTO {table} (event_id,{field}) VALUES (?,?)",
                                 [(event_id, item["id"]) for item in after[name]])
            conn.execute("DELETE FROM event_documents WHERE event_id=?", (event_id,))
            for doc in after["documents"]:
                existing = conn.execute("SELECT * FROM documents WHERE id=?", (doc["id"],)).fetchone()
                if existing and any(existing[k] != doc[k] for k in
                                    ("article_id", "source_id", "title", "url", "content_text", "document_type", "origin", "published_at")):
                    raise EventConflict("文档身份或原文快照发生变化，请重新核对")
                if not existing:
                    keys = ("id", "article_id", "source_id", "title", "url", "published_at", "content_text", "document_type", "origin")
                    conn.execute("INSERT INTO documents (" + ",".join(keys) + ") VALUES (" +
                                 ",".join("?" for _ in keys) + ")", [doc[k] for k in keys])
                conn.execute("INSERT INTO event_documents (event_id,document_id,evidence_role,is_primary,notes) VALUES (?,?,?,?,?)",
                             (event_id, doc["id"], doc["evidence_role"], doc["is_primary"], doc["notes"]))
            # Store snapshots without recursively embedding past history.
            prior = {k: v for k, v in (before or {}).items() if k not in ("history", "revision")}
            conn.execute("INSERT INTO event_change_log (event_id,action,change_reason,before_json,after_json) VALUES (?,?,?,?,?)",
                         (event_id, "create" if before is None else "update",
                          result["payload"]["change_reason"], _json(prior), _json(after)))
            conn.commit()
            return event_id
        except Exception:
            conn.rollback()
            raise
