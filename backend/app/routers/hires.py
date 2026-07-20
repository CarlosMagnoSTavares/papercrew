"""Governance-aware hiring: hire requests need explicit approval to become agents."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import AgentRow, HireRequestRow, add_event, get_db
from ..deps import current_company_id, require_company_id
from ..schemas import AgentOut, HireIn, HireOut

router = APIRouter(prefix="/api/hires", tags=["hires"])


def _scoped(db: Session, hire_id: int, company_id: int) -> HireRequestRow:
    row = db.get(HireRequestRow, hire_id)
    if row is None or row.company_id != company_id:
        raise HTTPException(404, "Hire request not found")
    return row


@router.get("", response_model=list[HireOut])
def list_hires(
    db: Session = Depends(get_db), company_id: int = Depends(current_company_id)
):
    return db.scalars(
        select(HireRequestRow)
        .where(HireRequestRow.company_id == company_id)
        .order_by(HireRequestRow.id.desc())
    ).all()


@router.post("", response_model=HireOut, status_code=201)
def create_hire(
    payload: HireIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(require_company_id),
):
    row = HireRequestRow(company_id=company_id, **payload.model_dump())
    db.add(row)
    add_event(db, "hire", f"Hire request filed: {payload.name} ({payload.role})", company_id)
    db.commit()
    return row


@router.post("/{hire_id}/approve", response_model=AgentOut)
def approve_hire(
    hire_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, hire_id, company_id)
    if row.status != "pending":
        raise HTTPException(422, f"Hire request already {row.status}")
    agent = AgentRow(
        company_id=company_id,
        name=row.name,
        role=row.role,
        goal=row.goal,
        backstory=row.backstory,
        specialty=row.specialty,
        model=row.model,
    )
    db.add(agent)
    row.status = "approved"
    add_event(db, "hire", f"Hire approved: {row.name} joined as {row.role}", company_id)
    db.commit()
    return agent


@router.post("/{hire_id}/reject", response_model=HireOut)
def reject_hire(
    hire_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, hire_id, company_id)
    if row.status != "pending":
        raise HTTPException(422, f"Hire request already {row.status}")
    row.status = "rejected"
    add_event(db, "hire", f"Hire rejected: {row.name}", company_id)
    db.commit()
    return row


@router.delete("/{hire_id}", status_code=204)
def delete_hire(
    hire_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    db.delete(_scoped(db, hire_id, company_id))
    db.commit()
