"""人工审核的事件台账、预览保存与只展示已确认事件的时间线。"""

import json
from urllib.parse import parse_qs, quote, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from orbitai.events.service import (
    EventConflict, list_events, load_event, load_options, preview_event, save_event,
)
from orbitai.web.templating import templates

router = APIRouter()
STATUS_LABELS = {"candidate": "候选", "confirmed": "已确认", "disputed": "有争议", "needs_evidence": "待补证", "archived": "已归档"}


def render(request, name, title, *, status_code=200, **context):
    return templates.TemplateResponse(request=request, name=f"dossier/{name}.html", context={
        "request": request, "page_title": title,
        "page_subtitle": "保留来源与不确定性 · 人工预览、确认与纠错",
        "active_page": "industry_structure", "status_labels": STATUS_LABELS, **context,
    }, status_code=status_code)


def filters(segment_id=None, organization_id=None, person_id=None):
    return {"segment_id": segment_id or None, "organization_id": organization_id or None, "person_id": person_id or None}


@router.get("/events")
def event_ledger(request: Request, status: str = "", segment_id: str = "", organization_id: str = "", person_id: str = ""):
    if status and status not in STATUS_LABELS:
        raise HTTPException(422, "未知事件状态")
    selected = filters(segment_id, organization_id, person_id)
    return render(request, "event_ledger", "事件台账", events=list_events(status=status or None, **selected), options=load_options(), selected=selected, selected_status=status)


@router.get("/timeline")
def event_timeline(request: Request, segment_id: str = "", organization_id: str = "", person_id: str = ""):
    selected = filters(segment_id, organization_id, person_id)
    return render(request, "timeline", "已确认事件时间线", events=list_events(status="confirmed", **selected), options=load_options(), selected=selected)


@router.get("/events/new")
def event_new(request: Request, document_id: str = "", article_id: int | None = None):
    options = load_options()
    selected = [d for d in options.get("documents", []) if d["id"] == document_id]
    if article_id is not None:
        selected += [{"article_id": a["id"]} for a in options["articles"] if a["id"] == article_id]
    return render(request, "event_form", "创建事件候选", event={"documents": selected}, options=options)


async def read_form(request):
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise ValueError("拒绝跨站提交，请从本地事件页面操作")
    expected = urlsplit(str(request.base_url))
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if value:
            actual = urlsplit(value)
            if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
                raise ValueError("提交来源与本地应用不一致")
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/x-www-form-urlencoded":
        raise ValueError("只接受事件页面的表单提交")
    body = await request.body()
    if len(body) > 1_000_000:
        raise ValueError("提交内容过大")
    return parse_qs(body.decode("utf-8"), keep_blank_values=True)


def form_payload(form):
    payload = {key: form.get(key, [""])[0] for key in (
        "id", "expected_revision", "title", "summary", "event_type_id", "status",
        "date_start", "date_end", "date_precision", "notes", "change_reason", "origin",
    )}
    for key in ("organization_ids", "segment_ids", "person_ids"):
        payload[key] = form.get(key, [])
    payload["confirmed_by_user"] = form.get("confirmed_by_user") == ["yes"]
    payload["materials"] = [{"article_id": int(value), "source_id": form.get(f"source_{value}", [""])[0] or None, "evidence_role": form.get(f"role_{value}", ["background"])[0], "notes": form.get(f"material_notes_{value}", [""])[0]} for value in form.get("article_ids", [])]
    payload["materials"] += [{"document_id": value, "evidence_role": form.get(f"doc_role_{value}", ["background"])[0], "notes": form.get(f"doc_notes_{value}", [""])[0]} for value in form.get("document_ids", [])]
    return payload


@router.post("/events/preview")
async def event_preview(request: Request):
    try:
        preview = preview_event(form_payload(await read_form(request)))
        before = preview["before"]
        before_clean = {key: value for key, value in before.items() if key not in ("history", "revision")} if before else None
        return render(request, "event_preview", "审核事件变更预览", preview=preview,
                      before_json=json.dumps(before_clean, ensure_ascii=False, indent=2),
                      after_json=json.dumps(preview["after"], ensure_ascii=False, indent=2),
                      payload_json=json.dumps(preview["payload"], ensure_ascii=False))
    except (ValueError, EventConflict) as error:
        return render(request, "event_error", "事件预览未通过", status_code=409 if isinstance(error, EventConflict) else 422, error=str(error))


@router.post("/events/save")
async def event_save(request: Request):
    try:
        form = await read_form(request)
        payload = json.loads(form.get("payload", [""])[0])
        if not isinstance(payload, dict):
            raise ValueError("事件内容必须为对象")
        event_id = save_event(payload, form.get("preview_token", [""])[0])
        return RedirectResponse(f"/events/{quote(str(event_id), safe='')}", status_code=303)
    except (ValueError, EventConflict) as error:
        return render(request, "event_error", "事件未保存", status_code=409 if isinstance(error, EventConflict) else 422, error=str(error))


@router.get("/events/{event_id}/edit")
def event_edit(request: Request, event_id: str):
    event = load_event(event_id)
    if event is None:
        raise HTTPException(404, "未找到事件")
    return render(request, "event_form", "编辑／纠错事件", event=event, options=load_options())


@router.get("/events/{event_id}")
def event_detail(request: Request, event_id: str):
    event = load_event(event_id)
    if event is None:
        raise HTTPException(404, "未找到事件")
    return render(request, "event_detail", event["title"], event=event)
