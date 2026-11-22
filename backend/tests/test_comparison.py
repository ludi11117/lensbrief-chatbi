from decimal import Decimal

import pytest

def test_previous_period_uses_same_metric_scope_and_is_saved_with_report(client, auth, body, query_body):
    headers = auth("manager")
    ordinary = {**query_body, "metric": "refund_rate", "dimension": "product"}
    prior = client.post("/api/queries", headers=headers, json={
        **ordinary, "start": "2026-10-08", "end": "2026-10-14",
    }).json()
    current = {**ordinary, "start": "2026-10-15", "end": "2026-10-21"}
    plain = client.post("/api/queries", headers=headers, json=current).json()
    response = client.post("/api/queries", headers=headers, json={**current, "compare_previous": True})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["rows"] == plain["rows"]
    assert result["scope"] == "department"
    assert result["comparison"] == {"start": prior["start"], "end": prior["end"], "rows": prior["rows"]}
    report = client.post("/api/reports", headers=headers, json={**body, "query_id": result["id"]})
    assert report.status_code == 201, report.text
    path = f"/api/reports/{report.json()['id']}"
    assert client.post(path + "/publish", headers=headers).status_code == 201
    saved = client.get(path + "/versions/1", headers=headers).json()
    assert saved["query"]["comparison"] == result["comparison"]

def test_comparison_draft_reports_percentage_point_change(client, auth, query_body):
    headers = auth()
    result = client.post("/api/queries", headers=headers, json={
        **query_body, "metric": "refund_rate", "dimension": "product", "compare_previous": True,
        "start": "2026-10-15", "end": "2026-10-21",
    }).json()
    peak = max(result["rows"], key=lambda row: row["value"])
    prior = next(row for row in result["comparison"]["rows"] if row["label"] == peak["label"])
    difference = Decimal(str(peak["value"])) - Decimal(str(prior["value"]))
    draft = client.post("/api/drafts/generate", headers=headers, json={"query_id": result["id"]})
    assert draft.status_code == 200
    assert f"{peak['label']}的本期与对照期差值为 {difference.normalize():+,f} 百分点" in draft.json()["content"]

def test_previous_period_returns_empty_rows_when_no_data(client, auth, query_body):
    response = client.post("/api/queries", headers=auth(), json={**query_body, "compare_previous": True})
    assert response.status_code == 201, response.text
    assert response.json()["comparison"] == {"start": "2026-08-31", "end": "2026-09-30", "rows": []}

def test_version_diff_reports_changed_saved_query_conditions(client, auth, body, query_body):
    headers = auth()

    def run_query(**overrides):
        response = client.post("/api/queries", headers=headers, json={**query_body, **overrides})
        assert response.status_code == 201, response.text
        return response.json()["id"]

    first = run_query()
    second = run_query(start="2026-10-15", channel="官网", compare_previous=True)
    created = client.post("/api/reports", headers=headers, json={**body, "query_id": first})
    assert created.status_code == 201
    path = f"/api/reports/{created.json()['id']}"
    assert client.post(path + "/publish", headers=headers).status_code == 201
    assert client.put(path, headers=headers, json={**body, "query_id": second}).status_code == 200
    assert client.post(path + "/publish", headers=headers).status_code == 201

    result = client.get(path + "/versions/diff", headers=headers, params={"base": 1, "target": 2}).json()

    assert result["changes"] == [{"field": "query_id", "before": first, "after": second}]
    assert result["query_changes"] == [
        {"field": "start", "before": "2026-10-01", "after": "2026-10-15"},
        {"field": "channel", "before": None, "after": "官网"},
        {"field": "comparison_window", "before": None, "after": "2026-09-28 至 2026-10-14"},
    ]

@pytest.mark.parametrize("override", [{"dimension": "day"}, {"start": "0001-01-01", "end": "0001-01-01"}])
def test_previous_period_rejects_unsupported_dimensions_or_invalid_windows(client, auth, query_body, override):
    response = client.post("/api/queries", headers=auth(), json={**query_body, **override, "compare_previous": True})
    assert response.status_code == 422
