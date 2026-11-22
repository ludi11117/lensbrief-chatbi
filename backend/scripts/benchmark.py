import argparse
import csv
import json
import math
import platform
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from backend.app.api.common import page
from backend.app.api.reports import listing_statements
from backend.app.auth import load_actor
from backend.app.db import ROOT, json_dump, sqlite_engine
from backend.app.models import reports, users, versions
from backend.scripts.seed import seed

SAMPLES = 100
WARMUP = 10
ROWS = 10_000
LIMIT = 20
CASES = [
    ("all_first", "admin", None, "", 0),
    ("all_deep", "admin", None, "", 9000),
    ("status_first", "admin", "published", "", 0),
    ("status_deep", "admin", "published", "", 3000),
    ("keyword_first", "admin", None, "渠道月报", 0),
    ("owner_first", "analyst", None, "", 0),
    ("department_first", "manager", None, "", 0),
]

def fill(session):
    seed(session)
    session.execute(delete(reports))
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    owners = session.execute(select(users.c.id, users.c.department_id)
                             .where(users.c.username.in_(("analyst", "manager", "overseas")))
                             .order_by(users.c.id)).all()
    rows = []
    statuses = ("draft", "published", "archived")
    for i in range(ROWS):
        owner = owners[(i // len(statuses)) % len(owners)]
        rows.append({
            "id": i + 1, "title": f"{'渠道月报' if i % 5 == 0 else '销售复盘'} {i:05}", "description": "分页基准合成记录",
            "content": "基准占位正文", "owner_id": owner.id, "department_id": owner.department_id, "dataset_id": 1,
            "status": statuses[i % len(statuses)], "created_at": base.isoformat(timespec="microseconds"),
            "updated_at": (base + timedelta(seconds=i)).isoformat(timespec="microseconds"),
        })
    session.execute(insert(reports), rows)
    session.execute(insert(versions), [
        {"report_id": row["id"], "number": 1, "created_by": row["owner_id"], "created_at": row["updated_at"],
         "snapshot_json": json_dump({**{key: row[key] for key in ("title", "description", "content", "dataset_id")},
                                     "query_id": None, "query": None, "asset_ids": []})}
        for row in rows if row["status"] != "draft"
    ])
    session.execute(update(reports).where(reports.c.status != "draft").values(current_version=1))
    session.commit()

def explain(session, statement):
    sql = str(statement.compile(session.bind, compile_kwargs={"literal_binds": True}))
    return [row[3] for row in session.connection().exec_driver_sql("EXPLAIN QUERY PLAN " + sql)]

def percentile(values, p):
    return sorted(values)[math.ceil(len(values) * p) - 1]

def measure(session):
    data, summary = [], {}
    actors = {row.username: load_actor(session, row) for row in session.execute(select(users))}
    for name, username, status, keyword, offset in CASES:
        actor = actors[username]
        statement, total = listing_statements(actor, status, keyword)
        plans = {"items": explain(session, statement.limit(LIMIT).offset(offset)), "count": explain(session, total)}
        for _ in range(WARMUP):
            page(session, statement, total, LIMIT, offset)
        values = []
        result = {}
        for sample in range(1, SAMPLES + 1):
            start = perf_counter_ns()
            result = page(session, statement, total, LIMIT, offset)
            elapsed_ms = (perf_counter_ns() - start) / 1_000_000
            values.append(elapsed_ms)
            data.append((name, sample, f"{elapsed_ms:.6f}"))
        summary[name] = {"p50_ms": round(percentile(values, .5), 6), "p95_ms": round(percentile(values, .95), 6),
                         "scope": actor.grants["report.read"], "total": result["total"],
                         "returned": len(result["items"]), "offset": offset, "plan": plans}
    return data, summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "benchmarks")
    parser.add_argument("--temp-dir", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.temp_dir:
        args.temp_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="lensbrief-benchmark-", dir=args.temp_dir) as tmp:
        engine = sqlite_engine(Path(tmp) / "bench.sqlite3")
        try:
            config = Config(str(ROOT / "backend" / "alembic.ini"))
            with engine.connect() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            with Session(engine) as session:
                fill(session)
                data, cases = measure(session)
        finally:
            engine.dispose()
    with (args.output / "samples.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["case", "iteration", "elapsed_ms"])
        writer.writerows(data)
    summary = {"environment": {"os": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
                              "sqlite": sqlite3.sqlite_version, "sqlalchemy": version("SQLAlchemy")},
               "rows": ROWS, "limit": LIMIT, "warmups_per_case": WARMUP, "samples_per_case": SAMPLES, "cases": cases}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({name: {k: item[k] for k in ("p50_ms", "p95_ms")} for name, item in cases.items()}, indent=2))

if __name__ == "__main__":
    main()
