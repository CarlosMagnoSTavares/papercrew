from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crew_runner import start_run
from ..db import AgentRow, RunRow, TaskRow, get_db
from ..schemas import TASK_STATUSES, RunOut, TaskIn, TaskOut, TaskPatch

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _validate_status(status: str) -> None:
    if status not in TASK_STATUSES:
        raise HTTPException(422, f"status must be one of {TASK_STATUSES}")


def _validate_agent(db: Session, agent_id: int | None) -> None:
    if agent_id is not None and db.get(AgentRow, agent_id) is None:
        raise HTTPException(422, "agent_id does not exist")


@router.get("", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return db.scalars(select(TaskRow).order_by(TaskRow.id)).all()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(payload: TaskIn, db: Session = Depends(get_db)):
    _validate_status(payload.status)
    _validate_agent(db, payload.agent_id)
    row = TaskRow(**payload.model_dump())
    db.add(row)
    db.commit()
    return row


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(task_id: int, payload: TaskPatch, db: Session = Depends(get_db)):
    row = db.get(TaskRow, task_id)
    if row is None:
        raise HTTPException(404, "Task not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        _validate_status(data["status"])
    if "agent_id" in data:
        _validate_agent(db, data["agent_id"])
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    return row


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    row = db.get(TaskRow, task_id)
    if row is None:
        raise HTTPException(404, "Task not found")
    for run in db.scalars(select(RunRow).where(RunRow.task_id == task_id)):
        db.delete(run)
    db.delete(row)
    db.commit()


@router.post("/{task_id}/run", response_model=RunOut, status_code=202)
def run_task(task_id: int, db: Session = Depends(get_db)):
    row = db.get(TaskRow, task_id)
    if row is None:
        raise HTTPException(404, "Task not found")
    if row.agent_id is None:
        raise HTTPException(422, "Assign an agent before running the task")
    run_id = start_run(task_id)
    return db.get(RunRow, run_id)


@router.get("/{task_id}/runs", response_model=list[RunOut])
def task_runs(task_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(RunRow).where(RunRow.task_id == task_id).order_by(RunRow.id.desc())
    ).all()
