"""Goals and the autopilot that works toward them."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..autopilot import autopilot_tick
from ..db import GoalRow, TaskRow, add_event, get_db
from ..schemas import GoalIn, GoalOut, TaskOut

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db)):
    return db.scalars(select(GoalRow).order_by(GoalRow.id.desc())).all()


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(payload: GoalIn, db: Session = Depends(get_db)):
    row = GoalRow(**payload.model_dump())
    db.add(row)
    add_event(db, "goal", f"Goal created: {payload.title}")
    db.commit()
    return row


@router.get("/{goal_id}/tasks", response_model=list[TaskOut])
def goal_tasks(goal_id: int, db: Session = Depends(get_db)):
    if db.get(GoalRow, goal_id) is None:
        raise HTTPException(404, "Goal not found")
    return db.scalars(
        select(TaskRow).where(TaskRow.goal_id == goal_id).order_by(TaskRow.id)
    ).all()


@router.post("/{goal_id}/pause", response_model=GoalOut)
def pause_goal(goal_id: int, db: Session = Depends(get_db)):
    row = db.get(GoalRow, goal_id)
    if row is None:
        raise HTTPException(404, "Goal not found")
    row.status = "paused"
    add_event(db, "goal", f"Goal paused: {row.title}")
    db.commit()
    return row


@router.post("/{goal_id}/resume", response_model=GoalOut)
def resume_goal(goal_id: int, db: Session = Depends(get_db)):
    row = db.get(GoalRow, goal_id)
    if row is None:
        raise HTTPException(404, "Goal not found")
    if row.status == "achieved":
        raise HTTPException(422, "Goal already achieved")
    row.status = "active"
    add_event(db, "goal", f"Goal resumed: {row.title}")
    db.commit()
    return row


@router.post("/tick")
def manual_tick():
    """Run one autopilot pass immediately (demo / tests)."""
    return {"actions": autopilot_tick()}
