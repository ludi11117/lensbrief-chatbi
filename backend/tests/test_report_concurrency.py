import pytest


def test_stale_edit_preserves_new_working_copy(client, auth, body):
    owner = auth()
    manager = auth("manager")
    created = client.post("/api/reports", headers=owner, json=body)
    path = f"/api/reports/{created.json()['id']}"
    initial = client.get(path, headers=owner)
    tag = initial.headers["etag"]
    assert initial.json()["etag"] == tag == created.headers["etag"]

    saved = client.put(path, headers={**manager, "If-Match": tag}, json={**body, "content": "主管的修改"})
    assert saved.status_code == 200 and saved.headers["etag"] != tag
    stale = client.put(path, headers={**owner, "If-Match": tag}, json={**body, "content": "旧页面的修改"})
    assert stale.status_code == 412
    assert client.get(path, headers=owner).json()["content"] == "主管的修改"
    current_tag = saved.headers["etag"]
    merged = client.put(path, headers={**owner, "If-Match": current_tag}, json={**body, "content": "重新核对的工作稿"})
    assert merged.status_code == 200 and merged.headers["etag"] != current_tag

def test_stale_publish_cannot_release_a_different_working_copy(client, auth, body):
    owner = auth()
    created = client.post("/api/reports", headers=owner, json=body)
    path = f"/api/reports/{created.json()['id']}"
    edited = client.put(path, headers=auth("manager"), json={**body, "content": "最新稿"})
    assert client.post(path + "/publish", headers={**owner, "If-Match": created.headers["etag"]}).status_code == 412
    assert client.get(path + "/versions", headers=owner).json()["total"] == 0
    published = client.post(path + "/publish", headers={**owner, "If-Match": edited.headers["etag"]})
    assert published.status_code == 201
    assert client.get(path + "/versions/1", headers=owner).json()["content"] == "最新稿"


@pytest.mark.parametrize(("method", "suffix", "status"), [
    ("POST", "/rollback/1", 201), ("POST", "/archive", 200), ("DELETE", "", 204),
])
def test_stale_report_actions_preserve_new_working_copy(client, auth, body, method, suffix, status):
    owner = auth()
    created = client.post("/api/reports", headers=owner, json=body)
    path = f"/api/reports/{created.json()['id']}"
    assert client.post(path + "/publish", headers=owner).status_code == 201
    previous = client.get(path, headers=owner).headers["etag"]
    edited = client.put(path, headers=auth("manager"), json={**body, "content": "最新稿"})
    assert edited.status_code == 200

    refused = client.request(method, path + suffix, headers={**owner, "If-Match": previous})
    assert refused.status_code == 412
    unchanged = client.get(path, headers=owner).json()
    assert (unchanged["status"], unchanged["current_version"], unchanged["content"]) == ("published", 1, "最新稿")

    verified = client.request(method, path + suffix, headers={**owner, "If-Match": edited.headers["etag"]})
    assert verified.status_code == status
