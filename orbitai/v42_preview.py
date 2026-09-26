"""Create a clearly labelled, isolated local review copy; never mutate active data."""

import argparse
import os
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path


def prepare_preview(project_root):
    root = Path(project_root).resolve()
    source = root / "var" / "orbitai.db"
    folder = root / "var" / "previews" / ("v42_" + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True)
    target = folder / "preview.db"
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
    from orbitai.events.service import FIELDS, list_events, load_event, preview_event, save_event
    for index, row in enumerate(list_events(target)):
        event = load_event(row["id"], target)
        payload = {key: event[key] for key in FIELDS}
        payload.update(title="【演示】" + event["title"],
                       expected_revision=event["revision"],
                       notes="隔离副本演示，不代表真实人工核实。\n" + event["notes"],
                       status="confirmed" if index == 0 else "candidate",
                       confirmed_by_user=index == 0,
                       change_reason="隔离演示：模拟确认与候选阅读，正式库不变")
        for name, key in (("organizations", "organization_ids"), ("people", "person_ids"), ("segments", "segment_ids")):
            payload[key] = [item["id"] for item in event[name]]
        payload["materials"] = [dict(document_id=d["id"], evidence_role=d["evidence_role"], notes=d["notes"])
                                for d in event["documents"]]
        preview = preview_event(payload, target)
        save_event(preview["payload"], preview["preview_token"], target)
    return target


def main():
    parser = argparse.ArgumentParser(description="创建隔离 V4.2 演示库并启动本地试用，正式库不变")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    database = prepare_preview(root)
    print(f"隔离演示库：{database}", flush=True)
    if not args.prepare_only:
        env = dict(os.environ, ORBITAI_PREVIEW_DATABASE=str(database), PYTHONUTF8="1")
        print(f"成果总览：http://127.0.0.1:{args.port}/events/review", flush=True)
        return subprocess.call([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
                                "--port", str(args.port)], cwd=root, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
