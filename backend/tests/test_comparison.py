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

def test_previous_period_returns_empty_rows_when_no_data(client, auth, query_body):
    response = client.post("/api/queries", headers=auth(), json={**query_body, "compare_previous": True})
    assert response.status_code == 201, response.text
    assert response.json()["comparison"] == {"start": "2026-08-31", "end": "2026-09-30", "rows": []}

@pytest.mark.parametrize("override", [{"dimension": "day"}, {"start": "0001-01-01", "end": "0001-01-01"}])
def test_previous_period_rejects_unsupported_dimensions_or_invalid_windows(client, auth, query_body, override):
    response = client.post("/api/queries", headers=auth(), json={**query_body, **override, "compare_previous": True})
    assert response.status_code == 422
