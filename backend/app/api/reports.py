import json
from difflib import unified_diff
from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Response
from sqlalchemy import and_, delete, func, insert, or_, select, update

from ..auth import Db, Denied, Identity, audit, scope_filter
from ..db import as_dict, begin_write, json_dump, utc_now
from ..models import assets, datasets, query_logs, report_assets, report_feedback, reports, users, version_assets, versions
from ..outputs import DiffResult, FeedbackEntry, Page, PublishResult, Report, ReportRow, ReportSummary, Version, VersionEntry
from ..schemas import FeedbackInput, ReportInput
from .common import Limit, Offset, count, page, take

router = APIRouter(prefix="/reports", tags=["报告及版本"])
METADATA = ("title", "description", "dataset_id", "query_id", "asset_ids")
QUERY_FIELDS = ("metric_name", "dimension_name", "scope", "start", "end", "channel")

def query_metadata(snapshot):
    query = snapshot.get("query") or {}
    metadata = {field: query.get(field) for field in QUERY_FIELDS}
    comparison = query.get("comparison")
    knowledge = query.get("knowledge")
    metadata["comparison_window"] = f"{comparison['start']} 至 {comparison['end']}" if comparison else None
    metadata["knowledge_pack"] = f"{knowledge['title']} v{knowledge['revision']}" if knowledge else None
    return metadata

def get_report(session, actor, report_id, action):
    actor.scope(action, "report", report_id)
    report = take(session, reports, report_id, "报告")
    if report["deleted_at"]:
        raise HTTPException(404, "报告不存在。")
    actor.require(action, "report", report)
    return report

def get_version(session, report_id, number):
    row = session.execute(select(versions).where(versions.c.report_id == report_id,
                                                  versions.c.number == number)).first()
    if row is None:
        raise HTTPException(404, "指定版本不存在。")
    return as_dict(row)

def working_snapshot(session, report):
    media = session.scalars(select(report_assets.c.asset_id)
                            .where(report_assets.c.report_id == report["id"])
                            .order_by(report_assets.c.asset_id)).all()
    query = session.scalar(select(query_logs.c.result_json).where(query_logs.c.id == report["query_id"]))
    return {**{key: report[key] for key in METADATA if key != "asset_ids"},
            "content": report["content"], "asset_ids": list(media), "query": json.loads(query) if query else None}

def media_metadata(session, ids):
    return [as_dict(row) for row in session.execute(select(assets.c.id, assets.c.filename, assets.c.mime,
                                                        assets.c.size_bytes).where(assets.c.id.in_(ids))
                                                        .order_by(assets.c.id))]

def set_media(session, report_id, ids):
    session.execute(delete(report_assets).where(report_assets.c.report_id == report_id))
    if ids:
        session.execute(insert(report_assets), [dict(report_id=report_id, asset_id=id_) for id_ in ids])

def validate_work(session, actor, payload, owner, department, existing_assets, existing_query):
    if payload.dataset_id is not None:
        actor.scope("dataset.read", "dataset", payload.dataset_id)
        take(session, datasets, payload.dataset_id, "数据集")
    if payload.query_id is not None and payload.query_id != existing_query:
        query = take(session, query_logs, payload.query_id, "查询记录")
        actor.require("query.read", "query", query, owner="user_id")
        if query["scope"] == "all" or query["department_id"] != department or (
            query["scope"] == "own" and query["user_id"] != owner
        ):
            raise Denied(actor.id, "report.attach_query", "query", payload.query_id)
        if query["dataset_id"] != payload.dataset_id or query["status"] != "ok":
            raise HTTPException(422, "仅可引用该数据集的成功查询。")
    if payload.query_id is not None and payload.query_id == existing_query:
        query = take(session, query_logs, payload.query_id, "查询记录")
        if query["dataset_id"] != payload.dataset_id:
            raise HTTPException(422, "引用查询必须属于所选数据集。")
    for asset_id in set(payload.asset_ids) - set(existing_assets):
        asset = take(session, assets, asset_id, "文件")
        if asset["owner_id"] != actor.id:
            raise Denied(actor.id, "report.attach_asset", "asset", asset_id)

