import random
from datetime import date, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from backend.app.auth import ACTIONS, passwords
from backend.app.db import begin_write, sqlite_engine, utc_now
from backend.app.models import (
    datasets, departments, dimensions, knowledge_items, knowledge_packs, metrics, permissions,
    reports, role_permissions, roles, sales, user_roles, users,
)
from backend.app.settings import Settings

START = date(2026, 10, 1)
PASSWORD = "LensBrief2026!"
ANALYST_ACTIONS = set(ACTIONS) - {"user.manage", "audit.read", "knowledge.manage"}
CATALOG = [
    ("gmv", "销售额", "元", "以支付日统计人民币成交金额，含后续退款订单。"),
    ("orders", "支付订单量", "单", "按支付日汇总支付订单数。"),
    ("refund_rate", "退款率", "%", "分组退款订单数除以支付订单数。"),
]
DIMENSIONS = [
    ("channel", "渠道", "按成交来源分组。"),
    ("product", "产品", "按虚构运动相机型号分组。"),
    ("day", "日期", "按支付日期分组。"),
    ("department", "部门", "按负责销售的部门分组。"),
]

def seed_knowledge(session, dataset_id):
    packs = [
        ("channel-review", "渠道销售复盘", "统一比较渠道贡献时的指标口径。",
         [("分组口径", "渠道按成交来源划分。比较前确认统计范围与支付日期一致。", None),
          ("销售额与净收入", "销售额含后续退款订单，不可直接作为净收入。", "gmv"),
          ("订单量解释", "订单量按支付订单计数，同一用户可能产生多笔订单。", "orders")]),
        ("refund-review", "退款风险排查", "用于按产品或渠道比较退款率。",
         [("比较前检查分母", "标记订单数较低的分组，避免把小样本变化当成趋势。", None),
          ("退款率加权", "汇总时应先合计退款数与支付订单数，再相除。", "refund_rate")]),
    ]
    ids = dict(session.execute(select(metrics.c.code, metrics.c.id).where(metrics.c.dataset_id == dataset_id)).all())
    for seed_key, title, description, items in packs:
        if session.scalar(select(knowledge_packs.c.id).where(knowledge_packs.c.seed_key == seed_key)) is not None:
            continue
        pack_id = session.execute(insert(knowledge_packs).values(
            dataset_id=dataset_id, seed_key=seed_key, title=title, description=description, revision=1, updated_at=utc_now()
        )).inserted_primary_key[0]
        session.execute(insert(knowledge_items), [
            dict(pack_id=pack_id, position=index, title=item, content=content, metric_id=ids.get(code))
            for index, (item, content, code) in enumerate(items)
        ])

def seed(session):
    begin_write(session)
    existing_id = session.scalar(select(datasets.c.id).where(datasets.c.code == "camera-sales"))
    if existing_id is not None:
        seed_knowledge(session, existing_id)
        session.commit()
        return
    session.execute(insert(departments), [{"id": 1, "name": "华东运营"}, {"id": 2, "name": "海外运营"}])
    session.execute(insert(roles), [
        {"id": 1, "code": "analyst", "name": "分析师"},
        {"id": 2, "code": "manager", "name": "部门主管"},
        {"id": 3, "code": "admin", "name": "管理员"},
    ])
    session.execute(insert(permissions), [{"code": code} for code in ACTIONS])
    for role_id, scope in enumerate(("own", "department", "all"), start=1):
        codes = ACTIONS if scope == "all" else [code for code in ACTIONS if code in ANALYST_ACTIONS]
        session.execute(insert(role_permissions), [
            {"role_id": role_id, "permission_code": code, "scope": scope} for code in codes
        ])
    people = [("analyst", "周宁", 1, 1), ("manager", "何岚", 1, 2),
              ("overseas", "林遥", 2, 1), ("admin", "陈颖", 1, 3)]
    for user_id, (handle, name, department_id, role_id) in enumerate(people, start=1):
        session.execute(insert(users).values(id=user_id, username=handle, name=name,
                         department_id=department_id, active=True, password_hash=passwords.hash(PASSWORD)))
        session.execute(insert(user_roles).values(user_id=user_id, role_id=role_id))
    session.execute(insert(datasets).values(id=1, code="camera-sales", name="运动相机销售",
                    description="2026 年 10 月的虚构交易汇总，覆盖华东与海外运营。"))
    session.execute(insert(metrics), [
        dict(dataset_id=1, code=code, name=name, unit=unit, description=description)
        for code, name, unit, description in CATALOG
    ])
    seed_knowledge(session, 1)
    session.execute(insert(dimensions), [
        dict(dataset_id=1, code=code, name=name, description=description)
        for code, name, description in DIMENSIONS
    ])
    rng = random.Random(360)
    facts = []
    for offset in range(31):
        day = START + timedelta(days=offset)
        for owner, department in ((1, 1), (2, 1), (3, 2)):
            for channel in ("官网", "电商平台", "线下零售"):
                for product, price in (("Trail X", 1999), ("Pocket Air", 1399), ("Orbit Mini", 999)):
                    orders = rng.randint(8, 35) + (9 if day.weekday() >= 5 else 0)
                    facts.append(dict(dataset_id=1, owner_id=owner, department_id=department, day=day.isoformat(),
                                      channel=channel, product=product, revenue=orders * price,
                                      orders=orders, refunds=rng.randint(0, 4)))
    session.execute(insert(sales), facts)
    now = utc_now()
    session.execute(insert(reports), [
        dict(owner_id=1, department_id=1, dataset_id=1, title="十月渠道表现复盘",
             description="比较三个销售渠道，记录值得跟进的变化。", content="先按渠道查看销售额，再补充退款率。",
             status="draft", created_at=now, updated_at=now),
        dict(owner_id=3, department_id=2, dataset_id=1, title="海外十月销售概览",
             description="海外运营内部报告。", content="按产品整理成交情况。",
             status="draft", created_at=now, updated_at=now),
    ])
    session.commit()

if __name__ == "__main__":
    engine = sqlite_engine(Settings.from_env().database)
    with Session(engine) as session:
        seed(session)
    engine.dispose()
