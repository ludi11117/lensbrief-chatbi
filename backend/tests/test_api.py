from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO

import httpx
import pytest
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import func, select

from backend.app.api import reports as report_api
from backend.app.models import audit_logs, reports, version_assets, versions

def make_report(client, headers, body):
    res = client.post("/api/reports", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]

def do(client, path, headers, status=201):
    res = client.post("/api" + path, headers=headers)
    assert res.status_code == status, res.text
    return res.json()

def test_unauthenticated_401_and_bad_credentials(client):
    assert client.get("/api/reports").status_code == 401
    assert client.post("/api/auth/login", json={"username": "analyst", "password": "invalid"}).status_code == 401

def test_same_department_and_cross_department_403_is_audited(client, auth):
    assert client.get("/api/reports/1", headers=auth("manager")).status_code == 200
    assert client.get("/api/reports/2", headers=auth("manager")).status_code == 403
    assert client.post("/api/reports/2/publish", headers=auth("analyst")).status_code == 403
    assert client.get("/api/access", headers=auth()).status_code == 403
    audit = client.get("/api/audit", headers=auth("admin")).json()["items"]
    assert {row["detail"]["permission"] for row in audit if row["action"] == "access.denied"} >= {
        "report.read", "report.publish", "user.manage"
    }
    assert client.get("/api/reports/2", headers=auth("admin")).status_code == 200
    assert client.get("/api/reports", headers=auth()).json()["total"] == 1
    assert client.get("/api/reports", headers=auth("admin")).json()["total"] == 2

@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"status": "pending"}])
def test_invalid_pagination_or_status(client, auth, params):
    assert client.get("/api/reports", headers=auth(), params=params).status_code == 422

def test_pagination_filters_and_soft_delete(client, auth, body):
    headers = auth()
    report_id = make_report(client, headers, {**body, "title": "渠道复盘 100%_完成"})
    first = client.get("/api/reports", headers=headers, params={"limit": 1}).json()
    second = client.get("/api/reports", headers=headers, params={"limit": 1, "offset": 1}).json()
    out = client.get("/api/reports", headers=headers, params={"limit": 1, "offset": 2}).json()
    assert first["total"] == second["total"] == out["total"] == 2
    assert first["items"][0]["id"] == report_id
    assert second["items"][0]["id"] != report_id and out["items"] == []
    filtered = client.get("/api/reports", headers=headers, params={"q": "%_", "status": "draft"}).json()
    assert [item["id"] for item in filtered["items"]] == [report_id]
    assert client.delete(f"/api/reports/{report_id}", headers=headers).status_code == 204
    assert client.get(f"/api/reports/{report_id}", headers=headers).status_code == 404
    assert client.get("/api/reports", headers=headers).json()["total"] == 1

def test_report_summary_counts_only_visible_current_reports(client, auth):
    owner = auth()
    route = "/api/reports/summary"
    assert client.get(route, headers=owner).json() == {"total": 1, "draft": 1, "published": 0, "archived": 0}
    assert client.get(route, headers=auth("admin")).json()["total"] == 2
    assert client.post("/api/reports/1/publish", headers=owner).status_code == 201
    assert client.post("/api/reports/1/archive", headers=owner).status_code == 200
    assert client.get(route, headers=owner).json() == {"total": 1, "draft": 0, "published": 0, "archived": 1}
    assert client.delete("/api/reports/1", headers=owner).status_code == 204
    assert client.get(route, headers=owner).json()["total"] == 0

def test_publish_failure_rolls_back_status_version_attachments_and_audit(client, auth, body, app, monkeypatch):
    headers = auth()
    upload = client.post("/api/assets", headers=headers, files={"file": ("a.csv", b"a,b\n1,2\n", "text/csv")})
    assert upload.status_code == 201, upload.text
    report_id = make_report(client, headers, {**body, "asset_ids": [upload.json()["id"]]})
    original_audit = report_api.audit

    def fail_at_audit(session, *args, **kwargs):
        original_audit(session, *args, **kwargs)
        raise RuntimeError("simulated failure after writing the audit row")

    monkeypatch.setattr(report_api, "audit", fail_at_audit)
    response = client.post(f"/api/reports/{report_id}/publish", headers=headers)
    assert response.status_code == 500
    with app.state.session_factory() as session:
        report = session.execute(select(reports).where(reports.c.id == report_id)).one()
        assert (report.status, report.current_version) == ("draft", None)
        assert session.scalar(select(func.count()).select_from(versions)) == 0
        assert session.scalar(select(func.count()).select_from(version_assets)) == 0
        assert session.scalar(select(func.count()).select_from(audit_logs).where(audit_logs.c.action == "report.publish")) == 0

