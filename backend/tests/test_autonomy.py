"""Tests for company creation, skills distribution and the autopilot goal loop."""
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def head(company_id: int) -> dict:
    return {"X-Company-Id": str(company_id)}


def test_company_creation_builds_crew_and_first_goal():
    res = client.post(
        "/api/companies",
        json={
            "company_name": "Nimbus Media",
            "mission": "Grow small brands with AI-generated content",
            "first_goal": "Launch the first client campaign",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    cid = body["company"]["id"]

    assert body["company"]["name"] == "Nimbus Media"
    assert len(body["agents"]) >= 5
    assert all(a["skills"] for a in body["agents"])
    assert body["goal"]["title"] == "Launch the first client campaign"
    assert len(body["tasks"]) >= 3

    listed = client.get("/api/companies").json()
    nimbus = [c for c in listed if c["id"] == cid][0]
    assert nimbus["agents"] >= 5
    assert nimbus["active_goals"] == 1

    goal_tasks = client.get(f"/api/goals/{body['goal']['id']}/tasks", headers=head(cid)).json()
    assert len(goal_tasks) >= 3
    assert all(t["company_id"] == cid for t in goal_tasks)


def test_skills_crud_and_generation():
    agent = client.get("/api/agents").json()[1]
    created = client.post(
        f"/api/agents/{agent['id']}/skills",
        json={"name": "SEO writing", "description": "Rank content on search"},
    )
    assert created.status_code == 201

    generated = client.post(f"/api/agents/{agent['id']}/skills/generate")
    assert generated.status_code == 200
    assert len(generated.json()) >= 1

    skills = client.get(f"/api/agents/{agent['id']}/skills").json()
    assert any(s["name"] == "SEO writing" for s in skills)

    assert (
        client.delete(f"/api/agents/{agent['id']}/skills/{skills[0]['id']}").status_code
        == 204
    )


def test_skills_appear_in_run_log():
    agent = client.get("/api/agents").json()[1]
    client.post(f"/api/agents/{agent['id']}/skills",
                json={"name": "Deep research", "description": "Thorough source digging"})
    task = client.post(
        "/api/tasks", json={"title": "Skill-aware run", "agent_id": agent["id"]}
    ).json()
    run = client.post(f"/api/tasks/{task['id']}/run").json()
    deadline = time.time() + 10
    while time.time() < deadline:
        current = client.get(f"/api/runs/{run['id']}").json()
        if current["status"] != "running":
            break
        time.sleep(0.2)
    assert current["status"] == "completed"
    assert "Applying skills" in current["log"]


def test_autopilot_works_goal_to_completion():
    company = [c for c in client.get("/api/companies").json() if c["name"] == "Nimbus Media"][0]
    cid = company["id"]
    goal = client.get("/api/goals", headers=head(cid)).json()[0]
    assert goal["status"] == "active"

    deadline = time.time() + 90
    while time.time() < deadline:
        client.post("/api/goals/tick")
        current = next(
            g for g in client.get("/api/goals", headers=head(cid)).json() if g["id"] == goal["id"]
        )
        if current["status"] == "achieved":
            break
        time.sleep(0.3)

    assert current["status"] == "achieved"
    assert current["progress"] == 100
    assert current["cycle"] >= 2  # complementary planning rounds happened

    tasks = client.get(f"/api/goals/{goal['id']}/tasks", headers=head(cid)).json()
    assert len(tasks) >= 5  # initial + complementary
    assert all(t["status"] == "done" for t in tasks)

    events = client.get("/api/events?limit=100", headers=head(cid)).json()
    messages = " | ".join(e["message"] for e in events)
    assert "Autopilot started" in messages
    assert "Autopilot approved" in messages
    assert "complementary tasks" in messages
    assert "Goal achieved" in messages


def test_goal_pause_resume():
    created = client.post(
        "/api/goals", json={"title": "Secondary goal", "description": "test"}
    ).json()
    paused = client.post(f"/api/goals/{created['id']}/pause").json()
    assert paused["status"] == "paused"
    resumed = client.post(f"/api/goals/{created['id']}/resume").json()
    assert resumed["status"] == "active"
    client.post(f"/api/goals/{created['id']}/pause")  # keep autopilot quiet for other tests
