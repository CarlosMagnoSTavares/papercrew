from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AgentRow, RoutineRow, add_event, get_db
from ..deps import current_company_id, require_company_id
from ..schemas import RoutineIn, RoutineOut

router = APIRouter(prefix="/api/routines", tags=["routines"])


def _scoped(db: Session, routine_id: int, company_id: int) -> RoutineRow:
    row = db.get(RoutineRow, routine_id)
    if row is None or row.company_id != company_id:
        raise HTTPException(404, "Routine not found")
    return row


def _validate_agent(db: Session, agent_id: int | None, company_id: int) -> None:
    if agent_id is None:
        return
    agent = db.get(AgentRow, agent_id)
    if agent is None or agent.company_id != company_id:
        raise HTTPException(422, "agent_id does not exist in this company")


@router.get("", response_model=list[RoutineOut])
def list_routines(
    db: Session = Depends(get_db), company_id: int = Depends(current_company_id)
):
    return db.scalars(
        select(RoutineRow).where(RoutineRow.company_id == company_id).order_by(RoutineRow.id)
    ).all()


@router.post("", response_model=RoutineOut, status_code=201)
def create_routine(
    payload: RoutineIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(require_company_id),
):
    _validate_agent(db, payload.agent_id, company_id)
    row = RoutineRow(company_id=company_id, **payload.model_dump())
    db.add(row)
    add_event(db, "routine",
              f"Routine created: {payload.title} (every {payload.interval_minutes}m)",
              company_id)
    db.commit()
    return row


@router.put("/{routine_id}", response_model=RoutineOut)
def update_routine(
    routine_id: int,
    payload: RoutineIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, routine_id, company_id)
    _validate_agent(db, payload.agent_id, company_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return row


@router.delete("/{routine_id}", status_code=204)
def delete_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    db.delete(_scoped(db, routine_id, company_id))
    db.commit()
