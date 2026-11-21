from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext

from backend.app.db import ROOT
from backend.scripts.seed import seed


def test_initial_schema_upgrade_preserves_published_report_query_and_file(app, client, auth, body, query_body):
    owner = auth()
    query = client.post("/api/queries", headers=owner, json=query_body)
    assert query.status_code == 201
    file = client.post("/api/assets", headers=owner, files={"file": ("原始数据.csv", b"month,orders\n10,20\n")})
    assert file.status_code == 201
    asset_id = file.json()["id"]
    query_id = query.json()["id"]
    created = client.post("/api/reports", headers=owner, json={**body, "query_id": query_id, "asset_ids": [asset_id]})
    assert created.status_code == 201
    report_id = created.json()["id"]
    path = f"/api/reports/{report_id}"
    assert client.post(path + "/publish", headers=owner).status_code == 201
    original = client.get(path + "/versions/1", headers=owner).json()

    config = Config(str(ROOT / "backend" / "alembic.ini"))
    with app.state.engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001")
        assert MigrationContext.configure(connection).get_current_revision() == "0001"
    with app.state.engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    with app.state.session_factory() as session:
        seed(session)

    assert client.get(path + "/versions/1", headers=owner).json() == original
    assert client.get(f"/api/queries/{query_id}", headers=owner).json()["result"]["rows"] == query.json()["rows"]
    preview = client.get(f"/api/assets/{asset_id}/csv", headers=owner, params={"report_id": report_id, "version": 1})
    assert preview.json()["rows"] == [["10", "20"]]
    assert client.get("/api/auth/me", headers=auth("admin")).json()["grants"]["knowledge.manage"] == "all"
    assert client.post(path + "/versions/1/feedback", headers=owner, json={"body": "迁移后可继续讨论"}).status_code == 201
