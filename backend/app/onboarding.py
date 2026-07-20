"""Company creation: the CEO designs a crew that fits *this* business.

There is no canned roster. The model reads the mission and first goal and
staffs the functions that company actually needs — a marketing shop gets
marketing roles, a goal about revenue pulls in a finance role, a dev-tools
company gets engineering and docs. Skills are generated per agent for the
same reason: they describe what that specific role must be good at.
"""
from . import llm
from .ceo import create_tasks_from_steps
from .db import AgentRow, CompanyRow, GoalRow, SessionLocal, SkillRow, TaskRow, add_event

TEAM_PROMPT = """You are founding an AI-run company and must staff it.

Company name: {name}
What it does: {mission}
First goal: {goal}

Design the smallest crew that can actually deliver this company's work and reach
that first goal. Think about which business functions this specific company
needs — not a generic template.

Rules:
- Exactly one CEO/orchestrator first, then 3 to 5 specialists.
- Derive every specialist from THIS company's industry, mission and first goal.
  A marketing company needs marketing roles; a goal about revenue, pricing or
  fundraising needs a finance role; a product company needs product/engineering;
  content work needs writing; anything customer-facing may need sales or support.
- Cover the first goal end to end: whoever must research, produce, verify and
  measure it should exist on this crew.
- "specialty" is one lowercase word or hyphenated phrase describing the function
  (examples: marketing, finance, engineering, research, content, design, sales,
  legal, operations, data-analysis). Use what fits this company.
- Give each agent 2-4 skills that are concrete and specific to their role.
- Names are short human first names or codenames. Do not reuse generic examples.

Keep it compact so the JSON is complete and valid:
- "goal" and "backstory": ONE short sentence each, under 120 characters.
- "description" fields: one short sentence.
- Never truncate: finish the JSON.

Reply with ONLY this JSON, no prose:
{{"agents": [{{"name": "...", "role": "...", "goal": "...", "backstory": "...",
"specialty": "...", "skills": [{{"name": "...", "description": "..."}}]}}],
"initial_tasks": [{{"title": "...", "description": "...", "specialty": "..."}}]}}

initial_tasks: 3 or 4 concrete first steps toward the goal, each assigned to a
specialty that exists on the crew above. Write everything in the same language
as the mission above."""


def _clean_agents(raw: list) -> list[dict]:
    agents = []
    for i, spec in enumerate(raw[:6]):
        if not isinstance(spec, dict) or not spec.get("role"):
            continue
        skills = [
            {"name": str(s.get("name", ""))[:120], "description": str(s.get("description", ""))}
            for s in spec.get("skills", [])[:5]
            if isinstance(s, dict) and s.get("name")
        ]
        agents.append(
            {
                "name": str(spec.get("name") or f"Agent {i + 1}")[:120],
                "role": str(spec["role"])[:200],
                "goal": str(spec.get("goal", "")),
                "backstory": str(spec.get("backstory", "")),
                "specialty": str(spec.get("specialty", "general")).lower()[:120],
                "is_ceo": bool(spec.get("is_ceo")) or i == 0,
                "skills": skills,
            }
        )
    return agents


def design_company(name: str, mission: str, goal: str) -> dict:
    """Ask the CEO model for a crew and first tasks tailored to this company.

    Chatty models sometimes overrun the token budget mid-JSON; one retry with a
    harder brevity instruction recovers that without bothering the user.
    """
    prompt = TEAM_PROMPT.format(name=name, mission=mission, goal=goal)
    try:
        plan = llm.call_json(prompt, max_tokens=4000)
    except llm.LLMError:
        plan = llm.call_json(
            prompt + "\n\nBe extremely terse: 4 agents maximum, 2 skills each, "
            "every sentence under 80 characters. The JSON MUST be complete.",
            max_tokens=4000,
        )
    agents = _clean_agents(plan.get("agents", []) if isinstance(plan, dict) else [])
    if len(agents) < 2:
        raise llm.LLMError("The model did not return a usable crew — try again.")
    tasks = [
        t for t in (plan.get("initial_tasks") or [])
        if isinstance(t, dict) and t.get("title")
    ][:4]
    return {"agents": agents, "initial_tasks": tasks}


def create_company(name: str, mission: str, goal_title: str) -> dict:
    """Create a company with its tailored crew, skills, first goal and tasks."""
    llm.require_api_key()
    plan = design_company(name, mission, goal_title)

    db = SessionLocal()
    try:
        company = CompanyRow(name=name[:120], mission=mission)
        db.add(company)
        db.flush()

        hired = []
        for spec in plan["agents"]:
            agent = AgentRow(
                company_id=company.id,
                name=spec["name"],
                role=spec["role"],
                goal=spec["goal"],
                backstory=spec["backstory"],
                specialty=spec["specialty"],
                is_ceo=1 if spec["is_ceo"] else 0,
            )
            db.add(agent)
            db.flush()
            for skill in spec["skills"]:
                db.add(
                    SkillRow(
                        agent_id=agent.id, name=skill["name"], description=skill["description"]
                    )
                )
            hired.append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "specialty": agent.specialty,
                    "skills": [s["name"] for s in spec["skills"]],
                }
            )

        goal = GoalRow(
            company_id=company.id,
            title=goal_title[:200],
            description=f"Mission: {mission}",
        )
        db.add(goal)
        db.flush()

        created, _ = create_tasks_from_steps(
            db, plan["initial_tasks"], company.id, priority="high"
        )
        for task_info in created:
            task = db.get(TaskRow, task_info["id"])
            if task is not None:
                task.goal_id = goal.id

        add_event(
            db,
            "company",
            f"Company '{name}' created: {len(hired)} agents hired "
            f"({', '.join(a['specialty'] for a in hired)}), "
            f"goal '{goal.title}' planned with {len(created)} tasks",
            company.id,
        )
        db.commit()
        return {
            "company": {"id": company.id, "name": company.name, "mission": company.mission},
            "agents": hired,
            "goal": {"id": goal.id, "title": goal.title},
            "tasks": created,
        }
    finally:
        db.close()
