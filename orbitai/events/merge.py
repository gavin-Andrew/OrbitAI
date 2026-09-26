"""Previewed, atomic duplicate-event merge; never deletes evidence or confirms facts."""

from copy import deepcopy

from orbitai.events.service import (
    EventConflict, RELATIONS, _connect, _hash, _json, _load, _text,
)


def _append(existing, addition):
    return (existing + "\n" + addition).strip() if existing else addition


def _snapshot(event):
    return {k: deepcopy(v) for k, v in event.items() if k not in ("history", "revision")}


def _prepare(conn, payload):
    if not isinstance(payload, dict):
        raise ValueError("合并内容必须是对象")
    normalized = {key: _text(payload, key, required=True, limit=2000)
                  for key in ("source_id", "target_id", "expected_source_revision",
                              "expected_target_revision", "change_reason")}
    if normalized["source_id"] == normalized["target_id"]:
        raise ValueError("不能将事件合并到自身")
    before = {}
    for side in ("source", "target"):
        event = _load(conn, normalized[f"{side}_id"])
        if event is None:
            raise ValueError("待合并事件不存在")
        if event["status"] == "archived":
            raise ValueError("已归档事件不能合并，请先核对事件状态")
        if event["revision"] != normalized[f"expected_{side}_revision"]:
            raise EventConflict("事件版本已变化，请重新打开并预览合并")
        # _load provides display identities; include complete relationship metadata
        # as well so roles/notes are preserved and protected by the preview token.
        event["relation_rows"] = {}
        for name, (table, field) in RELATIONS.items():
            role = "relationship_type" if name == "segments" else "role"
            event["relation_rows"][name] = [dict(row) for row in conn.execute(
                f"SELECT {field},{role},notes FROM {table} WHERE event_id=? ORDER BY {field},{role}",
                (event["id"],))]
        before[side] = event
    after = {side: _snapshot(event) for side, event in before.items()}
    source, target = after["source"], after["target"]
    target.update(status="candidate", confirmed_by_user=0)
    source.update(status="archived", confirmed_by_user=0)
    target["notes"] = _append(target["notes"], f"合并来源：{source['id']}（{source['title']}）；需重新人工确认。")
    source["notes"] = _append(source["notes"], f"已合并至：{target['id']}（{target['title']}）；原材料与历史保留。")
    for name, (_, field) in RELATIONS.items():
        role = "relationship_type" if name == "segments" else "role"
        rows = {(row[field], row[role]): deepcopy(row) for row in target["relation_rows"][name]}
        for row in source["relation_rows"][name]:
            key = row[field], row[role]
            if key not in rows:
                rows[key] = deepcopy(row)
            elif row["notes"] and row["notes"] != rows[key]["notes"]:
                rows[key]["notes"] = _append(rows[key]["notes"], f"来自 {source['id']}：{row['notes']}")
        target["relation_rows"][name] = [rows[key] for key in sorted(rows)]
        identities = {item["id"]: item for item in source[name] + target[name]}
        target[name] = [identities[key] for key in sorted(identities)]
    documents = {doc["id"]: doc for doc in target["documents"]}
    conflicts = []
    for doc in source["documents"]:
        if doc["id"] not in documents:
            documents[doc["id"]] = dict(doc, is_primary=0)
            continue
        kept = documents[doc["id"]]
        if doc["evidence_role"] != kept["evidence_role"]:
            conflicts.append(dict(document_id=doc["id"], title=doc["title"],
                source_evidence_role=doc["evidence_role"], target_evidence_role=kept["evidence_role"],
                resolution="采用目标事件的证据角色；源事件原记录保留"))
        if doc["notes"] and doc["notes"] != kept["notes"]:
            kept["notes"] = _append(kept["notes"], f"来自 {source['id']}：{doc['notes']}")
    target["documents"] = [documents[key] for key in sorted(documents)]
    return dict(payload=normalized, before=before, after=after, conflicts=conflicts)


def preview_merge(payload, database_file=None):
    with _connect(database_file) as conn:
        result = _prepare(conn, payload)
    result["preview_token"] = _hash(result)
    return result


def save_merge(payload, preview_token, database_file=None):
    with _connect(database_file, write=True) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='event_change_log'").fetchone():
                raise ValueError("事件写入需要先显式执行迁移 0007；页面不会自动迁移")
            result = _prepare(conn, payload)
            if not isinstance(preview_token, str) or _hash(result) != preview_token:
                raise EventConflict("合并内容或关联材料已变化，请重新预览")
            target = result["after"]["target"]
            for side in ("source", "target"):
                event = result["after"][side]
                conn.execute("UPDATE events SET status=?,confirmed_by_user=0,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                             (event["status"], event["notes"], event["id"]))
            for name, (table, field) in RELATIONS.items():
                role = "relationship_type" if name == "segments" else "role"
                conn.execute(f"DELETE FROM {table} WHERE event_id=?", (target["id"],))
                conn.executemany(f"INSERT INTO {table} (event_id,{field},{role},notes) VALUES (?,?,?,?)",
                    [(target["id"], row[field], row[role], row["notes"]) for row in target["relation_rows"][name]])
            conn.execute("DELETE FROM event_documents WHERE event_id=?", (target["id"],))
            conn.executemany("INSERT INTO event_documents (event_id,document_id,evidence_role,is_primary,notes) VALUES (?,?,?,?,?)",
                [(target["id"], doc["id"], doc["evidence_role"], doc["is_primary"], doc["notes"])
                 for doc in target["documents"]])
            for side in ("source", "target"):
                event = result["after"][side]
                reason = f"事件合并 {result['payload']['source_id']} → {target['id']}：{result['payload']['change_reason']}"
                conn.execute("INSERT INTO event_change_log (event_id,action,change_reason,before_json,after_json) VALUES (?,?,?,?,?)",
                    (event["id"], "update", reason, _json(_snapshot(result["before"][side])), _json(event)))
            conn.commit()
            return target["id"]
        except Exception:
            conn.rollback()
            raise
