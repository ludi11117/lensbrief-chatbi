import json
from dataclasses import replace

import httpx
import pytest
from sqlalchemy import update

from backend.app.models import sales

def plan(client, headers, question, context_id=None):
    return client.post("/api/queries/plan", headers=headers, json={
        "question": question, "dataset_id": 1, "context_id": context_id,
    })

def context(client, headers, title="日常分析"):
    created = client.post("/api/contexts", headers=headers, json={"dataset_id": 1, "title": title})
    assert created.status_code == 201
    return created.json()["id"]

def test_plan_parses_explicit_window_without_executing_query(client, auth):
    headers = auth()
    response = plan(client, headers, "2026-10-02 至 2026-10-17 按产品看退款率")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result == {"dataset_id": 1, "context_id": None, "start": "2026-10-02", "end": "2026-10-17",
                      "metric": "refund_rate", "dimension": "product", "scope": "own", "notes": [], "source": "rules",
                      "compare_previous": False, "channel": None}
    assert client.get("/api/queries", headers=headers).json()["total"] == 0
    fields = {name: value for name, value in result.items() if name not in ("notes", "source")}
    executed = client.post("/api/queries", headers=headers, json=fields)
    assert executed.status_code == 201 and len(executed.json()["rows"]) == 3

def test_scoped_default_window_and_implicit_year(client, auth):
    manager = auth("manager")
    result = plan(client, manager, "按渠道看成交额").json()
    assert (result["start"], result["end"], result["scope"]) == ("2026-10-02", "2026-10-31", "department")
    assert "30" in result["notes"][0]
    month = plan(client, manager, "十月按部门查订单量").json()
    assert (month["start"], month["end"], month["dimension"]) == ("2026-10-01", "2026-10-31", "department")
    assert "2026 年" in month["notes"][0]
    assert plan(client, auth("admin"), "2026年10月按渠道看GMV").json()["scope"] == "department"

def test_recent_days_use_latest_visible_data_day(app, client, auth, query_body):
    with app.state.session_factory() as session:
        session.execute(update(sales).where(sales.c.department_id == 2, sales.c.day == "2026-10-31")
                        .values(day="2026-11-07"))
        session.commit()
    owner = auth()
    work = context(client, owner)
    ran = client.post("/api/queries", headers=owner, json={
        **query_body, "end": "2026-10-08", "context_id": work,
    })
    assert ran.status_code == 201
    for question, context_id in [("最近 7 天按产品看成交额", None), ("改成过去7个自然日", work)]:
        resolved = plan(client, owner, question, context_id)
        assert resolved.status_code == 200, resolved.text
        result = resolved.json()
        assert (result["start"], result["end"]) == ("2026-10-25", "2026-10-31")
        assert "最新数据日 2026-10-31" in result["notes"][0]
    assert plan(client, auth("overseas"), "最近7天按渠道看成交额").json()["end"] == "2026-11-07"

def test_period_comparison_can_be_planned_inherited_and_cleared(client, auth):
    headers = auth()
    work = context(client, headers)
    parsed = plan(client, headers, "最近7天按产品看成交额并对照上一期", work)
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["compare_previous"] is True
    fields = {name: value for name, value in parsed.json().items() if name not in ("notes", "source")}
    assert client.post("/api/queries", headers=headers, json=fields).status_code == 201
    inherited = plan(client, headers, "改看退款率", work).json()
    assert inherited["compare_previous"] is True
    assert "上一期对照" in inherited["notes"][0]
    assert plan(client, headers, "改为取消对照", work).json()["compare_previous"] is False
    assert plan(client, headers, "改按日", work).json()["compare_previous"] is False
    daily = plan(client, headers, "最近7天按日看销售额并对照上一期")
    assert daily.status_code == 422 and "分组" in daily.json()["detail"]

@pytest.mark.parametrize("question", [
    "按渠道查看销售额和订单量", "同比分析上月各渠道销售额", "看看销售情况", "按产品比较官网和电商平台销售额",
    "2026-10-15 至 2026-10-01 按渠道看销售额", "2026-13-01 按渠道看销售额",
    "2026年11月2日按渠道看销售额", "2026年9月和10月按渠道看销售额",
    "最近367天按产品看退款率", "最近一周按产品看退款率", "十月和最近7天按渠道看销售额",
])
def test_ambiguous_invalid_or_unsupported_questions_rejected(client, auth, question):
    response = plan(client, auth(), question)
    assert response.status_code == 422

