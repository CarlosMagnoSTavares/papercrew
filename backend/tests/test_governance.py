"""Tests for hires, plans, inbox, work products, agent stats, budget, priority."""
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


def test_hire_request_lifecycle():
    created = client.post(
        "/api/hires",
        json={"name": "Pixel", "role": "Designer", "specialty": "design",
              "reason": "Need visual assets"},
    )
    assert created.status_code == 201
    hire_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    agents_before = len(client.get("/api/agents").json())
    approved = client.post(f"/api/hires/{hire_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["name"] == "Pixel"
    assert len(client.get("/api/agents").json()) == agents_before + 1

    again = client.post(f"/api/hires/{hire_id}/approve")
    assert again.status_code == 422

    rejected_req = client.post(
        "/api/hires", json={"name": "Nope", "role": "X"}
    ).json()
    assert client.post(f"/api/hires/{rejected_req['id']}/reject").json()["status"] == "rejected"


def test_plan_draft_and_convert():
    created = client.post(
        "/api/plans",
        json={"title": "Q3 Content Plan", "objective": "Ship a content engine",
              "draft_with_ceo": True},
    )
    assert created.status_code == 201
    plan = created.json()
    assert plan["status"] == "draft"
    assert "## Steps" in plan["content"]

    converted = client.post(f"/api/plans/{plan['id']}/convert")
    assert converted.status_code == 200
    tasks = converted.json()["tasks"]
    assert len(tasks) == 3

    assert client.post(f"/api/plans/{plan['id']}/convert").status_code == 422
    plans = client.get("/api/plans").json()
    assert [p for p in plans if p["id"] == plan["id"]][0]["status"] == "converted"


def test_task_priority_and_due_date():
    agent = client.get("/api/agents").json()[1]
    bad = client.post("/api/tasks", json={"title": "x", "priority": "asap"})
    assert bad.status_code == 422
    ok = client.post(
        "/api/tasks",
        json={"title": "Urgent thing", "agent_id": agent["id"],
              "priority": "urgent", "due_date": "2026-08-01"},
    )
    assert ok.status_code == 201
    assert ok.json()["priority"] == "urgent"
    patched = client.patch(f"/api/tasks/{ok.json()['id']}", json={"priority": "low"})
    assert patched.json()["priority"] == "low"


def test_inbox_aggregates_attention_items():
    client.post("/api/tasks", json={"title": "Orphan task"})
    client.post("/api/hires", json={"name": "Inbox Hire", "role": "Y"})
    inbox = client.get("/api/inbox").json()
    kinds = {item["kind"] for item in inbox}
    assert "unassigned" in kinds
    assert "hire" in kinds


def test_work_products_from_approved_tasks():
    agent = client.get("/api/agents").json()[1]
    task = client.post(
        "/api/tasks", json={"title": "Deliverable task", "agent_id": agent["id"]}
    ).json()
    run = client.post(f"/api/tasks/{task['id']}/run").json()
    wait_run(run["id"])
    client.post(f"/api/tasks/{task['id']}/approve")

    products = client.get("/api/work-products").json()
    match = [p for p in products if p["task_id"] == task["id"]]
    assert len(match) == 1
    assert match[0]["agent"] == agent["name"]
    assert match[0]["output"]


def test_agent_stats():
    agent = client.get("/api/agents").json()[1]
    stats = client.get(f"/api/agents/{agent['id']}/stats").json()
    assert stats["tasks_total"] >= 1
    assert stats["runs_total"] >= 1
    assert stats["tokens"] > 0
    assert client.get("/api/agents/99999/stats").status_code == 404


def test_budget_blocks_runs():
    from app.db import RunRow, SessionLocal

    company = client.get("/api/companies").json()[0]
    agent = client.get("/api/agents").json()[1]
    task = client.post(
        "/api/tasks", json={"title": "Blocked by budget", "agent_id": agent["id"]}
    ).json()

    db = SessionLocal()
    try:
        db.add(RunRow(task_id=task["id"], status="completed", cost=9.99))
        db.commit()
    finally:
        db.close()

    client.patch(f"/api/companies/{company['id']}", json={"monthly_budget": 5})
    blocked = client.post(f"/api/tasks/{task['id']}/run")
    assert blocked.status_code == 402
    assert "Budget exceeded" in blocked.json()["detail"]

    client.patch(f"/api/companies/{company['id']}", json={"monthly_budget": 0})
    allowed = client.post(f"/api/tasks/{task['id']}/run")
    assert allowed.status_code == 202
    wait_run(allowed.json()["id"])


def test_company_profile_roundtrip():
    company = client.get("/api/companies").json()[0]
    updated = client.patch(
        f"/api/companies/{company['id']}",
        json={"mission": "Ship useful AI work", "monthly_budget": 5},
    ).json()
    assert updated["mission"] == "Ship useful AI work"
    assert updated["monthly_budget"] == 5
    client.patch(f"/api/companies/{company['id']}", json={"monthly_budget": 0})
