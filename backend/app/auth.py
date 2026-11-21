from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from .db import json_dump, utc_now
from .models import audit_logs, role_permissions, roles, user_roles, users

ACTIONS = (
    "report.read", "report.create", "report.edit", "report.delete", "report.publish",
    "report.rollback", "report.archive", "asset.upload", "dataset.read", "dataset.query",
    "query.read", "user.manage", "audit.read", "knowledge.manage",
)
SCOPE_RANK = {"own": 0, "department": 1, "all": 2}
passwords = PasswordHash.recommended()
dummy_hash = passwords.hash("lensbrief-placeholder-for-missing-user")
bearer = HTTPBearer(auto_error=False)

class Denied(Exception):
    def __init__(self, actor_id, action, resource, resource_id=None):
        self.actor_id = actor_id
        self.action = action
        self.resource = resource
        self.resource_id = resource_id

@dataclass(frozen=True)
class Actor:
    id: int
    username: str
    name: str
    department_id: int
    roles: list[str]
    grants: dict[str, str]

    def scope(self, action, resource, resource_id=None):
        if action not in self.grants:
            raise Denied(self.id, action, resource, resource_id)
        return self.grants[action]

    def require(self, action, resource, item, owner="owner_id"):
        scope = self.scope(action, resource, item["id"])
        if scope == "all" or (scope == "own" and item[owner] == self.id):
            return
        if scope == "department" and item["department_id"] == self.department_id:
            return
        raise Denied(self.id, action, resource, item["id"])

def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session

Db = Annotated[Session, Depends(get_session)]

def load_actor(session, row):
    assigned = session.execute(select(roles.c.code, roles.c.id).join(user_roles)
                               .where(user_roles.c.user_id == row.id).order_by(roles.c.code)).all()
    grants = {}
    for code, scope in session.execute(select(role_permissions.c.permission_code, role_permissions.c.scope)
                                       .where(role_permissions.c.role_id.in_([role.id for role in assigned]))):
        if code not in grants or SCOPE_RANK[scope] > SCOPE_RANK[grants[code]]:
            grants[code] = scope
    return Actor(row.id, row.username, row.name, row.department_id, [role.code for role in assigned], grants)

def token_for(actor, settings):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(actor.id), "iss": "lensbrief", "iat": now,
                       "exp": now + timedelta(hours=8)}, settings.jwt_secret, algorithm="HS256")

def current_actor(request: Request, session: Db,
                  credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    unauthorized = HTTPException(401, "请先登录或重新登录。", headers={"WWW-Authenticate": "Bearer"})
    if not credentials:
        raise unauthorized
    try:
        claims = jwt.decode(credentials.credentials, request.app.state.settings.jwt_secret,
                            algorithms=["HS256"], issuer="lensbrief", options={"require": ["exp", "iat", "sub"]})
        actor_id = int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized from None
    user = session.execute(select(users).where(users.c.id == actor_id, users.c.active.is_(True))).first()
    if user is None:
        raise unauthorized
    return load_actor(session, user)

Identity = Annotated[Actor, Depends(current_actor)]

def scope_filter(table, scope, actor, owner="owner_id"):
    if scope == "own":
        return table.c[owner] == actor.id
    if scope == "department":
        return table.c.department_id == actor.department_id
    return True

def audit(session, actor_id, action, resource, resource_id=None, **detail):
    session.execute(insert(audit_logs).values(user_id=actor_id, action=action, resource=resource,
                    resource_id=resource_id, detail_json=json_dump(detail), created_at=utc_now()))
