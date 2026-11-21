from sqlalchemy import insert, update

from backend.app.models import query_logs, sales

def test_filter_values_respect_the_users_scope(client, auth, app, query_body):
    with app.state.session_factory.begin() as session:
        session.execute(insert(sales).values(dataset_id=1, owner_id=2, department_id=1, day="2026-10-01",
                        channel="主管渠道", product="Trail X", revenue=1999, orders=1, refunds=0))
    route = "/api/datasets/1/dimensions"
    analyst = auth()
    manager = auth("manager")
    for headers, is_visible in ((analyst, False), (manager, True)):
        dimensions = client.get(route, headers=headers).json()["items"]
        channels = next(item["values"] for item in dimensions if item["code"] == "channel")
        assert ("主管渠道" in channels) is is_visible
    query = {**query_body, "channel": "主管渠道"}
    assert client.post("/api/queries", headers=analyst, json=query).status_code == 422
    result = client.post("/api/queries", headers=manager, json=query)
    assert result.status_code == 201, result.text
    assert result.json()["rows"] == [{"label": "主管渠道", "value": 1999}]

def test_same_channel_filter_applies_to_both_comparison_periods(client, auth, query_body):
    headers = auth()
    params = {**query_body, "start": "2026-10-15", "end": "2026-10-21", "compare_previous": True}
    groups = client.post("/api/queries", headers=headers, json=params).json()
    filtered = client.post("/api/queries", headers=headers, json={**params, "channel": "官网", "dimension": "product"})
    assert filtered.status_code == 201, filtered.text
    result = filtered.json()
    assert result["channel"] == "官网"
    for current, combined in ((result, groups), (result["comparison"], groups["comparison"])):
        expected = next(row["value"] for row in combined["rows"] if row["label"] == "官网")
        assert sum(row["value"] for row in current["rows"]) == expected

def test_selected_report_query_scope_applies_to_planning_and_catalog(client, auth, app):
    with app.state.session_factory.begin() as session:
        session.execute(insert(sales).values(dataset_id=1, owner_id=1, department_id=1, day="2026-10-01",
                        channel="协作渠道", product="Trail X", revenue=1999, orders=1, refunds=0))
    route = "/api/datasets/1/dimensions"
    question = {"dataset_id": 1, "question": "按产品只看协作渠道成交额"}
    manager = auth("manager")
    for scope in ("own", "department"):
        data = client.get(route, headers=manager, params={"scope": scope}).json()
        channels = next(item["values"] for item in data["items"] if item["code"] == "channel")
        assert ("协作渠道" in channels) == (scope == "department")
    result = client.post("/api/queries/plan", headers=manager, json={**question, "scope": "department"})
    assert result.status_code == 200
    assert (result.json()["scope"], result.json()["channel"]) == ("department", "协作渠道")
    assert client.post("/api/queries/plan", headers=manager, json={**question, "scope": "own"}).status_code == 422
    assert client.get(route, headers=auth(), params={"scope": "department"}).status_code == 403
    assert client.post("/api/queries/plan", headers=auth(), json={**question, "scope": "department"}).status_code == 403

def test_history_date_filter_includes_last_microsecond_of_the_utc_day(client, auth, app, query_body):
    headers = auth()
    query_ids = [client.post("/api/queries", headers=headers, json=query_body).json()["id"] for _ in range(2)]
    with app.state.session_factory.begin() as session:
        for query_id, executed in zip(query_ids, ("2026-10-31T23:59:59.999999+00:00", "2026-11-01T00:00:00.000000+00:00")):
            session.execute(update(query_logs).where(query_logs.c.id == query_id).values(created_at=executed))
    path = "/api/queries"
    day = client.get(path, headers=headers, params={"start": "2026-10-31", "end": "2026-10-31"}).json()
    assert day["total"] == 1 and day["items"][0]["id"] == query_ids[0]
    assert client.get(path, headers=headers, params={"end": "9999-12-31"}).json()["total"] == 2
