import json

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import delete, insert, select

from ..auth import Actor, Db, Identity, audit, dummy_hash, load_actor, passwords, token_for
from ..db import as_dict, begin_write
from ..models import audit_logs, departments, role_permissions, roles, user_roles, users
from ..outputs import LoginResult
from ..schemas import Login, RoleUpdate
from .common import Limit, Offset, count, page, take

router = APIRouter(tags=["身份与权限"])

@router.post("/auth/login", response_model=LoginResult)
def login(payload: Login, request: Request, session: Db):
    user = session.execute(select(users).where(users.c.username == payload.username)).first()
    valid = passwords.verify(payload.password, user.password_hash if user else dummy_hash)
    if not valid or user is None or not user.active:
        raise HTTPException(401, "用户名或密码错误。")
    actor = load_actor(session, user)
    return {"access_token": token_for(actor, request.app.state.settings), "token_type": "bearer", "user": actor}

@router.get("/auth/me", response_model=Actor)
def profile(actor: Identity):
    return actor

@router.get("/access")
def access(session: Db, actor: Identity):
    actor.scope("user.manage", "user")
    people = [as_dict(row) for row in session.execute(
        select(users.c.id, users.c.username, users.c.name, departments.c.name.label("department"))
        .join(departments).order_by(users.c.id))]
    for person in people:
        person["roles"] = list(session.scalars(select(roles.c.code).join(user_roles)
                                              .where(user_roles.c.user_id == person["id"]).order_by(roles.c.code)))
    role_list = [as_dict(row) for row in session.execute(select(roles).order_by(roles.c.id))]
    for role in role_list:
        role["grants"] = dict(session.execute(
            select(role_permissions.c.permission_code, role_permissions.c.scope)
            .where(role_permissions.c.role_id == role["id"])).all())
    return {"users": people, "roles": role_list}

@router.put("/access/users/{user_id}/roles")
def assign_roles(user_id: int, payload: RoleUpdate, session: Db, actor: Identity):
    actor.scope("user.manage", "user", user_id)
    if user_id == actor.id:
        raise HTTPException(409, "不能变更当前登录账号自己的角色。")
    begin_write(session)
    take(session, users, user_id, "账号")
    ids = session.scalars(select(roles.c.id).where(roles.c.code.in_(payload.roles))).all()
    session.execute(delete(user_roles).where(user_roles.c.user_id == user_id))
    if ids:
        session.execute(insert(user_roles), [dict(user_id=user_id, role_id=role_id) for role_id in ids])
    audit(session, actor.id, "user.roles_changed", "user", user_id, roles=sorted(set(payload.roles)))
    session.commit()
    return {"user_id": user_id, "roles": sorted(set(payload.roles))}

@router.get("/audit")
def logs(session: Db, actor: Identity, limit: Limit = 20, offset: Offset = 0):
    actor.scope("audit.read", "audit")
    statement = select(audit_logs, users.c.username).join(users).order_by(audit_logs.c.created_at.desc(),
                                                                         audit_logs.c.id.desc())
    result = page(session, statement, count(audit_logs), limit, offset)
    for item in result["items"]:
        item["detail"] = json.loads(item.pop("detail_json"))
    return result
