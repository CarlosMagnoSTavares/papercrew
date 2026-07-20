from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import AgentRow, RunRow, TaskRow, get_db
from ..schemas import AgentIn, AgentOut, AgentStatsOut

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.scalars(select(AgentRow).order_by(AgentRow.id)).all()


@router.post("", response_model=AgentOut, status_code=201)
def create_agent(payload: AgentIn, db: Session = Depends(get_db)):
    row = AgentRow(**payload.model_dump())
    db.add(row)
    db.commit()
    return row


@router.put("/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: int, payload: AgentIn, db: Session = Depends(get_db)):
    row = db.get(AgentRow, agent_id)
    if row is None:
        raise HTTPException(404, "Agent not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return row


@router.get("/{agent_id}/stats", response_model=AgentStatsOut)
def agent_stats(agent_id: int, db: Session = Depends(get_db)):
    if db.get(AgentRow, agent_id) is None:
        raise HTTPException(404, "Agent not found")
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
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    row = db.get(AgentRow, agent_id)
    if row is None:
        raise HTTPException(404, "Agent not found")
    db.delete(row)
    db.commit()