def attachable_scope(report, actor, action):
    scope = actor.grants.get(action)
    return scope == "all" or (scope == "own" and report["owner_id"] == actor.id) or (
        scope == "department" and report["department_id"] == actor.department_id)

def can_edit_working_report(report, actor):
    return report["status"] != "archived" and attachable_scope(report, actor, "report.edit")

def report_tag(report, snapshot):
    state = [report["id"], report["updated_at"], report["status"], report["current_version"], snapshot]
    return '"' + sha256(json_dump(state).encode()).hexdigest() + '"'

def require_matching_report(session, report, actor, if_match, snapshot=None):
    if if_match is None or if_match.strip() == "*":
        return
    if report["current_version"] and not can_edit_working_report(report, actor):
        snapshot = json.loads(get_version(session, report["id"], report["current_version"])["snapshot_json"])
    elif snapshot is None:
        snapshot = working_snapshot(session, report)
    if report_tag(report, snapshot) not in {value.strip() for value in if_match.split(",")}:
        raise HTTPException(412, "报告已被更新。当前输入保留，请核对最新工作稿后再提交。")

def present(session, report, actor):
    number = report["current_version"]
    published = json.loads(get_version(session, report["id"], number)["snapshot_json"]) if number else None
    editable = can_edit_working_report(report, actor)
    active = working_snapshot(session, report) if editable or not published else published
    return {**{key: report[key] for key in ("id", "owner_id", "department_id", "status", "current_version",
                                            "created_at", "updated_at")},
            **active, "assets": media_metadata(session, active["asset_ids"]), "etag": report_tag(report, active),
            "has_unpublished_changes": bool(editable and published and active != published),
            "allowed": {action: attachable_scope(report, actor, f"report.{action}") for action in
                        ("edit", "delete", "publish", "rollback", "archive")}}

def listing_statements(actor, status=None, q=""):
    scope = actor.scope("report.read", "report")
    conditions = [reports.c.deleted_at.is_(None), scope_filter(reports, scope, actor)]
    if status:
        conditions.append(reports.c.status == status)

    edit_scope = actor.grants.get("report.edit")
    published_view = reports.c.status == "archived"
    if edit_scope and edit_scope != "all":
        published_view = or_(published_view, ~scope_filter(reports, edit_scope, actor))
    source = reports.outerjoin(versions, and_(
        versions.c.report_id == reports.c.id,
        versions.c.number == reports.c.current_version,
        published_view if edit_scope else True,
    ))
    title = func.coalesce(func.json_extract(versions.c.snapshot_json, "$.title"), reports.c.title)
    description = func.coalesce(func.json_extract(versions.c.snapshot_json, "$.description"), reports.c.description)
    total_source = reports
    if q.strip():
        keyword = q.strip()
        conditions.append(title.icontains(keyword, autoescape=True) | description.icontains(keyword, autoescape=True))
        total_source = source
    fields = (reports.c.id, title.label("title"), description.label("description"), reports.c.status, reports.c.owner_id,
              reports.c.current_version, reports.c.updated_at, users.c.name.label("owner_name"))
    statement = (select(*fields).select_from(source.join(users, users.c.id == reports.c.owner_id)).where(*conditions)
                 .order_by(reports.c.updated_at.desc(), reports.c.id.desc()))
    return statement, count(total_source, *conditions)

@router.get("", response_model=Page[ReportRow])
def list_reports(session: Db, actor: Identity, limit: Limit = 10, offset: Offset = 0,
                 status: Literal["draft", "published", "archived"] | None = None,
                 q: str = Query("", max_length=120)):
    statement, total = listing_statements(actor, status, q)
    return page(session, statement, total, limit, offset)

@router.get("/summary", response_model=ReportSummary)
def report_summary(session: Db, actor: Identity):
    scope = actor.scope("report.read", "report")
    groups = dict(session.execute(select(reports.c.status, func.count()).where(
        reports.c.deleted_at.is_(None), scope_filter(reports, scope, actor)
    ).group_by(reports.c.status)).all())
    return {"total": sum(groups.values()), "draft": groups.get("draft", 0),
            "published": groups.get("published", 0), "archived": groups.get("archived", 0)}

