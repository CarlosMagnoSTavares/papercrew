"""Several companies coexist: isolated data, parallel autopilots, archiving."""
import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def head(company_id: int) -> dict:
    return {"X-Company-Id": str(company_id)}


def make_company(name: str, goal: str) -> dict:
    res = client.post(
        "/api/companies",
        json={"company_name": name, "mission": f"{name} mission", "first_goal": goal},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_two_companies_are_isolated():
    a = make_company("Alpha Labs", "Ship the Alpha launch")
    b = make_company("Beta Studio", "Ship the Beta launch")
    a_id, b_id = a["company"]["id"], b["company"]["id"]
    assert a_id != b_id

    a_agents = client.get("/api/agents", headers=head(a_id)).json()
    b_agents = client.get("/api/agents", headers=head(b_id)).json()
    assert {ag["id"] for ag in a_agents}.isdisjoint({ag["id"] for ag in b_agents})
    assert all(ag["company_id"] == a_id for ag in a_agents)

    a_tasks = client.get("/api/tasks", headers=head(a_id)).json()
    b_tasks = client.get("/api/tasks", headers=head(b_id)).json()
    assert all("Alpha" in t["title"] for t in a_tasks)
    assert all("Beta" in t["title"] for t in b_tasks)

    a_goals = client.get("/api/goals", headers=head(a_id)).json()
    assert len(a_goals) == 1
    assert a_goals[0]["title"] == "Ship the Alpha launch"

    # chat, events and plans stay separate too
    client.post("/api/chat", json={"message": "Alpha objective"}, headers=head(a_id))
    assert len(client.get("/api/chat", headers=head(a_id)).json()) == 2
    assert client.get("/api/chat", headers=head(b_id)).json() == []
    a_events = client.get("/api/events", headers=head(a_id)).json()
    assert all("Beta" not in e["message"] for e in a_events)


def test_cross_company_access_is_blocked():
    companies = client.get("/api/companies").json()
    alpha = [c for c in companies if c["name"] == "Alpha Labs"][0]
    beta = [c for c in companies if c["name"] == "Beta Studio"][0]

    beta_task = client.get("/api/tasks", headers=head(beta["id"])).json()[0]
    # reading Beta's task while acting as Alpha must 404, not leak
    assert client.get(
        f"/api/tasks/{beta_task['id']}/runs", headers=head(alpha["id"])
    ).status_code == 404
    assert client.post(
        f"/api/tasks/{beta_task['id']}/approve", headers=head(alpha["id"])
    ).status_code == 404

    beta_agent = client.get("/api/agents", headers=head(beta["id"])).json()[0]
    assert client.get(
        f"/api/agents/{beta_agent['id']}/stats", headers=head(alpha["id"])
    ).status_code == 404
    # and Alpha cannot assign Beta's agent to its own task
    rejected = client.post(
        "/api/tasks",
        json={"title": "Cross-company", "agent_id": beta_agent["id"]},
        headers=head(alpha["id"]),
    )
    assert rejected.status_code == 422

    assert client.get("/api/agents", headers={"X-Company-Id": "99999"}).status_code == 404


def test_autopilots_run_in_parallel():
    companies = client.get("/api/companies").json()
    alpha = [c for c in companies if c["name"] == "Alpha Labs"][0]["id"]
    beta = [c for c in companies if c["name"] == "Beta Studio"][0]["id"]

    def goal_of(cid: int) -> dict:
        return client.get("/api/goals", headers=head(cid)).json()[0]

    deadline = time.time() + 120
    while time.time() < deadline:
        client.post("/api/goals/tick")  # one tick serves every company
        if (
            goal_of(alpha)["status"] == "achieved"
            and goal_of(beta)["status"] == "achieved"
        ):
            break
        time.sleep(0.2)

    assert goal_of(alpha)["status"] == "achieved"
    assert goal_of(beta)["status"] == "achieved"

    # each company only ever worked its own tasks
    for cid, marker in ((alpha, "Alpha"), (beta, "Beta")):
        runs = client.get("/api/runs", headers=head(cid)).json()
        assert runs
        tasks = {t["id"]: t for t in client.get("/api/tasks", headers=head(cid)).json()}
        assert all(r["task_id"] in tasks for r in runs)
        assert all(marker in t["title"] for t in tasks.values())

    alpha_stats = client.get("/api/stats", headers=head(alpha)).json()
    beta_stats = client.get("/api/stats", headers=head(beta)).json()
    assert alpha_stats["total_runs"] > 0
    assert beta_stats["total_runs"] > 0


def test_archive_stops_a_company_and_restore_brings_it_back():
    gamma = make_company("Gamma Corp", "Ship the Gamma launch")
    cid = gamma["company"]["id"]

    archived = client.post(f"/api/companies/{cid}/archive").json()
    assert archived["archived"] is True
    assert client.get("/api/goals", headers=head(cid)).status_code == 404
    assert all(c["id"] != cid for c in client.get("/api/companies").json())
    assert any(
        c["id"] == cid for c in client.get("/api/companies?include_archived=true").json()
    )

    from app.autopilot import autopilot_tick
    from app.db import GoalRow, SessionLocal

    autopilot_tick()
    db = SessionLocal()
    try:
        goals = db.query(GoalRow).filter(GoalRow.company_id == cid).all()
        assert all(g.status == "paused" for g in goals)
    finally:
        db.close()

    restored = client.post(f"/api/companies/{cid}/restore").json()
    assert restored["archived"] is False
    assert client.get("/api/goals", headers=head(cid)).status_code == 200


def test_company_summary_counts():
    companies = client.get("/api/companies").json()
    alpha = [c for c in companies if c["name"] == "Alpha Labs"][0]
    beta = [c for c in companies if c["name"] == "Beta Studio"][0]

    assert alpha["agents"] >= 5
    assert alpha["active_goals"] == 0  # its goal was achieved
    assert alpha["total_cost"] == 0.0  # free model in demo mode

    # Alpha's extra open tasks came from its CEO chat (outside any goal, so the
    # autopilot left them alone); Beta never chatted and has none.
    alpha_tasks = client.get("/api/tasks", headers=head(alpha["id"])).json()
    assert alpha["open_tasks"] == sum(1 for t in alpha_tasks if t["status"] != "done")
    assert beta["open_tasks"] == 0
