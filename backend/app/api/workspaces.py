from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, insert, or_, select, update

from ..auth import Db, Denied, Identity, audit
from ..db import as_dict, begin_write, utc_now
from ..models import analysis_contexts, datasets, knowledge_items, knowledge_packs, metrics
from ..outputs import AnalysisContext, KnowledgePack, KnowledgePackRow, Page
from ..schemas import ContextInput, KnowledgePackInput
from .common import Limit, Offset, count, page, take

router = APIRouter(tags=["场景知识与分析上下文"])
PACK_FIELDS = [c for c in knowledge_packs.c if c.name != "seed_key"]
CONTEXT_VIEW = select(analysis_contexts, knowledge_packs.c.title.label("pack_title")).outerjoin(knowledge_packs)

def read_items(session, pack_id, metric_id=None):
    statement = select(knowledge_items.c.title, knowledge_items.c.content, knowledge_items.c.metric_id).where(
        knowledge_items.c.pack_id == pack_id)
    if metric_id is not None:
        statement = statement.where(or_(knowledge_items.c.metric_id.is_(None), knowledge_items.c.metric_id == metric_id))
    return [as_dict(row) for row in session.execute(statement.order_by(knowledge_items.c.position))]

def knowledge_snapshot(session, context, metric_id):
    pack_id = context["knowledge_pack_id"]
    if pack_id is None:
        return None
    pack = take(session, knowledge_packs, pack_id, "知识包")
    items = read_items(session, pack_id, metric_id)
    if not items:
        return None
    return {"id": pack_id, "title": pack["title"], "revision": pack["revision"], "items": items}

def pack_detail(session, pack_id):
    return {**take(session, knowledge_packs, pack_id, "知识包"), "items": read_items(session, pack_id)}

@router.get("/knowledge/packs", response_model=Page[KnowledgePackRow])
def list_packs(session: Db, actor: Identity, dataset_id: int | None = None,
               limit: Limit = 20, offset: Offset = 0):
    actor.scope("dataset.read", "knowledge_pack")
    conditions = [knowledge_packs.c.dataset_id == dataset_id] if dataset_id is not None else []
    statement = select(*PACK_FIELDS).where(*conditions).order_by(knowledge_packs.c.id)
    return page(session, statement, count(knowledge_packs, *conditions), limit, offset)

@router.get("/knowledge/packs/{pack_id}", response_model=KnowledgePack)
def get_pack(pack_id: int, session: Db, actor: Identity):
    actor.scope("dataset.read", "knowledge_pack", pack_id)
    return pack_detail(session, pack_id)

def set_items(session, pack_id, payload):
    target_ids = {item.metric_id for item in payload.items if item.metric_id is not None}
    if target_ids:
        valid = set(session.scalars(select(metrics.c.id).where(
            metrics.c.dataset_id == payload.dataset_id, metrics.c.id.in_(target_ids))))
        if valid != target_ids:
            raise HTTPException(422, "知识条目的指标必须属于知识包的数据集。")
    session.execute(delete(knowledge_items).where(knowledge_items.c.pack_id == pack_id))
    session.execute(insert(knowledge_items), [
        {"pack_id": pack_id, "position": idx, **item.model_dump()} for idx, item in enumerate(payload.items)
    ])

@router.post("/knowledge/packs", response_model=KnowledgePack, status_code=201)
def create_pack(payload: KnowledgePackInput, session: Db, actor: Identity):
    actor.scope("knowledge.manage", "knowledge_pack")
    begin_write(session)
    take(session, datasets, payload.dataset_id, "数据集")
    pack_id = session.execute(insert(knowledge_packs).values(
        **payload.model_dump(exclude={"items"}), revision=1, updated_at=utc_now()
    )).inserted_primary_key[0]
    set_items(session, pack_id, payload)
    audit(session, actor.id, "knowledge.create", "knowledge_pack", pack_id, revision=1)
    saved = pack_detail(session, pack_id)
    session.commit()
    return saved

