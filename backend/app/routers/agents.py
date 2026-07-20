from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import AgentRow, RunRow, SkillRow, TaskRow, add_event, get_db
from ..deps import current_company_id, require_company_id
from ..schemas import AgentIn, AgentOut, AgentStatsOut, SkillIn, SkillOut

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _scoped(db: Session, agent_id: int, company_id: int) -> AgentRow:
    row = db.get(AgentRow, agent_id)
    if row is None or row.company_id != company_id:
        raise HTTPException(404, "Agent not found")
    return row


@router.get("", response_model=list[AgentOut])
def list_agents(
    db: Session = Depends(get_db), company_id: int = Depends(current_company_id)
):
    return db.scalars(
        select(AgentRow).where(AgentRow.company_id == company_id).order_by(AgentRow.id)
    ).all()


@router.post("", response_model=AgentOut, status_code=201)
def create_agent(
    payload: AgentIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(require_company_id),
):
    row = AgentRow(company_id=company_id, **payload.model_dump())
    db.add(row)
    db.commit()
    return row


@router.put("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: int,
    payload: AgentIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, agent_id, company_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return row


@router.get("/{agent_id}/stats", response_model=AgentStatsOut)
def agent_stats(
    agent_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    _scoped(db, agent_id, company_id)
    tasks_total = db.scalar(
        select(func.count(TaskRow.id)).where(TaskRow.agent_id == agent_id)
    )
    tasks_done = db.scalar(
        select(func.count(TaskRow.id)).where(
            TaskRow.agent_id == agent_id, TaskRow.status == "done"
        )
    )
    run_row = db.execute(
        select(
            func.count(RunRow.id),
            func.coalesce(func.sum(RunRow.prompt_tokens + RunRow.completion_tokens), 0),
            func.coalesce(func.sum(RunRow.cost), 0.0),
        )
        .join(TaskRow, TaskRow.id == RunRow.task_id)
        .where(TaskRow.agent_id == agent_id)
    ).one()
    return AgentStatsOut(
        agent_id=agent_id,
        tasks_total=tasks_total or 0,
        tasks_done=tasks_done or 0,
        runs_total=run_row[0],
        tokens=run_row[1],
        cost=round(run_row[2], 6),
    )


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, agent_id, company_id)
    for skill in db.scalars(select(SkillRow).where(SkillRow.agent_id == agent_id)):
        db.delete(skill)
    db.delete(row)
    db.commit()


@router.get("/{agent_id}/skills", response_model=list[SkillOut])
def list_skills(
    agent_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    _scoped(db, agent_id, company_id)
    return db.scalars(
        select(SkillRow).where(SkillRow.agent_id == agent_id).order_by(SkillRow.id)
    ).all()


@router.post("/{agent_id}/skills", response_model=SkillOut, status_code=201)
def add_skill(
    agent_id: int,
    payload: SkillIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    _scoped(db, agent_id, company_id)
    row = SkillRow(agent_id=agent_id, **payload.model_dump())
    db.add(row)
    db.commit()
    return row


@router.delete("/{agent_id}/skills/{skill_id}", status_code=204)
def delete_skill(
    agent_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    _scoped(db, agent_id, company_id)
    row = db.get(SkillRow, skill_id)
    if row is None or row.agent_id != agent_id:
        raise HTTPException(404, "Skill not found")
    db.delete(row)
    db.commit()


@router.post("/{agent_id}/skills/generate", response_model=list[SkillOut])
def generate_skills(
    agent_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    """CEO distributes skills that fit this agent's role and specialty."""
    from .. import llm

    agent = _scoped(db, agent_id, company_id)
    existing = {
        s.name.lower()
        for s in db.scalars(select(SkillRow).where(SkillRow.agent_id == agent_id))
    }

    try:
        candidates = llm.call_json(
            f"Agent role: {agent.role}. Specialty: {agent.specialty}. Goal: {agent.goal}.\n"
            f"Already has: {', '.join(existing) or 'nothing'}.\n"
            "Propose 3 concrete new skills this specific role needs. "
            'Reply ONLY JSON: [{"name": "...", "description": "..."}]',
            max_tokens=600,
            company_id=company_id,
            as_list=True,
        )
    except llm.LLMNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    if not isinstance(candidates, list):
        raise HTTPException(502, "The CEO did not return a skill list")

    created = []
    for skill in candidates[:5]:
        if not isinstance(skill, dict) or not skill.get("name"):
            continue
        if str(skill["name"]).lower() in existing:
            continue
        row = SkillRow(agent_id=agent_id, name=str(skill["name"])[:120],
                       description=str(skill.get("description", "")))
        db.add(row)
        created.append(row)
    add_event(db, "skill", f"Skills distributed to {agent.name}: "
              f"{', '.join(s.name for s in created) or 'none new'}", company_id)
    db.commit()
    return created
