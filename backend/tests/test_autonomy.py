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
    assert len(body["agents"]) >= 4
    assert all(a["skills"] for a in body["agents"])
    # the crew is designed for THIS business, not a fixed roster
    assert any(a["specialty"] == "marketing" for a in body["agents"])
    assert sum(1 for a in body["agents"] if a["role"].startswith("CEO")) == 1
    assert body["goal"]["title"] == "Launch the first client campaign"
    assert len(body["tasks"]) >= 3

    listed = client.get("/api/companies").json()
    nimbus = [c for c in listed if c["id"] == cid][0]
    assert nimbus["agents"] == len(body["agents"])
    assert nimbus["active_goals"] == 1

    goal_tasks = client.get(f"/api/goals/{body['goal']['id']}/tasks", headers=head(cid)).json()
    assert len(goal_tasks) >= 3
    assert all(t["company_id"] == cid for t in goal_tasks)


def test_crew_is_tailored_to_each_business():
    """Different missions and goals staff different functions."""
    finance = client.post(
        "/api/companies",
        json={
            "company_name": "Ledger Row",
            "mission": "We run subscription pricing and revenue operations for SaaS",
            "first_goal": "Rebuild the pricing model to lift revenue",
        },
    ).json()
    devtools = client.post(
        "/api/companies",
        json={
            "company_name": "Forge API",
            "mission": "We build developer tools and API documentation",
            "first_goal": "Ship the developer docs portal",
        },
    ).json()

    finance_specialties = {a["specialty"] for a in finance["agents"]}
    devtools_specialties = {a["specialty"] for a in devtools["agents"]}

    assert "finance" in finance_specialties
    assert "engineering" in devtools_specialties
    assert finance_specialties != devtools_specialties

    # tasks are delegated to agents that actually exist on that crew
    for company in (finance, devtools):
        names = {a["name"] for a in company["agents"]}
        assert all(t["agent"] in names for t in company["tasks"])


def test_company_creation_requires_an_api_key():
    from app.db import SessionLocal, SettingRow

    db = SessionLocal()
    try:
        row = db.get(SettingRow, "openrouter_api_key")
        saved = row.value
        row.value = ""
        db.commit()
    finally:
        db.close()

    try:
        blocked = client.post(
            "/api/companies",
            json={"company_name": "Keyless Co", "mission": "m", "first_goal": "g"},
        )
        assert blocked.status_code == 400
        assert "OpenRouter API key" in blocked.json()["detail"]
        assert all(c["name"] != "Keyless Co" for c in client.get("/api/companies").json())
    finally:
        db = SessionLocal()
        try:
            db.get(SettingRow, "openrouter_api_key").value = saved
            db.commit()
        finally:
            db.close()


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
    assert "[skills]" in current["log"]
    assert "Deep research" in current["log"]


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
