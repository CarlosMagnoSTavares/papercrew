"""CEO brain: chat objectives → plans → delegated tasks, plus plan documents.

All lookups are company-scoped: a CEO only sees and delegates to its own crew.
When a plan step needs a specialty no agent covers, the CEO files a pending
hire request instead of silently mis-assigning (governance).
"""
from sqlalchemy import select

from . import llm
from .db import (
    AgentRow,
    ChatMessageRow,
    HireRequestRow,
    PlanRow,
    SessionLocal,
    TaskRow,
    add_event,
)
from .token_optimizer import TERSE_SUFFIX, compress_text

PLAN_PROMPT = """You are the CEO of this company.

Company: {company}
Mission: {mission}
Crew available (specialty — role): {crew}

Break this objective into 2-4 concrete, self-contained tasks that this crew can
actually execute, in order. Assign each to the specialty best suited to it,
preferring specialties that already exist on the crew.

Objective: {objective}

Reply with ONLY a JSON array, no prose:
[{{"title": "...", "description": "...", "specialty": "..."}}]""" + TERSE_SUFFIX


def _company_context(db, company_id: int) -> tuple[str, str, str]:
    from .db import CompanyRow

    company = db.get(CompanyRow, company_id)
    agents = db.scalars(
        select(AgentRow).where(AgentRow.company_id == company_id).order_by(AgentRow.id)
    ).all()
    crew = ", ".join(f"{a.specialty} — {a.role}" for a in agents) or "none yet"
    return (
        company.name if company else "the company",
        company.mission if company else "",
        crew,
    )


def match_agent(db, specialty: str, company_id: int) -> tuple[AgentRow | None, bool]:
    """Best-fit worker inside this company. Returns (agent, exact_match)."""
    agents = db.scalars(
        select(AgentRow).where(AgentRow.company_id == company_id).order_by(AgentRow.id)
    ).all()
    workers = [a for a in agents if not a.is_ceo] or agents
    needle = (specialty or "general").lower().strip()
    if needle:
        for agent in workers:
            if needle == agent.specialty.lower():
                return agent, True
        for agent in workers:
            haystack = f"{agent.specialty} {agent.role} {agent.goal}".lower()
            if needle in haystack or any(
                word and word in haystack for word in needle.split("-")
            ):
                return agent, True
    return (workers[0] if workers else None), False


def _maybe_request_hire(db, specialty: str, company_id: int) -> bool:
    """File a pending hire request for an uncovered specialty (once per company)."""
    if not specialty or specialty == "general":
        return False
    existing = db.scalars(
        select(HireRequestRow).where(
            HireRequestRow.company_id == company_id,
            HireRequestRow.specialty == specialty,
            HireRequestRow.status == "pending",
        )
    ).first()
    if existing:
        return False
    db.add(
        HireRequestRow(
            company_id=company_id,
            name=f"New {specialty.title()} Specialist",
            role=f"{specialty.title()} Specialist",
            goal=f"Own all {specialty} work with high quality",
            specialty=specialty,
            reason=f"CEO: no current agent covers the '{specialty}' specialty.",
        )
    )
    add_event(db, "hire", f"CEO requested a hire for specialty '{specialty}'", company_id)
    return True


def build_steps(objective: str, company_id: int = 0) -> list[dict]:
    db = SessionLocal()
    try:
        company, mission, crew = _company_context(db, company_id)
    finally:
        db.close()
    steps = llm.call_json(
        PLAN_PROMPT.format(
            company=company, mission=mission, crew=crew, objective=objective
        ),
        max_tokens=1200,
        company_id=company_id,
        as_list=True,
    )
    if not isinstance(steps, list):
        raise llm.LLMError("The CEO did not return a task list.")
    return [s for s in steps if isinstance(s, dict) and s.get("title")][:4]


