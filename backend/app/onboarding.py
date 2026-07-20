"""Company onboarding: describe your company once — the CEO builds the team,
distributes skills, creates the first goal and plans the onboarding project.

Fake mode is deterministic; real mode asks the LLM for a tailored JSON plan.
"""
import json
import re

from .ceo import _llm_call, create_tasks_from_steps
from .crew_runner import fake_llm_enabled
from .db import AgentRow, GoalRow, SessionLocal, SettingRow, SkillRow, add_event
from .token_optimizer import TERSE_SUFFIX, compress_text

ONBOARD_PROMPT = (
    "You are founding an AI company. Company: {name}. Mission: {mission}. "
    "First goal: {goal}.\n"
    "Design the team. Reply ONLY with JSON: {{\"agents\": [{{\"name\", \"role\", \"goal\", "
    "\"backstory\", \"specialty\" (research|writing|engineering|analysis|marketing|general), "
    "\"skills\": [{{\"name\", \"description\"}}] (2-4 each)}}] (1 CEO first + 3-5 specialists), "
    "\"initial_tasks\": [{{\"title\", \"description\", \"specialty\"}}] (3-4 tasks toward the goal)}}"
    + TERSE_SUFFIX
)

FAKE_TEAM = [
    {
        "name": "Atlas", "role": "CEO / Orchestrator", "specialty": "general", "is_ceo": True,
        "goal": "Break down objectives, delegate work, review results and keep the company on target",
        "backstory": "Founder-mode operator that keeps the crew focused and shipping.",
        "skills": [
            {"name": "Strategic planning", "description": "Turn objectives into executable roadmaps"},
            {"name": "Delegation", "description": "Match work to the best-fit specialist"},
            {"name": "Quality review", "description": "Judge deliverables against the goal"},
        ],
    },
    {
        "name": "Nova", "role": "Researcher", "specialty": "research",
        "goal": "Gather accurate, well-sourced information for any topic",
        "backstory": "Curious analyst that digs deep and summarizes clearly.",
        "skills": [
            {"name": "Market research", "description": "Map competitors, audiences and trends"},
            {"name": "Source evaluation", "description": "Rank information by reliability"},
        ],
    },
    {
        "name": "Scribe", "role": "Writer", "specialty": "writing",
        "goal": "Turn research and ideas into polished, structured documents",
        "backstory": "Technical writer with a knack for clarity and concision.",
        "skills": [
            {"name": "Copywriting", "description": "Persuasive, audience-fit writing"},
            {"name": "Structured docs", "description": "Reports, guides and briefs that scan well"},
        ],
    },
    {
        "name": "Vector", "role": "Engineer", "specialty": "engineering",
        "goal": "Design and reason about technical solutions and automation",
        "backstory": "Pragmatic engineer that favors simple, working solutions.",
        "skills": [
            {"name": "Automation design", "description": "Spot and script repeatable work"},
            {"name": "Technical review", "description": "Evaluate feasibility and risks"},
        ],
    },
    {
        "name": "Prism", "role": "Analyst", "specialty": "analysis",
        "goal": "Review deliverables critically and measure progress toward goals",
        "backstory": "Detail-oriented reviewer with high standards.",
        "skills": [
            {"name": "KPI tracking", "description": "Define and measure success metrics"},
            {"name": "Critical review", "description": "Find gaps before they ship"},
        ],
    },
]


def _fake_company_plan(name: str, mission: str, goal: str) -> dict:
    topic = compress_text(goal or mission, 100)
    return {
        "agents": FAKE_TEAM,
        "initial_tasks": [
            {"title": f"Research: {topic}",
             "description": f"Map the landscape, audience and constraints for: {goal}. Company mission: {mission}",
             "specialty": "research"},
            {"title": f"Strategy: {topic}",
             "description": f"Define the approach and success metrics for: {goal}",
             "specialty": "analysis"},
            {"title": f"Produce: {topic}",
             "description": f"Create the first concrete deliverable toward: {goal}",
             "specialty": "writing"},
        ],
    }


def _llm_company_plan(name: str, mission: str, goal: str) -> dict:
    raw = _llm_call(
        ONBOARD_PROMPT.format(name=name, mission=mission, goal=goal), max_tokens=2000
    )
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise RuntimeError(f"CEO returned no JSON company plan: {raw:.300}")
    return json.loads(match.group(0))


def onboard_company(name: str, mission: str, goal_title: str) -> dict:
    """Create agents + skills + first goal + onboarding tasks. Idempotent guard
    lives in the router (rejects if already onboarded)."""
    plan = (
        _fake_company_plan(name, mission, goal_title)
        if fake_llm_enabled()
        else _llm_company_plan(name, mission, goal_title)
    )

    db = SessionLocal()
    try:
        hired = []
        for i, spec in enumerate(plan.get("agents", [])[:6]):
            agent = AgentRow(
                name=spec.get("name", f"Agent {i+1}")[:120],
                role=spec.get("role", "Specialist")[:200],
                goal=spec.get("goal", ""),
                backstory=spec.get("backstory", ""),
                specialty=spec.get("specialty", "general")[:120],
                is_ceo=1 if (spec.get("is_ceo") or i == 0) else 0,
            )
            db.add(agent)
            db.flush()
            skills = []
            for skill in spec.get("skills", [])[:5]:
                db.add(SkillRow(agent_id=agent.id, name=skill.get("name", "Skill")[:120],
                                description=skill.get("description", "")))
                skills.append(skill.get("name", "Skill"))
            hired.append({"id": agent.id, "name": agent.name, "role": agent.role,
                          "skills": skills})

        goal = GoalRow(title=goal_title[:200] or f"First milestone for {name}",
                       description=f"Mission: {mission}")
        db.add(goal)
        db.flush()

        created, _ = create_tasks_from_steps(db, plan.get("initial_tasks", []), priority="high")
        for task_info in created:
            from .db import TaskRow

            task = db.get(TaskRow, task_info["id"])
            if task is not None:
                task.goal_id = goal.id

        for key, value in (("company_name", name), ("company_mission", mission),
                           ("onboarded", "1")):
            row = db.get(SettingRow, key)
            if row is None:
                db.add(SettingRow(key=key, value=value))
            else:
                row.value = value

        add_event(db, "company",
                  f"Company '{name}' onboarded: {len(hired)} agents hired, "
                  f"goal '{goal.title}' created with {len(created)} tasks")
        db.commit()
        return {"agents": hired, "goal": {"id": goal.id, "title": goal.title},
                "tasks": created}
    finally:
        db.close()
