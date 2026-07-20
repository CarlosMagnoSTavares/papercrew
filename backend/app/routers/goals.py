"""Goals and the autopilot that works toward them."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..autopilot import autopilot_tick
from ..db import GoalRow, TaskRow, add_event, get_db
from ..deps import current_company_id, require_company_id
from ..schemas import GoalIn, GoalOut, TaskOut

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _scoped(db: Session, goal_id: int, company_id: int) -> GoalRow:
    row = db.get(GoalRow, goal_id)
    if row is None or row.company_id != company_id:
        raise HTTPException(404, "Goal not found")
    return row


@router.get("", response_model=list[GoalOut])
def list_goals(
    db: Session = Depends(get_db), company_id: int = Depends(current_company_id)
):
    return db.scalars(
        select(GoalRow).where(GoalRow.company_id == company_id).order_by(GoalRow.id.desc())
    ).all()


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(
    payload: GoalIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(require_company_id),
):
    row = GoalRow(company_id=company_id, **payload.model_dump())
    db.add(row)
    add_event(db, "goal", f"Goal created: {payload.title}", company_id)
    db.commit()
    return row


@router.get("/{goal_id}/tasks", response_model=list[TaskOut])
def goal_tasks(
    goal_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    _scoped(db, goal_id, company_id)
    return db.scalars(
        select(TaskRow).where(TaskRow.goal_id == goal_id).order_by(TaskRow.id)
    ).all()


@router.post("/{goal_id}/pause", response_model=GoalOut)
def pause_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, goal_id, company_id)
    row.status = "paused"
    add_event(db, "goal", f"Goal paused: {row.title}", company_id)
    db.commit()
    return row


@router.post("/{goal_id}/resume", response_model=GoalOut)
def resume_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, goal_id, company_id)
    if row.status == "achieved":
        raise HTTPException(422, "Goal already achieved")
    row.status = "active"
    add_event(db, "goal", f"Goal resumed: {row.title}", company_id)
    db.commit()
    return row


@router.post("/tick")
def manual_tick():
    """Run one autopilot pass across every company immediately (demo / tests)."""
    return {"actions": autopilot_tick()}