def create_tasks_from_steps(
    db, steps: list[dict], company_id: int, priority: str = "medium"
) -> tuple[list[dict], int]:
    """Create dependency-chained tasks; file hires for uncovered specialties."""
    created, hires = [], 0
    previous_id: int | None = None
    for step in steps:
        specialty = str(step.get("specialty", "")).lower().strip()
        agent, exact = match_agent(db, specialty, company_id)
        if not exact and _maybe_request_hire(db, specialty, company_id):
            hires += 1
        task = TaskRow(
            company_id=company_id,
            title=str(step["title"])[:200],
            description=str(step.get("description", "")),
            agent_id=agent.id if agent else None,
            depends_on=str(previous_id) if previous_id else "",
            priority=priority,
        )
        db.add(task)
        db.flush()
        previous_id = task.id
        created.append(
            {"id": task.id, "title": task.title, "agent": agent.name if agent else "unassigned"}
        )
    return created, hires


def handle_message(message: str, company_id: int) -> dict:
    db = SessionLocal()
    try:
        db.add(ChatMessageRow(company_id=company_id, role="user", body=message))
        db.commit()
    finally:
        db.close()

    steps = build_steps(message, company_id)

    db = SessionLocal()
    try:
        created, hires = create_tasks_from_steps(db, steps, company_id)
        lines = [f"Plan created — {len(created)} tasks, chained by dependency:"]
        lines += [f"• #{t['id']} {t['title']} → {t['agent']}" for t in created]
        if hires:
            lines.append(f"Also filed {hires} hire request(s) for uncovered specialties — see Inbox.")
        reply = "\n".join(lines)
        db.add(ChatMessageRow(company_id=company_id, role="ceo", body=reply))
        add_event(db, "plan", f"CEO planned {len(created)} tasks from chat objective", company_id)
        db.commit()
        return {"reply": reply, "tasks": created}
    finally:
        db.close()


def draft_plan_content(title: str, objective: str, company_id: int = 0) -> str:
    """Markdown plan document written by the CEO."""
    db = SessionLocal()
    try:
        company, mission, crew = _company_context(db, company_id)
    finally:
        db.close()
    return llm.call_text(
        f"You are the CEO of {company}. Mission: {mission}. Crew: {crew}.\n"
        f"Write a concise markdown execution plan titled '{title}'. "
        f"Sections: Objective, Steps (numbered, each tagged with the specialty that owns it), "
        f"Risks.\nObjective: {objective}" + TERSE_SUFFIX,
        max_tokens=1500,
        company_id=company_id,
    )


def convert_plan(plan_id: int) -> list[dict]:
    """Turn an approved plan document into dependency-chained tasks."""
    db = SessionLocal()
    try:
        plan = db.get(PlanRow, plan_id)
        if plan is None:
            raise ValueError("Plan not found")
        company_id = plan.company_id
        objective = plan.objective or plan.title
    finally:
        db.close()

    steps = build_steps(objective, company_id)

    db = SessionLocal()
    try:
        plan = db.get(PlanRow, plan_id)
        created, _hires = create_tasks_from_steps(db, steps, company_id)
        plan.status = "converted"
        add_event(db, "plan", f"Plan '{plan.title}' converted into {len(created)} tasks",
                  company_id)
        db.commit()
        return created
    finally:
        db.close()


def summarize_for_goal(goal_title: str, done_titles: list[str], company_id: int) -> tuple[bool, list[dict]]:
    """Judge whether a goal is met and propose the next tasks if not."""
    done = "\n".join(f"- {t}" for t in done_titles) or "- (nothing yet)"
    data = llm.call_json(
        f"Goal: {goal_title}\nCompleted tasks:\n{done}\n\n"
        "Is this goal fully achieved? If not, propose up to 3 concrete follow-up tasks "
        "that would finish it. Reply ONLY JSON: "
        '{"achieved": true|false, "next_tasks": [{"title": "...", "description": "...", '
        '"specialty": "..."}]}' + TERSE_SUFFIX,
        max_tokens=900,
        company_id=company_id,
    )
    if not isinstance(data, dict):
        return True, []
    next_tasks = [
        t for t in (data.get("next_tasks") or [])
        if isinstance(t, dict) and t.get("title")
    ][:3]
    return bool(data.get("achieved")), next_tasks


def compress(text: str, budget: int) -> str:
    return compress_text(text, budget)
