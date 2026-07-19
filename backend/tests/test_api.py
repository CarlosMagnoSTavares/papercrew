"""API tests. Fake LLM + temp DB + scheduler off (set in conftest)."""
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def wait_run(run_id: int, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.2)
    return run


def make_task(**overrides) -> dict:
    agent = client.get("/api/agents").json()[1]  # non-CEO worker
    payload = {"title": "Test task", "agent_id": agent["id"], **overrides}
    res = client.post("/api/tasks", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_seed_agents_with_ceo():
    agents = client.get("/api/agents").json()
    assert len(agents) >= 5
    assert any(a["is_ceo"] for a in agents)


def test_agent_crud():
    created = client.post(
        "/api/agents",
        json={"name": "Tester", "role": "QA", "specialty": "analysis"},
    )
    assert created.status_code == 201
    agent_id = created.json()["id"]
    updated = client.put(
        f"/api/agents/{agent_id}", json={"name": "Tester2", "role": "QA"}
    )
    assert updated.json()["name"] == "Tester2"
    assert client.delete(f"/api/agents/{agent_id}").status_code == 204


def test_task_validation():
    assert client.post("/api/tasks", json={"title": "x", "status": "bogus"}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "agent_id": 9999}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "crew_mode": "nope"}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "depends_on": "9999"}).status_code == 422


def test_run_completes_with_metrics():
    task = make_task(title="Metrics run", description="do something")
    run = client.post(f"/api/tasks/{task['id']}/run")
    assert run.status_code == 202
    finished = wait_run(run.json()["id"])
    assert finished["status"] == "completed"
    assert finished["prompt_tokens"] > 0
    assert finished["completion_tokens"] > 0


def test_dependency_blocking_and_context():
    dep = make_task(title="Dep task", description="produce data")
    dependent = make_task(title="Dependent", depends_on=str(dep["id"]))

    blocked = client.post(f"/api/tasks/{dependent['id']}/run")
    assert blocked.status_code == 422
    assert "dependencies" in blocked.json()["detail"]

    run = client.post(f"/api/tasks/{dep['id']}/run").json()
    assert wait_run(run["id"])["status"] == "completed"
    client.post(f"/api/tasks/{dep['id']}/approve")

    run2 = client.post(f"/api/tasks/{dependent['id']}/run")
    assert run2.status_code == 202
    assert wait_run(run2.json()["id"])["status"] == "completed"


def test_approve_and_reject_flow():
    task = make_task(title="Review me")
    run = client.post(f"/api/tasks/{task['id']}/run").json()
    wait_run(run["id"])

    rejected = client.post(
        f"/api/tasks/{task['id']}/reject", json={"feedback": "Too short", "rerun": True}
    )
    assert rejected.status_code == 200
    assert rejected.json()["feedback"] == "Too short"
    runs = client.get(f"/api/tasks/{task['id']}/runs").json()
    assert len(runs) >= 2
    wait_run(runs[0]["id"])

    approved = client.post(f"/api/tasks/{task['id']}/approve").json()
    assert approved["status"] == "done"
    assert approved["feedback"] == ""

    comments = client.get(f"/api/tasks/{task['id']}/comments").json()
    bodies = [c["body"] for c in comments]
    assert any("Changes requested" in b for b in bodies)
    assert any("Approved" in b for b in bodies)


def test_comments_crud():
    task = make_task(title="Commented")
    created = client.post(
        f"/api/tasks/{task['id']}/comments", json={"body": "Looks good", "author": "You"}
    )
    assert created.status_code == 201
    assert client.get(f"/api/tasks/{task['id']}/comments").json()[-1]["body"] == "Looks good"


def test_chat_creates_dependency_chained_plan():
    res = client.post("/api/chat", json={"message": "Launch a newsletter about AI agents"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["tasks"]) == 3
    task_ids = [t["id"] for t in body["tasks"]]
    all_tasks = {t["id"]: t for t in client.get("/api/tasks").json()}
    assert all_tasks[task_ids[1]]["depends_on"] == str(task_ids[0])
    assert all_tasks[task_ids[2]]["depends_on"] == str(task_ids[1])
    history = client.get("/api/chat").json()
    assert history[-1]["role"] == "ceo"


def test_routines_crud_and_fire():
    from app.scheduler import fire_due_routines

    agent = client.get("/api/agents").json()[1]
    created = client.post(
        "/api/routines",
        json={
            "title": "Daily digest",
            "description": "Summarize activity",
            "agent_id": agent["id"],
            "interval_minutes": 60,
            "auto_run": False,
        },
    )
    assert created.status_code == 201

    fired = fire_due_routines()
    assert fired >= 1
    titles = [t["title"] for t in client.get("/api/tasks").json()]
    assert any(t.startswith("[routine] Daily digest") for t in titles)

    routine = client.get("/api/routines").json()[-1]
    assert client.delete(f"/api/routines/{routine['id']}").status_code == 204


def test_events_and_stats():
    events = client.get("/api/events").json()
    assert len(events) > 0
    stats = client.get("/api/stats").json()
    assert stats["total_runs"] > 0
    assert stats["prompt_tokens"] > 0


def test_settings_roundtrip():
    updated = client.put(
        "/api/settings",
        json={
            "openrouter_api_key": "sk-test",
            "default_model": "some/model:free",
            "company_name": "Acme AI",
        },
    )
    body = updated.json()
    assert body["openrouter_api_key_set"] is True
    assert body["default_model"] == "some/model:free"
    assert body["company_name"] == "Acme AI"
    assert body["fake_llm"] is True
