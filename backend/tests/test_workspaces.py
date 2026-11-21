from alembic import command
from alembic.config import Config

from backend.app.db import ROOT
from backend.scripts.seed import seed

def packs(client, headers):
    return client.get("/api/knowledge/packs?dataset_id=1", headers=headers).json()["items"]

def create_context(client, headers, pack_id=None):
    payload = {"title": "渠道周会", "objective": "比较渠道表现", "dataset_id": 1, "knowledge_pack_id": pack_id}
    response = client.post("/api/contexts", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"], payload

def test_context_is_personal_even_with_department_and_admin_scope(client, auth, query_body):
    owner = auth()
    context_id, _ = create_context(client, owner)
    query_response = client.post("/api/queries", headers=owner, json={**query_body, "context_id": context_id})
    assert query_response.status_code == 201, query_response.text
    query_id = query_response.json()["id"]

    manager = auth("manager")
    for headers in (manager, auth("admin")):
        assert client.get("/api/contexts", headers=headers).json()["items"] == []
        assert client.get(f"/api/contexts/{context_id}", headers=headers).status_code == 403
        assert client.get(f"/api/queries?context_id={context_id}", headers=headers).status_code == 403
        assert client.post("/api/queries", headers=headers, json={**query_body, "context_id": context_id}).status_code == 403
        record = client.get(f"/api/queries/{query_id}", headers=headers).json()
        assert "context_id" not in record and "context_id" not in record["filters"]
    history = client.get(f"/api/queries?context_id={context_id}", headers=owner)
    assert [row["id"] for row in history.json()["items"]] == [query_id]

def test_archived_context_keeps_history_and_can_be_restored(client, auth, query_body):
    headers = auth()
    context_id, payload = create_context(client, headers)
    attempt = {**query_body, "context_id": context_id}
    assert client.post("/api/queries", headers=headers, json=attempt).status_code == 201
    route = f"/api/contexts/{context_id}"
    archived = client.put(route, headers=headers, json={**payload, "archived": True})
    assert archived.json()["archived"] is True
    assert client.post("/api/queries", headers=headers, json=attempt).status_code == 409
    assert client.get(f"/api/queries?context_id={context_id}", headers=headers).json()["total"] == 1
    assert client.get("/api/contexts?archived=false", headers=headers).json()["total"] == 0
    assert client.put(route, headers=headers, json=payload).status_code == 200
    assert client.post("/api/queries", headers=headers, json=attempt).status_code == 201

def test_selected_knowledge_revision_stays_in_query_draft_and_published_report(client, auth, query_body, body):
    headers = auth()
    pack = packs(client, headers)[0]
    path = f"/api/knowledge/packs/{pack['id']}"
    context_id, _ = create_context(client, headers, pack["id"])
    attempt = {**query_body, "context_id": context_id}
    original = client.post("/api/queries", headers=headers, json=attempt)
    assert original.status_code == 201, original.text
    result = original.json()
    assert result["knowledge"]["revision"] == 1
    assert [item["title"] for item in result["knowledge"]["items"]] == ["分组口径", "销售额与净收入"]
    payload = {"dataset_id": 1, "title": pack["title"], "items": [{"title": "新的规则", "content": "按支付日核对。"}]}
    assert client.put(path, headers=headers, json=payload).status_code == 403
    assert client.put(path, headers=auth("admin"), json=payload).json()["revision"] == 2

    draft = client.post("/api/drafts/generate", headers=headers, json={"query_id": result["id"]}).json()
    assert "渠道销售复盘 v1" in draft["content"] and "新的规则" not in draft["content"]
    report = client.post("/api/reports", headers=headers, json={**body, "query_id": result["id"]})
    assert report.status_code == 201, report.text
    report_path = f"/api/reports/{report.json()['id']}"
    assert client.post(report_path + "/publish", headers=headers).status_code == 201
    snapshot = client.get(report_path + "/versions/1", headers=headers).json()["query"]["knowledge"]
    assert snapshot == result["knowledge"]
    assert client.post("/api/queries", headers=headers, json=attempt).json()["knowledge"]["revision"] == 2

def test_admin_pack_rejects_unknown_metric_without_leaving_partial_pack(client, auth):
    admin = auth("admin")
    body = {"title": "无效条目", "dataset_id": 1,
            "items": [{"title": "口径", "content": "说明", "metric_id": 999}]}
    assert client.post("/api/knowledge/packs", headers=admin, json=body).status_code == 422
    assert len(packs(client, admin)) == 2
    body["items"][0]["metric_id"] = None
    created = client.post("/api/knowledge/packs", headers=admin, json=body)
    assert (created.status_code, created.json()["revision"]) == (201, 1)

def test_upgrade_from_initial_schema_preserves_reports_and_admin_permissions(app, client, auth):
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    with app.state.engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001")
        command.upgrade(config, "head")
    with app.state.session_factory() as session:
        seed(session)
        seed(session)
    assert client.get("/api/reports/1", headers=auth()).json()["title"] == "十月渠道表现复盘"
    assert len(packs(client, auth())) == 2
    assert client.get("/api/auth/me", headers=auth("admin")).json()["grants"]["knowledge.manage"] == "all"