def test_version_diff_and_rollback_preserve_history(client, auth, body):
    headers = auth()
    report_id = make_report(client, headers, body)
    path = f"/reports/{report_id}"
    assert do(client, path + "/publish", headers)["number"] == 1
    edited = client.put("/api" + path, headers=headers, json={**body, "title": "新标题", "content": "版本二"})
    assert edited.json()["has_unpublished_changes"]
    assert client.get("/api" + path + "/versions/1", headers=headers).json()["content"] == "版本一"
    assert do(client, path + "/publish", headers)["number"] == 2
    diff = client.get("/api" + path + "/versions/diff?base=1&target=2", headers=headers).json()
    assert diff["changes"] == [{"field": "title", "before": body["title"], "after": "新标题"}]
    assert diff["content_changed"]
    assert diff["content_diff"] == ["--- v1", "+++ v2", "@@ -1 +1 @@", "-版本一", "+版本二"]
    restored = do(client, path + "/rollback/1", headers)
    assert (restored["number"], restored["restored_from"]) == (3, 1)
    assert client.get("/api" + path, headers=headers).json()["content"] == "版本一"
    assert client.get("/api" + path + "/versions/2", headers=headers).json()["content"] == "版本二"
    assert [row["number"] for row in client.get("/api" + path + "/versions", headers=headers).json()["items"]] == [3, 2, 1]

def test_concurrent_publish_serializes_version_numbers(client, auth, body):
    headers = auth()
    report_id = make_report(client, headers, body)
    path = f"/reports/{report_id}/publish"
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: do(client, path, headers), range(2)))
    assert sorted(response["number"] for response in responses) == [1, 2]

def test_invalid_state_transitions(client, auth, body):
    headers = auth()
    path = f"/reports/{make_report(client, headers, body)}"
    do(client, path + "/archive", headers, 409)
    do(client, path + "/rollback/1", headers, 409)
    do(client, path + "/publish", headers)
    assert do(client, path + "/archive", headers, 200)["status"] == "archived"
    do(client, path + "/publish", headers, 409)
    assert client.put("/api" + path, headers=headers, json=body).status_code == 409

@pytest.mark.parametrize("name,data", [
    ("shell.txt", b"a,b\n1,2"), ("broken.png", b"not an image"),
    ("broken.pdf", b"%PDF-1.7\nbroken"), ("broken.csv", b"a,b\n1\n"), ("binary.csv", b"a,\0b"),
])
def test_rejects_invalid_file_content(client, auth, name, data):
    assert client.post("/api/assets", headers=auth(), files={"file": (name, data, "text/csv")}).status_code == 415

def test_upload_size_limit(client, auth):
    data = b"A" * (5 * 1024 * 1024 + 1)
    assert client.post("/api/assets", headers=auth(), files={"file": ("big.csv", data)}).status_code == 413

def test_assets_page_is_private_and_supports_reuse(client, auth, body):
    owner = auth()
    older = client.post("/api/assets", headers=owner, files={"file": ("older.csv", b"a\n1\n")}).json()
    recent = client.post("/api/assets", headers=owner, files={"file": ("recent.csv", b"a\n2\n")}).json()
    for offset, expected in enumerate([[recent], [older], []]):
        result = client.get("/api/assets", headers=owner, params={"limit": 1, "offset": offset})
        assert result.json() == {"items": expected, "limit": 1, "offset": offset, "total": 2}
    assert client.get("/api/assets", headers=auth("admin")).json()["total"] == 0

    for title in ("渠道复盘", "经营简报"):
        report_id = make_report(client, owner, {**body, "title": title, "asset_ids": [recent["id"]]})
        assert client.get(f"/api/reports/{report_id}", headers=owner).json()["assets"] == [recent]

def test_csv_attachment_is_authorized_against_version(client, auth, body):
    headers = auth()
    file = client.post("/api/assets", headers=headers, files={"file": ("数据.csv", "渠道,订单\n官网,3\n".encode())}).json()
    report_id = make_report(client, headers, {**body, "asset_ids": [file["id"]]})
    path = f"/api/assets/{file['id']}"
    assert client.get(path + "/content", headers=auth("manager")).status_code == 403
    do(client, f"/reports/{report_id}/publish", headers)
    client.put(f"/api/reports/{report_id}", headers=headers, json=body)
    params = {"report_id": report_id, "version": 1}
    assert client.get(path + "/csv", headers=auth("manager"), params=params).json()["rows"] == [["官网", "3"]]
    assert client.get(path + "/content", headers=auth("overseas"), params=params).status_code == 403
    assert client.get(path + "/content", headers=headers, params={"report_id": report_id}).status_code == 403
    res = client.get(path + "/content", headers=headers, params={**params, "download": True})
    assert res.headers["content-disposition"].startswith("attachment;")