def test_followup_only_uses_latest_successful_query_from_owned_context(client, auth, query_body):
    owner = auth()
    work = context(client, owner)
    other = context(client, owner, "其他分析")
    assert plan(client, owner, "改按产品", work).status_code == 422
    first = client.post("/api/queries", headers=owner, json={
        **query_body, "context_id": work, "scope": "own", "start": "2026-10-05",
    })
    assert first.status_code == 201
    assert client.post("/api/queries", headers=owner, json={
        **query_body, "metric": "unsupported", "context_id": work,
    }).status_code == 422
    assert client.post("/api/queries", headers=owner, json={
        **query_body, "context_id": other, "metric": "refund_rate",
    }).status_code == 201
    resolved = plan(client, owner, "改按产品", work).json()
    assert (resolved["metric"], resolved["dimension"], resolved["start"]) == ("gmv", "product", "2026-10-05")
    assert "指标、日期" in resolved["notes"][0]
    assert plan(client, auth("manager"), "改按产品", work).status_code == 403
    assert plan(client, owner, "改成不知道", work).status_code == 422
    assert plan(client, owner, "改按产品", other).json()["metric"] == "refund_rate"
    assert client.get(f"/api/queries?context_id={work}", headers=owner).json()["total"] == 2

@pytest.fixture
def provider(app, monkeypatch):
    app.state.settings = replace(app.state.settings, planner_mode="llm", model_url="https://model.example/v1",
                                 model_name="test-model", model_key="test-only")
    calls = []

    def configure(reply):
        def post(url, **kwargs):
            calls.append((url, kwargs["json"]))
            if isinstance(reply, Exception):
                raise reply
            return httpx.Response(200, request=httpx.Request("POST", url),
                                  json={"choices": [{"message": {"content": json.dumps(reply)}}]})
        monkeypatch.setattr(httpx, "post", post)
        return calls

    return configure

def test_model_planner_only_sends_question_and_catalog_to_fill_missing_axis(client, auth, provider):
    seen = provider({"supported": True, "metric": "orders", "dimension": "product"})
    actor = auth()
    reply = plan(client, actor, "2026年10月比较各款的下单笔数")
    assert reply.status_code == 200, reply.text
    assert (reply.json()["source"], reply.json()["metric"], reply.json()["scope"]) == ("llm", "orders", "own")
    assert reply.json()["start"] == "2026-10-01"
    url, call = seen[0]
    assert url == "https://model.example/v1/chat/completions"
    sent = json.loads(call["messages"][-1]["content"])
    assert set(sent) == {"question", "recognized", "metrics", "dimensions"}
    assert client.get("/api/queries", headers=actor).json()["total"] == 0

@pytest.mark.parametrize(("reply", "status"), [
    ({"supported": False}, 422),
    ({"supported": True, "metric": "orders", "dimension": "product", "scope": "all"}, 502),
    ({"supported": True, "metric": "orders", "dimension": "province"}, 502),
    ({"supported": True, "metric": "gmv", "dimension": "product"}, 502),
    (httpx.ConnectError("provider-down"), 502),
])
def test_invalid_model_suggestion_or_failure_cannot_replace_known_metric(client, auth, provider, reply, status):
    provider(reply)
    response = plan(client, auth(), "按各款看看订单量")
    assert response.status_code == status, response.text

def test_deterministic_rules_still_work_without_model_in_llm_mode(client, auth, provider):
    seen = provider(httpx.ConnectError("provider-down"))
    assert plan(client, auth(), "按渠道看销售额").json()["source"] == "rules"
    assert plan(client, auth(), "按渠道看退款率和销售额").status_code == 422
    assert plan(client, auth(), "2026-09-31 看各款成交情况").status_code == 422
    assert seen == []

def test_channel_from_authorized_catalog_is_preserved_or_cleared_in_followups(client, auth, query_body):
    headers = auth()
    context_id = context(client, headers)
    parsed = plan(client, headers, "十月按产品只看官网成交额", context_id)
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["channel"] == "官网"
    ran = client.post("/api/queries", headers=headers, json={
        **query_body, "channel": "官网", "context_id": context_id,
    })
    assert ran.status_code == 201
    assert plan(client, headers, "改看退款率", context_id).json()["channel"] == "官网"
    assert plan(client, headers, "改成全部渠道", context_id).json()["channel"] is None
    assert plan(client, headers, "改成只看全部渠道", context_id).json()["channel"] is None
    assert plan(client, headers, "按产品只看抖音成交额", context_id).status_code == 422
    for question in (
        "按产品只看官网和抖音成交额", "按产品只看抖音和官网成交额",
        "按产品看官网或抖音成交额", "按产品看官网成交额，不包含线下零售",
    ):
        assert plan(client, headers, question, context_id).status_code == 422
