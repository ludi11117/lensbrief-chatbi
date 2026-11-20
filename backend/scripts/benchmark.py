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
from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from backend.app.api.common import page
from backend.app.api.reports import listing_statements
from backend.app.auth import Actor
from backend.app.db import ROOT, sqlite_engine
from backend.app.models import reports
from backend.scripts.seed import seed

SAMPLES = 100
WARMUP = 10
ROWS = 10_000
LIMIT = 20
CASES = [
    ("all_first", None, "", 0),
    ("all_deep", None, "", 9000),
    ("status_first", "published", "", 0),
    ("status_deep", "published", "", 3000),
    ("keyword_first", None, "渠道月报", 0),
]
ACTOR = Actor(4, "admin", "管理员", 1, ["admin"], {"report.read": "all"})

def fill(session):
    seed(session)
    session.execute(delete(reports))
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    session.execute(insert(reports), [
        {"title": f"{'渠道月报' if i % 5 == 0 else '销售复盘'} {i:05}", "description": "分页基准合成记录",
         "content": "基准占位正文", "owner_id": (i % 2) + 1, "department_id": 1, "dataset_id": 1,
         "status": ("draft", "published", "archived")[i % 3],
         "created_at": base.isoformat(timespec="microseconds"),
         "updated_at": (base + timedelta(seconds=i)).isoformat(timespec="microseconds")}
        for i in range(ROWS)
    ])
    session.commit()

def explain(session, statement):
    sql = str(statement.compile(session.bind, compile_kwargs={"literal_binds": True}))
    return [row[3] for row in session.connection().exec_driver_sql("EXPLAIN QUERY PLAN " + sql)]

def percentile(values, p):
    return sorted(values)[math.ceil(len(values) * p) - 1]

def measure(session):
    data, summary = [], {}
    for name, status, keyword, offset in CASES:
        statement, total = listing_statements(ACTOR, status, keyword)
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
                         "total": result["total"], "returned": len(result["items"]), "offset": offset, "plan": plans}
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
