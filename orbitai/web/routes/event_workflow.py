"""V4.2 的材料补充、草稿生成、合并与统一阅读入口。"""

import json
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from orbitai.events.service import EventConflict, load_event, load_options, list_events
from orbitai.events.merge import preview_merge, save_merge
from orbitai.events.extraction import extract_candidate
from orbitai.materials.intake import (
    DocumentConflict, list_documents, preview_document, save_document, fetch_website_document,
)
from orbitai.web.routes.events import render, read_form

router = APIRouter()


def failed(request, error):
    return render(request, "event_error", "本次操作未完成", error=str(error),
                  status_code=409 if isinstance(error, (EventConflict, DocumentConflict)) else 422)


@router.get("/events/review")
def v42_review(request: Request):
    events = list_events()
    counts = {state: sum(e["status"] == state for e in events)
              for state in ("candidate", "needs_evidence", "confirmed", "disputed", "archived")}
    return render(request, "v42_review", "V4.2 · 从消息到产业动态", counts=counts,
                  events=[e for e in events if e["status"] not in ("confirmed", "archived")])


@router.get("/events/materials")
def document_intake(request: Request, saved: str = ""):
    return render(request, "document_intake", "补充原始材料", options=load_options(),
                  documents=list_documents(), saved=saved)


@router.post("/events/materials/preview")
async def document_preview(request: Request):
    try:
        form = await read_form(request)
        payload = {key: form.get(key, [""])[0] for key in
                   ("source_id", "title", "url", "published_at", "content_text")}
        payload["document_type"] = "manual_excerpt"
        return document_preview_response(request, preview_document(payload))
    except ValueError as error:
        return failed(request, error)


def document_preview_response(request, preview):
    return render(request, "document_preview", "核对原始材料", preview=preview,
                  payload_json=json.dumps(preview["payload"], ensure_ascii=False))


@router.post("/events/materials/fetch")
async def document_fetch(request: Request):
    try:
        form = await read_form(request)
        payload = await run_in_threadpool(fetch_website_document,
            form.get("source_id", [""])[0], form.get("url", [""])[0])
        return document_preview_response(request, preview_document(payload))
    except ValueError as error:
        return failed(request, error)


@router.post("/events/materials/save")
async def document_save(request: Request):
    try:
        form = await read_form(request)
        payload = json.loads(form.get("payload", [""])[0])
        document_id = save_document(payload, form.get("preview_token", [""])[0])
        return RedirectResponse("/events/materials?saved=" + quote(document_id, safe=""), status_code=303)
    except ValueError as error:
        return failed(request, error)


@router.get("/events/extract")
def event_extract_form(request: Request):
    return render(request, "event_extract", "从 RSS 拟事件草稿", options=load_options())


@router.post("/events/extract")
async def event_extract(request: Request):
    try:
        form = await read_form(request)
        result = await run_in_threadpool(extract_candidate, [int(i) for i in form.get("article_ids", [])])
        return render(request, "event_extraction_result", "核对事件草稿", result=result,
                      event=result["event"] or {}, options=load_options())
    except ValueError as error:
        return failed(request, error)


@router.get("/events/{event_id}/merge")
def event_merge_form(request: Request, event_id: str):
    source = load_event(event_id)
    if source is None:
        raise HTTPException(404, "未找到事件")
    targets = [e for e in list_events() if e["id"] != event_id and e["status"] != "archived"]
    return render(request, "event_merge", "整理重复事件", source=source, targets=targets)


@router.post("/events/merge/preview")
async def event_merge_preview(request: Request):
    try:
        form = await read_form(request)
        payload = {key: form.get(key, [""])[0] for key in
                   ("source_id", "target_id", "expected_source_revision", "change_reason")}
        target = load_event(payload["target_id"])
        if target is None:
            raise ValueError("目标事件不存在")
        payload["expected_target_revision"] = target["revision"]
        preview = preview_merge(payload)
        return render(request, "event_merge_preview", "核对事件合并", preview=preview,
                      payload_json=json.dumps(preview["payload"], ensure_ascii=False))
    except ValueError as error:
        return failed(request, error)


@router.post("/events/merge/save")
async def event_merge_save(request: Request):
    try:
        form = await read_form(request)
        event_id = save_merge(json.loads(form.get("payload", [""])[0]), form.get("preview_token", [""])[0])
        return RedirectResponse("/events/" + quote(event_id, safe=""), status_code=303)
    except ValueError as error:
        return failed(request, error)