@router.put("/knowledge/packs/{pack_id}", response_model=KnowledgePack)
def update_pack(pack_id: int, payload: KnowledgePackInput, session: Db, actor: Identity):
    actor.scope("knowledge.manage", "knowledge_pack", pack_id)
    begin_write(session)
    pack = take(session, knowledge_packs, pack_id, "知识包")
    if pack["dataset_id"] != payload.dataset_id:
        raise HTTPException(409, "已有知识包不能更换数据集。")
    revision = pack["revision"] + 1
    set_items(session, pack_id, payload)
    session.execute(update(knowledge_packs).where(knowledge_packs.c.id == pack_id).values(
        title=payload.title, description=payload.description, revision=revision, updated_at=utc_now()
    ))
    audit(session, actor.id, "knowledge.update", "knowledge_pack", pack_id, revision=revision)
    saved = pack_detail(session, pack_id)
    session.commit()
    return saved

def owned_context(session, actor, context_id, active=False):
    actor.scope("dataset.query", "analysis_context", context_id)
    row = session.execute(CONTEXT_VIEW.where(analysis_contexts.c.id == context_id)).first()
    if row is None:
        raise HTTPException(404, "分析上下文不存在。")
    if row.owner_id != actor.id:
        raise Denied(actor.id, "context.owner", "analysis_context", context_id)
    if active and row.archived:
        raise HTTPException(409, "请先恢复已归档的分析上下文。")
    return as_dict(row)

def validate_context(session, payload):
    take(session, datasets, payload.dataset_id, "数据集")
    if payload.knowledge_pack_id is not None:
        pack = take(session, knowledge_packs, payload.knowledge_pack_id, "知识包")
        if pack["dataset_id"] != payload.dataset_id:
            raise HTTPException(422, "所选知识包必须属于同一个数据集。")

@router.get("/contexts", response_model=Page[AnalysisContext])
def list_contexts(session: Db, actor: Identity, dataset_id: int | None = None, archived: bool | None = None,
                  limit: Limit = 20, offset: Offset = 0):
    actor.scope("dataset.query", "analysis_context")
    conditions = [analysis_contexts.c.owner_id == actor.id]
    if dataset_id is not None:
        conditions.append(analysis_contexts.c.dataset_id == dataset_id)
    if archived is not None:
        conditions.append(analysis_contexts.c.archived == archived)
    statement = CONTEXT_VIEW.where(*conditions).order_by(analysis_contexts.c.updated_at.desc(), analysis_contexts.c.id.desc())
    return page(session, statement, count(analysis_contexts, *conditions), limit, offset)

@router.post("/contexts", response_model=AnalysisContext, status_code=201)
def create_context(payload: ContextInput, session: Db, actor: Identity):
    actor.scope("dataset.query", "analysis_context")
    begin_write(session)
    validate_context(session, payload)
    context_id = session.execute(insert(analysis_contexts).values(
        **payload.model_dump(), owner_id=actor.id, updated_at=utc_now()
    )).inserted_primary_key[0]
    saved = owned_context(session, actor, context_id)
    session.commit()
    return saved

@router.get("/contexts/{context_id}", response_model=AnalysisContext)
def get_context(context_id: int, session: Db, actor: Identity):
    return owned_context(session, actor, context_id)

@router.put("/contexts/{context_id}", response_model=AnalysisContext)
def update_context(context_id: int, payload: ContextInput, session: Db, actor: Identity):
    begin_write(session)
    context = owned_context(session, actor, context_id)
    if payload.dataset_id != context["dataset_id"]:
        raise HTTPException(409, "已有分析上下文不能更换数据集。")
    validate_context(session, payload)
    session.execute(update(analysis_contexts).where(analysis_contexts.c.id == context_id).values(
        **payload.model_dump(exclude={"dataset_id"}), updated_at=utc_now()
    ))
    saved = owned_context(session, actor, context_id)
    session.commit()
    return saved
