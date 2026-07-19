from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AgentRow, RoutineRow, add_event, get_db
from ..schemas import RoutineIn, RoutineOut

router = APIRouter(prefix="/api/routines", tags=["routines"])


def _validate_agent(db: Session, agent_id: int | None) -> None:
    if agent_id is not None and db.get(AgentRow, agent_id) is None:
        raise HTTPException(422, "agent_id does not exist")


@router.get("", response_model=list[RoutineOut])
def list_routines(db: Session = Depends(get_db)):
    return db.scalars(select(RoutineRow).order_by(RoutineRow.id)).all()


@router.post("", response_model=RoutineOut, status_code=201)
def create_routine(payload: RoutineIn, db: Session = Depends(get_db)):
    _validate_agent(db, payload.agent_id)
    row = RoutineRow(**payload.model_dump())
    db.add(row)
    add_event(db, "routine", f"Routine created: {payload.title} (every {payload.interval_minutes}m)")
    db.commit()
    return row


@router.put("/{routine_id}", response_model=RoutineOut)
def update_routine(routine_id: int, payload: RoutineIn, db: Session = Depends(get_db)):
    row = db.get(RoutineRow, routine_id)
    if row is None:
        raise HTTPException(404, "Routine not found")
    _validate_agent(db, payload.agent_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return row


@router.delete("/{routine_id}", status_code=204)
def delete_routine(routine_id: int, db: Session = Depends(get_db)):
    row = db.get(RoutineRow, routine_id)
    if row is None:
        raise HTTPException(404, "Routine not found")
    db.delete(row)
    db.commit()
