import json
from collections import deque
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest


@pytest.fixture
def model_server(app, monkeypatch):
    requests = []
    responses = deque()

    class ModelHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers.get("Authorization"), payload))
            status, message = responses.popleft()
            content = json.dumps({"choices": [{"message": {"content": message}}]}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    with ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler) as server:
        app.state.settings = replace(
            app.state.settings, draft_mode="llm", planner_mode="llm",
            model_url=f"http://127.0.0.1:{server.server_port}/v1/",
            model_name="fixture", model_key="test-model-key",
        )
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield requests, responses
        finally:
            server.shutdown()
            thread.join()


def test_compatible_model_receives_only_scoped_aggregates_over_http(client, auth, query_body, model_server):
    requests, responses = model_server
    responses.append((200, '```json\n{"title":"渠道分析","description":"十月","content":"检查数据口径。"}\n```'))
    headers = auth()
    query = client.post("/api/queries", headers=headers, json=query_body).json()

    draft = client.post("/api/drafts/generate", headers=headers, json={"query_id": query["id"], "goal": "复盘"})

    assert draft.status_code == 200, draft.text
    assert (draft.json()["mode"], draft.json()["title"]) == ("llm", "渠道分析")
    (path, bearer, payload), = requests
    assert (path, bearer, payload["model"]) == ("/v1/chat/completions", "Bearer test-model-key", "fixture")
    sent = json.loads(payload["messages"][-1]["content"])
    assert set(sent) == {"goal", "result"}
    assert (sent["goal"], sent["result"]["scope"], sent["result"]["rows"]) == ("复盘", "own", query["rows"])


@pytest.mark.parametrize(("status", "message"), [(503, ""), (200, "无法解析的模型正文")])
def test_compatible_model_failure_can_reuse_query_in_offline_mode(client, auth, query_body, model_server, status, message):
    requests, responses = model_server
    responses.append((status, message))
    headers = auth()
    query = client.post("/api/queries", headers=headers, json=query_body).json()
    payload = {"query_id": query["id"], "goal": "复盘"}

    failed = client.post("/api/drafts/generate", headers=headers, json=payload)
    offline = client.post("/api/drafts/generate", headers=headers, json={**payload, "mode": "mock"})

    assert failed.status_code == 502
    assert offline.status_code == 200
    assert (offline.json()["mode"], offline.json()["query_id"]) == ("mock", query["id"])
    assert len(requests) == 1


def test_compatible_planner_http_round_trip_only_receives_catalog(client, auth, model_server):
    requests, responses = model_server
    responses.append((200, '{"supported":true,"metric":"orders","dimension":"product"}'))
    headers = auth()
    question = "2026年10月比较各款的下单笔数"

    plan = client.post("/api/queries/plan", headers=headers, json={"dataset_id": 1, "question": question})

    assert plan.status_code == 200, plan.text
    assert (plan.json()["source"], plan.json()["scope"], plan.json()["metric"]) == ("llm", "own", "orders")
    (_, _, payload), = requests
    sent = json.loads(payload["messages"][-1]["content"])
    assert set(sent) == {"question", "recognized", "metrics", "dimensions"}
    assert sent["question"] == question
    assert client.get("/api/queries", headers=headers).json()["total"] == 0
