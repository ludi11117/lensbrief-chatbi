import random
from datetime import date, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from backend.app.auth import ACTIONS, passwords
from backend.app.db import begin_write, sqlite_engine, utc_now
from backend.app.models import (
    datasets, departments, dimensions, metrics, permissions, reports, role_permissions, roles,
    sales, user_roles, users,
)
from backend.app.settings import Settings

START = date(2026, 10, 1)
PASSWORD = "LensBrief2026!"
ANALYST_ACTIONS = set(ACTIONS) - {"user.manage", "audit.read"}
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

def seed(session):
    begin_write(session)
    if session.scalar(select(datasets.c.id).where(datasets.c.code == "camera-sales")):
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
