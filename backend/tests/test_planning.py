import pytest

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
                      "metric": "refund_rate", "dimension": "product", "scope": "own", "notes": []}
    assert client.get("/api/queries", headers=headers).json()["total"] == 0
    fields = {name: value for name, value in result.items() if name != "notes"}
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

@pytest.mark.parametrize("question", [
    "按渠道查看销售额和订单量", "同比分析上月各渠道销售额", "看看销售情况", "按产品看官网销售额",
    "2026-10-15 至 2026-10-01 按渠道看销售额", "2026-13-01 按渠道看销售额",
    "2026年11月2日按渠道看销售额", "2026年9月和10月按渠道看销售额",
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
