def publish_report(client, headers, payload):
    report = client.post("/api/reports", headers=headers, json=payload)
    assert report.status_code == 201, report.text
    path = f"/api/reports/{report.json()['id']}"
    assert client.post(path + "/publish", headers=headers).status_code == 201
    return path

def test_version_feedback_is_shared_within_department_and_keeps_original_version(client, auth, body):
    owner = auth()
    manager = auth("manager")
    path = publish_report(client, owner, body)
    first = path + "/versions/1/feedback"
    response = client.post(first, headers=manager, json={"body": "请核对渠道归类。"})
    assert response.status_code == 201, response.text
    assert response.json()["author_name"] == "何岚"
    assert client.get(first, headers=owner).json()["items"] == [response.json()]
    assert client.post(path + "/publish", headers=owner).status_code == 201
    assert client.post(path + "/rollback/1", headers=owner).status_code == 201
    for number in (2, 3):
        assert client.get(path + f"/versions/{number}/feedback", headers=owner).json()["total"] == 0
    assert client.get(first, headers=manager).json()["total"] == 1
    audit = client.get("/api/audit", headers=auth("admin")).json()["items"]
    entry = next(item for item in audit if item["action"] == "report.feedback")
    assert entry["detail"] == {"version": 1, "feedback_id": response.json()["id"]}

def test_feedback_enforces_report_permissions_and_version_exists(client, auth, body):
    owner = auth()
    other = auth("overseas")
    path = publish_report(client, owner, body) + "/versions/"
    assert client.get(path + "1/feedback", headers=other).status_code == 403
    assert client.post(path + "1/feedback", headers=other, json={"body": "越权"}).status_code == 403
    assert client.get(path + "2/feedback", headers=owner).status_code == 404
    assert client.post(path + "1/feedback", headers=owner, json={"body": "  "}).status_code == 422

def test_feedback_pages_and_archived_version_is_read_only(client, auth, body):
    headers = auth()
    path = publish_report(client, headers, body)
    endpoint = path + "/versions/1/feedback"
    assert client.post(endpoint, headers=headers, json={"body": "第一条"}).status_code == 201
    assert client.post(endpoint, headers=headers, json={"body": "第二条"}).status_code == 201
    page = client.get(endpoint + "?limit=1&offset=1", headers=headers).json()
    assert page["total"] == 2 and [item["body"] for item in page["items"]] == ["第一条"]
    assert client.post(path + "/archive", headers=headers).status_code == 200
    assert client.get(endpoint, headers=headers).json()["total"] == 2
    assert client.post(endpoint, headers=headers, json={"body": "归档之后"}).status_code == 409
