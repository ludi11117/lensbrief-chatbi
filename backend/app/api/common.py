from typing import Annotated

from fastapi import HTTPException, Query
from sqlalchemy import func, select

from ..db import as_dict

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=2**63 - 1)]

def page(session, statement, count_statement, limit, offset):
    # Keep rows and count on one snapshot, including when called inside a transaction.
    with session.begin_nested():
        items = [as_dict(row) for row in session.execute(statement.limit(limit).offset(offset))]
        total = session.scalar(count_statement)
    return {"items": items, "total": total, "limit": limit, "offset": offset}

def take(session, table, item_id, label):
    row = session.execute(select(table).where(table.c.id == item_id)).first()
    if row is None:
        raise HTTPException(404, f"{label}不存在。")
    return as_dict(row)

def count(table, *conditions):
    return select(func.count()).select_from(table).where(*conditions)