@router.post("", status_code=201, response_model=Report)
def create_report(payload: ReportInput, response: Response, session: Db, actor: Identity):
    actor.scope("report.create", "report")
    begin_write(session)
    validate_work(session, actor, payload, actor.id, actor.department_id, [], None)
    now = utc_now()
    new_id = session.execute(insert(reports).values(**payload.model_dump(exclude={"asset_ids"}),
                             owner_id=actor.id, department_id=actor.department_id, status="draft",
                             created_at=now, updated_at=now)).inserted_primary_key[0]
    set_media(session, new_id, sorted(set(payload.asset_ids)))
    audit(session, actor.id, "report.create", "report", new_id)
    session.commit()
    return report_response(response, session, take(session, reports, new_id, "报告"), actor)

@router.get("/{report_id}", response_model=Report)
def detail(report_id: int, response: Response, session: Db, actor: Identity):
    return report_response(response, session, get_report(session, actor, report_id, "report.read"), actor)

def report_response(response, session, report, actor):
    data = present(session, report, actor)
    response.headers["ETag"] = data["etag"]
    response.headers["Cache-Control"] = "private, no-store"
    return data

@router.put("/{report_id}", response_model=Report)
def edit(report_id: int, payload: ReportInput, response: Response, session: Db, actor: Identity,
         if_match: str | None = Header(None)):
    begin_write(session)
    report = get_report(session, actor, report_id, "report.edit")
    require_state(report, {"draft", "published"})
    existing = working_snapshot(session, report)
    require_matching_report(session, report, actor, if_match, existing)
    validate_work(session, actor, payload, report["owner_id"], report["department_id"],
                  existing["asset_ids"], report["query_id"])
    session.execute(update(reports).where(reports.c.id == report_id)
                    .values(**payload.model_dump(exclude={"asset_ids"}), updated_at=utc_now()))
    set_media(session, report_id, sorted(set(payload.asset_ids)))
    audit(session, actor.id, "report.edit", "report", report_id)
    session.commit()
    return report_response(response, session, take(session, reports, report_id, "报告"), actor)

@router.delete("/{report_id}", status_code=204)
def remove(report_id: int, session: Db, actor: Identity, if_match: str | None = Header(None)):
    begin_write(session)
    report = get_report(session, actor, report_id, "report.delete")
    require_matching_report(session, report, actor, if_match)
    now = utc_now()
    session.execute(update(reports).where(reports.c.id == report_id).values(deleted_at=now, updated_at=now))
    audit(session, actor.id, "report.delete", "report", report_id)
    session.commit()

def require_state(report, allowed):
    if report["status"] not in allowed:
        raise HTTPException(409, "当前报告状态不允许此操作。")

def write_version(session, actor, report, snapshot, restored_from=None):
    report_id = report["id"]
    number = (report["current_version"] or 0) + 1
    now = utc_now()
    session.execute(insert(versions).values(report_id=report_id, number=number, created_by=actor.id,
                    created_at=now, restored_from=restored_from, snapshot_json=json_dump(snapshot)))
    ids = snapshot["asset_ids"]
    if ids:
        session.execute(insert(version_assets), [dict(report_id=report_id, version=number, asset_id=id_) for id_ in ids])
    values = {key: snapshot[key] for key in ("title", "description", "content", "query_id", "dataset_id")}
    session.execute(update(reports).where(reports.c.id == report_id)
                    .values(**values, current_version=number, updated_at=now, status="published"))
    if restored_from is not None:
        set_media(session, report_id, ids)
    audit(session, actor.id, "report.rollback" if restored_from is not None else "report.publish",
          "report", report_id, version=number, restored_from=restored_from)
    session.commit()
    return {"report_id": report_id, "number": number, "status": "published", "restored_from": restored_from}

@router.post("/{report_id}/publish", status_code=201, response_model=PublishResult)
def publish(report_id: int, session: Db, actor: Identity, if_match: str | None = Header(None)):
    begin_write(session)
    report = get_report(session, actor, report_id, "report.publish")
    require_state(report, {"draft", "published"})
    snapshot = working_snapshot(session, report)
    require_matching_report(session, report, actor, if_match, snapshot)
    return write_version(session, actor, report, snapshot)

