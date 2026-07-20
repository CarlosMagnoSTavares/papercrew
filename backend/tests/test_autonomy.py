"""Tests for onboarding, skills distribution and the autopilot goal loop."""
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_onboarding_builds_company():
    res = client.post(
        "/api/company/onboard",
        json={
            "company_name": "Nimbus Media",
            "mission": "Grow small brands with AI-generated content",
            "first_goal": "Launch the first client campaign",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert len(body["agents"]) >= 5
    assert all(a["skills"] for a in body["agents"])
    assert body["goal"]["title"] == "Launch the first client campaign"
    assert len(body["tasks"]) >= 3

    company = client.get("/api/company").json()
    assert company["onboarded"] is True
    assert company["company_name"] == "Nimbus Media"

    goal_tasks = client.get(f"/api/goals/{body['goal']['id']}/tasks").json()
    assert len(goal_tasks) >= 3
    assert all(t["goal_id"] == body["goal"]["id"] for t in goal_tasks)

    again = client.post(
        "/api/company/onboard",
        json={"company_name": "X", "mission": "y", "first_goal": "z"},
    )
    assert again.status_code == 422


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
    goals = client.get("/api/goals").json()
    goal = next(g for g in goals if g["title"] == "Launch the first client campaign")
    assert goal["status"] == "active"

    deadline = time.time() + 90
    while time.time() < deadline:
        client.post("/api/goals/tick")
        current = next(
            g for g in client.get("/api/goals").json() if g["id"] == goal["id"]
        )
        if current["status"] == "achieved":
            break
        time.sleep(0.3)

    assert current["status"] == "achieved"
    assert current["progress"] == 100
    assert current["cycle"] >= 2  # complementary planning rounds happened

    tasks = client.get(f"/api/goals/{goal['id']}/tasks").json()
    assert len(tasks) >= 5  # initial + complementary
    assert all(t["status"] == "done" for t in tasks)

    events = client.get("/api/events?limit=100").json()
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
