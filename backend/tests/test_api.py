"""API tests. Run with PAPERCREW_FAKE_LLM=1 and a temp DB (set in conftest)."""
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_seed_agents_present():
    res = client.get("/api/agents")
    assert res.status_code == 200
    assert len(res.json()) >= 3


def test_agent_crud():
    created = client.post(
        "/api/agents",
        json={"name": "Tester", "role": "QA", "goal": "test", "backstory": "b"},
    )
    assert created.status_code == 201
    agent_id = created.json()["id"]

    updated = client.put(
        f"/api/agents/{agent_id}",
        json={"name": "Tester2", "role": "QA", "goal": "test", "backstory": "b"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Tester2"

    assert client.delete(f"/api/agents/{agent_id}").status_code == 204
    assert client.delete(f"/api/agents/{agent_id}").status_code == 404


def test_task_crud_and_validation():
    bad = client.post("/api/tasks", json={"title": "x", "status": "bogus"})
    assert bad.status_code == 422

    bad_agent = client.post("/api/tasks", json={"title": "x", "agent_id": 99999})
    assert bad_agent.status_code == 422

    created = client.post("/api/tasks", json={"title": "Write report"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["status"] == "todo"

    moved = client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"})
    assert moved.status_code == 200
    assert moved.json()["status"] == "in_progress"

    assert client.delete(f"/api/tasks/{task_id}").status_code == 204


def test_run_requires_agent():
    task = client.post("/api/tasks", json={"title": "No agent"}).json()
    res = client.post(f"/api/tasks/{task['id']}/run")
    assert res.status_code == 422


def test_run_task_fake_llm_completes():
    agent = client.get("/api/agents").json()[0]
    task = client.post(
        "/api/tasks",
        json={"title": "Demo run", "description": "demo", "agent_id": agent["id"]},
    ).json()

    run = client.post(f"/api/tasks/{task['id']}/run")
    assert run.status_code == 202
    run_id = run.json()["id"]

    for _ in range(40):
        current = client.get(f"/api/runs/{run_id}").json()
        if current["status"] != "running":
            break
        time.sleep(0.25)

    assert current["status"] == "completed"
    assert "[demo output]" in current["output"]
    assert "[demo]" in current["log"]

    task_after = [
        t for t in client.get("/api/tasks").json() if t["id"] == task["id"]
    ][0]
    assert task_after["status"] == "review"


def test_settings_roundtrip():
    res = client.get("/api/settings")
    assert res.status_code == 200
    assert res.json()["fake_llm"] is True

    updated = client.put(
        "/api/settings",
        json={"openrouter_api_key": "sk-test", "default_model": "some/model:free"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["openrouter_api_key_set"] is True
    assert body["default_model"] == "some/model:free"
