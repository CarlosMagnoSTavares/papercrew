"""Governance-aware hiring: hire requests need explicit approval to become agents."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AgentRow, HireRequestRow, add_event, get_db
from ..schemas import AgentOut, HireIn, HireOut

router = APIRouter(prefix="/api/hires", tags=["hires"])


@router.get("", response_model=list[HireOut])
def list_hires(db: Session = Depends(get_db)):
    return db.scalars(select(HireRequestRow).order_by(HireRequestRow.id.desc())).all()


@router.post("", response_model=HireOut, status_code=201)
def create_hire(payload: HireIn, db: Session = Depends(get_db)):
    row = HireRequestRow(**payload.model_dump())
    db.add(row)
    add_event(db, "hire", f"Hire request filed: {payload.name} ({payload.role})")
    db.commit()
    return row


@router.post("/{hire_id}/approve", response_model=AgentOut)
def approve_hire(hire_id: int, db: Session = Depends(get_db)):
    row = db.get(HireRequestRow, hire_id)
    if row is None:
        raise HTTPException(404, "Hire request not found")
    if row.status != "pending":
        raise HTTPException(422, f"Hire request already {row.status}")
    agent = AgentRow(
        name=row.name,
        role=row.role,
        goal=row.goal,
        backstory=row.backstory,
        specialty=row.specialty,
        model=row.model,
    )
    db.add(agent)
    row.status = "approved"
    add_event(db, "hire", f"Hire approved: {row.name} joined as {row.role}")
    db.commit()
    return agent


@router.post("/{hire_id}/reject", response_model=HireOut)
def reject_hire(hire_id: int, db: Session = Depends(get_db)):
    row = db.get(HireRequestRow, hire_id)
    if row is None:
        raise HTTPException(404, "Hire request not found")
    if row.status != "pending":
        raise HTTPException(422, f"Hire request already {row.status}")
    row.status = "rejected"
    add_event(db, "hire", f"Hire rejected: {row.name}")
    db.commit()
    return row


@router.delete("/{hire_id}", status_code=204)
def delete_hire(hire_id: int, db: Session = Depends(get_db)):
    row = db.get(HireRequestRow, hire_id)
    if row is None:
        raise HTTPException(404, "Hire request not found")
    db.delete(row)
    db.commit()
