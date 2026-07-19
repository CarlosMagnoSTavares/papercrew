from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AgentRow, get_db
from ..schemas import AgentIn, AgentOut

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


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    row = db.get(AgentRow, agent_id)
    if row is None:
        raise HTTPException(404, "Agent not found")
    db.delete(row)
    db.commit()