@pytest.mark.parametrize("kind", ["png", "pdf"])
def test_image_and_pdf_content(client, auth, kind):
    payload = BytesIO()
    if kind == "png":
        Image.new("RGB", (10, 10), color="blue").save(payload, "PNG")
        mime = "image/png"
    else:
        writer = PdfWriter()
        writer.add_blank_page(width=60, height=40)
        writer.write(payload)
        mime = "application/pdf"
    res = client.post("/api/assets", headers=auth(), files={"file": ("valid." + kind, payload.getvalue())})
    assert res.status_code == 201, res.text
    saved = client.get(f"/api/assets/{res.json()['id']}/content", headers=auth())
    assert saved.headers["content-type"] == mime and saved.content == payload.getvalue()

def test_catalog_and_query_scope_logging_and_mock(client, auth, query_body):
    headers = auth()
    catalog = client.get("/api/datasets/1/metrics?limit=1&offset=1", headers=headers).json()
    assert catalog["total"] == 3 and len(catalog["items"]) == 1
    assert client.get("/api/datasets/1/dimensions", headers=headers).json()["total"] == 4
    own = client.post("/api/queries", headers=headers, json=query_body)
    assert own.status_code == 201, own.text
    data = own.json()
    assert data["scope"] == "own" and len(data["rows"]) == 3
    draft = client.post("/api/drafts/generate", headers=headers, json={"query_id": data["id"], "goal": "复盘渠道"})
    assert draft.status_code == 200 and draft.json()["mode"] == "mock"
    assert data["rows"][0]["label"] in draft.json()["content"]
    assert client.post("/api/queries", headers=headers, json={**query_body, "scope": "all"}).status_code == 403
    assert client.post("/api/queries", headers=headers, json={**query_body, "metric": "unknown"}).status_code == 422
    department = client.post("/api/queries", headers=auth("manager"), json=query_body).json()
    assert department["scope"] == "department"
    assert sum(r["value"] for r in department["rows"]) > sum(r["value"] for r in data["rows"])
    logs = client.get("/api/queries?user_id=1&start=2026-01-01&end=2099-12-31", headers=auth("admin")).json()
    assert [item["status"] for item in logs["items"]] == ["invalid", "denied", "ok"]
    assert client.get(f"/api/queries/{data['id']}", headers=auth("overseas")).status_code == 403

def test_admin_changes_role_and_existing_token_receives_new_permissions(client, auth):
    person = auth("overseas")
    assert client.get("/api/access", headers=person).status_code == 403
    updated = client.put("/api/access/users/3/roles", headers=auth("admin"), json={"roles": ["admin"]})
    assert updated.status_code == 200
    assert client.get("/api/access", headers=person).status_code == 200
    assert client.put("/api/access/users/4/roles", headers=auth("admin"), json={"roles": []}).status_code == 409

def test_department_cannot_read_or_attach_admin_global_query(client, auth, query_body, body):
    admin = auth("admin")
    created = client.post("/api/queries", headers=admin, json=query_body)
    assert created.status_code == 201, created.text
    assert created.json()["scope"] == "all"
    query_id = created.json()["id"]
    manager = auth("manager")
    assert client.get("/api/queries", headers=manager).json()["total"] == 0
    assert client.get(f"/api/queries/{query_id}", headers=manager).status_code == 403
    assert client.post("/api/reports", headers=admin, json={**body, "query_id": query_id}).status_code == 403

def test_openai_compatible_draft_contract_without_network(client, auth, query_body, app, monkeypatch):
    app.state.settings = replace(app.state.settings, draft_mode="llm", model_url="https://model.example/v1",
                                 model_name="fixture", model_key="test-model-key")
    headers = auth()
    query_id = client.post("/api/queries", headers=headers, json=query_body).json()["id"]
    seen = []

    def fake_post(url, **options):
        seen.append(options["json"])
        assert url == "https://model.example/v1/chat/completions"
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": {"content": '{"title":"渠道分析","description":"十月","content":"检查数据口径。"}'}}]
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    result = client.post("/api/drafts/generate", headers=headers, json={"query_id": query_id, "goal": "复盘"})
    assert (result.status_code, result.json()["mode"], result.json()["title"]) == (200, "llm", "渠道分析")
    assert seen[0]["model"] == "fixture"
    assert '"scope":"own"' in seen[0]["messages"][-1]["content"]
