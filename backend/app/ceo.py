"""CEO brain: chat objectives → plans → delegated tasks, plus plan documents.

Fake mode is deterministic (demo/CI). Real mode asks the CEO agent via the
OpenRouter LLM. When a plan step needs a specialty no agent covers, the CEO
files a pending hire request instead of silently mis-assigning (governance).
"""
import json
import re

from sqlalchemy import select

from .crew_runner import DEFAULT_MODEL, fake_llm_enabled, get_setting
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

PLAN_PROMPT = (
    "You are the CEO of an AI company. Break this objective into 2-4 concrete, "
    "self-contained tasks. Reply ONLY with a JSON array of objects with keys "
    '"title", "description", "specialty" (one of: research, writing, engineering, '
    "analysis, general). Objective:\n{objective}" + TERSE_SUFFIX
)


def match_agent(db, specialty: str) -> tuple[AgentRow | None, bool]:
    """Best-fit worker for a specialty. Returns (agent, exact_match)."""
    agents = db.scalars(select(AgentRow).order_by(AgentRow.id)).all()
    workers = [a for a in agents if not a.is_ceo] or agents
    needle = (specialty or "general").lower()
    for agent in workers:
        haystack = f"{agent.specialty} {agent.role} {agent.goal}".lower()
        if needle in haystack:
            return agent, True
    return (workers[0] if workers else None), False


def _maybe_request_hire(db, specialty: str) -> bool:
    """File a pending hire request for an uncovered specialty (once)."""
    if not specialty or specialty == "general":
        return False
    existing = db.scalars(
        select(HireRequestRow).where(
            HireRequestRow.specialty == specialty, HireRequestRow.status == "pending"
        )
    ).first()
    if existing:
        return False
    db.add(
        HireRequestRow(
            name=f"New {specialty.title()} Specialist",
            role=f"{specialty.title()} Specialist",
            goal=f"Own all {specialty} work with high quality",
            specialty=specialty,
            reason=f"CEO: no current agent covers the '{specialty}' specialty.",
        )
    )
    add_event(db, "hire", f"CEO requested a hire for specialty '{specialty}'")
    return True


def _fake_steps(objective: str) -> list[dict]:
    topic = compress_text(objective, 120)
    return [
        {
            "title": f"Research: {topic}",
            "description": f"Gather key facts and constraints for: {objective}",
            "specialty": "research",
        },
        {
            "title": f"Execute: {topic}",
            "description": f"Produce the main deliverable for: {objective}",
            "specialty": "writing",
        },
        {
            "title": f"Review: {topic}",
            "description": f"Quality-check the deliverable for: {objective}",
            "specialty": "analysis",
        },
    ]


def _llm_call(prompt: str, max_tokens: int = 1024) -> str:
    from crewai import LLM

    db = SessionLocal()
    try:
        api_key = get_setting(db, "openrouter_api_key")
        model = get_setting(db, "default_model", DEFAULT_MODEL)
    finally:
        db.close()
    if not api_key:
        raise RuntimeError("No OpenRouter API key configured — add one in Settings.")
    llm = LLM(model=f"openrouter/{model}", api_key=api_key,
              base_url="https://openrouter.ai/api/v1", max_tokens=max_tokens)
    return str(llm.call(prompt))


def _llm_steps(objective: str) -> list[dict]:
    raw = _llm_call(PLAN_PROMPT.format(objective=objective))
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise RuntimeError(f"CEO returned no JSON plan: {raw:.300}")
    plan = json.loads(match.group(0))
    return [p for p in plan if isinstance(p, dict) and p.get("title")][:4]


def build_steps(objective: str) -> list[dict]:
    return _fake_steps(objective) if fake_llm_enabled() else _llm_steps(objective)


def create_tasks_from_steps(db, steps: list[dict], priority: str = "medium") -> tuple[list[dict], int]:
    """Create dependency-chained tasks; file hires for uncovered specialties."""
    created, hires = [], 0
    previous_id: int | None = None
    for step in steps:
        specialty = step.get("specialty", "")
        agent, exact = match_agent(db, specialty)
        if not exact and _maybe_request_hire(db, specialty):
            hires += 1
        task = TaskRow(
            title=step["title"][:200],
            description=step.get("description", ""),
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


def handle_message(message: str) -> dict:
    db = SessionLocal()
    try:
        db.add(ChatMessageRow(role="user", body=message))
        db.commit()
    finally:
        db.close()

    steps = build_steps(message)

    db = SessionLocal()
    try:
        created, hires = create_tasks_from_steps(db, steps)
        lines = [f"Plan created — {len(created)} tasks, chained by dependency:"]
        lines += [f"• #{t['id']} {t['title']} → {t['agent']}" for t in created]
        if hires:
            lines.append(f"Also filed {hires} hire request(s) for uncovered specialties — see Inbox.")
        reply = "\n".join(lines)
        db.add(ChatMessageRow(role="ceo", body=reply))
        add_event(db, "plan", f"CEO planned {len(created)} tasks from chat objective")
        db.commit()
        return {"reply": reply, "tasks": created}
    finally:
        db.close()


def draft_plan_content(title: str, objective: str) -> str:
    """Markdown plan document. Deterministic in fake mode, LLM otherwise."""
    if fake_llm_enabled():
        steps = _fake_steps(objective)
        lines = [f"# {title}", "", f"**Objective:** {objective}", "", "## Steps", ""]
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. **{step['title']}** ({step['specialty']})")
            lines.append(f"   {step['description']}")
        lines += ["", "## Risks", "- Scope creep — keep steps self-contained.",
                  "- Review quality — final step verifies the deliverable."]
        return "\n".join(lines)
    return _llm_call(
        f"Write a concise markdown execution plan titled '{title}' for this objective. "
        f"Sections: Objective, Steps (numbered, each with a specialty tag), Risks.\n"
        f"Objective: {objective}" + TERSE_SUFFIX,
        max_tokens=1500,
    )


def convert_plan(plan_id: int) -> list[dict]:
    """Turn an approved plan document into dependency-chained tasks."""
    db = SessionLocal()
    try:
        plan = db.get(PlanRow, plan_id)
        if plan is None:
            raise ValueError("Plan not found")
        steps = build_steps(plan.objective or plan.title)
        created, _hires = create_tasks_from_steps(db, steps)
        plan.status = "converted"
        add_event(db, "plan", f"Plan '{plan.title}' converted into {len(created)} tasks")
        db.commit()
        return created
    finally:
        db.close()