@router.post("/{report_id}/rollback/{number}", status_code=201, response_model=PublishResult)
def rollback(report_id: int, number: int, session: Db, actor: Identity, if_match: str | None = Header(None)):
    begin_write(session)
    report = get_report(session, actor, report_id, "report.rollback")
    require_state(report, {"published"})
    require_matching_report(session, report, actor, if_match)
    previous = get_version(session, report_id, number)
    return write_version(session, actor, report, json.loads(previous["snapshot_json"]), number)

@router.post("/{report_id}/archive")
def archive(report_id: int, session: Db, actor: Identity, if_match: str | None = Header(None)):
    begin_write(session)
    report = get_report(session, actor, report_id, "report.archive")
    require_state(report, {"published"})
    require_matching_report(session, report, actor, if_match)
    session.execute(update(reports).where(reports.c.id == report_id).values(status="archived", updated_at=utc_now()))
    audit(session, actor.id, "report.archive", "report", report_id)
    session.commit()
    return {"id": report_id, "status": "archived"}

@router.get("/{report_id}/versions", response_model=Page[VersionEntry])
def list_versions(report_id: int, session: Db, actor: Identity, limit: Limit = 50, offset: Offset = 0):
    get_report(session, actor, report_id, "report.read")
    condition = versions.c.report_id == report_id
    statement = select(versions.c.number, versions.c.created_at, versions.c.restored_from,
                       users.c.name.label("created_by_name")).join(users, versions.c.created_by == users.c.id)
    return page(session, statement.where(condition).order_by(versions.c.number.desc()),
                count(versions, condition), limit, offset)

@router.get("/{report_id}/versions/diff", response_model=DiffResult)
def diff(report_id: int, base: int, target: int, session: Db, actor: Identity):
    get_report(session, actor, report_id, "report.read")
    before = json.loads(get_version(session, report_id, base)["snapshot_json"])
    after = json.loads(get_version(session, report_id, target)["snapshot_json"])
    before_query, after_query = query_metadata(before), query_metadata(after)
    content_diff = list(unified_diff(before["content"].split("\n"), after["content"].split("\n"),
                                     fromfile=f"v{base}", tofile=f"v{target}", n=2, lineterm=""))
    return {"base": base, "target": target, "changes": [
        {"field": key, "before": before[key], "after": after[key]}
        for key in METADATA if before[key] != after[key]
    ], "query_changes": [
        {"field": key, "before": before_query[key], "after": after_query[key]}
        for key in before_query if before_query[key] != after_query[key]
    ], "content_changed": bool(content_diff), "content_diff": content_diff}

@router.get("/{report_id}/versions/{number}", response_model=Version)
def version_detail(report_id: int, number: int, session: Db, actor: Identity):
    get_report(session, actor, report_id, "report.read")
    selected = get_version(session, report_id, number)
    snapshot = json.loads(selected.pop("snapshot_json"))
    return {**selected, **snapshot, "assets": media_metadata(session, snapshot["asset_ids"])}

@router.get("/{report_id}/versions/{number}/feedback", response_model=Page[FeedbackEntry])
def list_feedback(report_id: int, number: int, session: Db, actor: Identity, limit: Limit = 10, offset: Offset = 0):
    get_report(session, actor, report_id, "report.read")
    get_version(session, report_id, number)
    condition = (report_feedback.c.report_id == report_id) & (report_feedback.c.version == number)
    statement = select(report_feedback.c.id, report_feedback.c.body, report_feedback.c.created_at,
                       users.c.name.label("author_name")).join(users).where(condition).order_by(report_feedback.c.id.desc())
    return page(session, statement, count(report_feedback, condition), limit, offset)

@router.post("/{report_id}/versions/{number}/feedback", response_model=FeedbackEntry, status_code=201)
def create_feedback(report_id: int, number: int, payload: FeedbackInput, session: Db, actor: Identity):
    begin_write(session)
    report = get_report(session, actor, report_id, "report.read")
    get_version(session, report_id, number)
    require_state(report, {"published"})
    when = utc_now()
    feedback_id = session.execute(insert(report_feedback).values(
        report_id=report_id, version=number, author_id=actor.id, body=payload.body, created_at=when
    )).inserted_primary_key[0]
    audit(session, actor.id, "report.feedback", "report", report_id, version=number, feedback_id=feedback_id)
    session.commit()
    return {"id": feedback_id, "body": payload.body, "created_at": when, "author_name": actor.name}
