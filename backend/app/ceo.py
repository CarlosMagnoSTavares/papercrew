"""CEO chat: turns an objective into a plan of assigned tasks (Paperclip-style).

Fake mode produces a deterministic 3-step plan. Real mode asks the CEO agent
(via CrewAI) for a JSON plan, then creates and delegates the tasks.
"""
import json
import re

from sqlalchemy import select

from .crew_runner import DEFAULT_MODEL, fake_llm_enabled, get_setting
from .db import AgentRow, ChatMessageRow, SessionLocal, TaskRow, add_event
from .token_optimizer import TERSE_SUFFIX, compress_text

PLAN_PROMPT = (
    "You are the CEO of an AI company. Break this objective into 2-4 concrete, "
    "self-contained tasks. Reply ONLY with a JSON array of objects with keys "
    '"title", "description", "specialty" (one of: research, writing, engineering, '
    "analysis, general). Objective:\n{objective}" + TERSE_SUFFIX
)


def _match_agent(db, specialty: str) -> AgentRow | None:
    agents = db.scalars(select(AgentRow).order_by(AgentRow.id)).all()
    workers = [a for a in agents if not a.is_ceo] or agents
    needle = (specialty or "general").lower()
    for agent in workers:
        haystack = f"{agent.specialty} {agent.role} {agent.goal}".lower()
        if needle in haystack:
            return agent
    return workers[0] if workers else None


def _fake_plan(objective: str) -> list[dict]:
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


def _llm_plan(objective: str) -> list[dict]:
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
              base_url="https://openrouter.ai/api/v1", max_tokens=1024)
    raw = llm.call(PLAN_PROMPT.format(objective=objective))
    match = re.search(r"\[.*\]", str(raw), re.DOTALL)
    if not match:
        raise RuntimeError(f"CEO returned no JSON plan: {raw!s:.300}")
    plan = json.loads(match.group(0))
    return [p for p in plan if isinstance(p, dict) and p.get("title")][:4]


def handle_message(message: str) -> dict:
    """Persist chat, build plan, create tasks with dependency chain, reply."""
    db = SessionLocal()
    try:
        db.add(ChatMessageRow(role="user", body=message))
        db.commit()
    finally:
        db.close()

    plan = _fake_plan(message) if fake_llm_enabled() else _llm_plan(message)

    db = SessionLocal()
    try:
        created = []
        previous_id: int | None = None
        for step in plan:
            agent = _match_agent(db, step.get("specialty", ""))
            task = TaskRow(
                title=step["title"][:200],
                description=step.get("description", ""),
                agent_id=agent.id if agent else None,
                depends_on=str(previous_id) if previous_id else "",
            )
            db.add(task)
            db.flush()
            previous_id = task.id
            created.append(
                {"id": task.id, "title": task.title,
                 "agent": agent.name if agent else "unassigned"}
            )
        lines = [f"Plan created — {len(created)} tasks, chained by dependency:"]
        lines += [f"• #{t['id']} {t['title']} → {t['agent']}" for t in created]
        reply = "\n".join(lines)
        db.add(ChatMessageRow(role="ceo", body=reply))
        add_event(db, "plan", f"CEO planned {len(created)} tasks from chat objective")
        db.commit()
        return {"reply": reply, "tasks": created}
    finally:
        db.close()
