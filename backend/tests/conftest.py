from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from backend.app.db import ROOT
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.scripts.seed import PASSWORD, seed

@pytest.fixture(scope="session")
def sign_in_seed(tmp_path_factory):
    root = tmp_path_factory.mktemp("seed")
    database = root / "seed.sqlite3"
    settings = Settings(database, root / "files", "test-jwt-secret-lensbrief-at-least-32-characters")
    app = create_app(settings)
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    with app.state.engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with app.state.session_factory() as session:
        seed(session)
    app.state.engine.dispose()
    return Path(database)

@pytest.fixture
def app(tmp_path, sign_in_seed, monkeypatch):
    monkeypatch.delenv("LENSBRIEF_FRONTEND_DIST", raising=False)
    database = tmp_path / "test.sqlite3"
    database.write_bytes(sign_in_seed.read_bytes())
    application = create_app(Settings(database, tmp_path / "files", "test-jwt-secret-lensbrief-at-least-32-characters"))
    yield application
    application.state.engine.dispose()

@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

@pytest.fixture
def auth(client):
    headers = {}
    def for_user(username="analyst"):
        if username not in headers:
            res = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
            assert res.status_code == 200, res.text
            headers[username] = {"Authorization": "Bearer " + res.json()["access_token"]}
        return headers[username]
    return for_user

@pytest.fixture
def body():
    return {"title": "渠道复盘", "description": "十月", "content": "版本一", "dataset_id": 1}

@pytest.fixture
def query_body():
    return {"dataset_id": 1, "metric": "gmv", "dimension": "channel",
            "start": "2026-10-01", "end": "2026-10-31"}
