import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import URL, create_engine, event, text

ROOT = Path(__file__).resolve().parents[2]

def sqlite_engine(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(path)), connect_args={"timeout": 10})

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine

def begin_write(session):
    # Serialize the read/modify/write sequence before reading the current version.
    session.execute(text("BEGIN IMMEDIATE"))

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")

def json_dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

def as_dict(row):
    return dict(row._mapping)
