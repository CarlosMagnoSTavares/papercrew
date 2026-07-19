from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crew_runner import start_run, unmet_dependencies
from ..db import AgentRow, CommentRow, RunRow, TaskRow, add_event, get_db
from ..schemas import (
    CREW_MODES,
    TASK_STATUSES,
    CommentIn,
    CommentOut,
    RejectIn,
    RunOut,
    TaskIn,
    TaskOut,
    TaskPatch,
)
from ..token_optimizer import dependency_ids

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _validate(db: Session, data: dict, task_id: int | None = None) -> None:
    if "status" in data and data["status"] not in TASK_STATUSES:
        raise HTTPException(422, f"status must be one of {TASK_STATUSES}")
    if "crew_mode" in data and data["crew_mode"] not in CREW_MODES:
        raise HTTPException(422, f"crew_mode must be one of {CREW_MODES}")
    if data.get("agent_id") is not None and db.get(AgentRow, data["agent_id"]) is None:
        raise HTTPException(422, "agent_id does not exist")
    for dep_id in dependency_ids(data.get("depends_on") or ""):
        if dep_id == task_id:
            raise HTTPException(422, "task cannot depend on itself")
        if db.get(TaskRow, dep_id) is None:
            raise HTTPException(422, f"dependency task {dep_id} does not exist")


@router.get("", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return db.scalars(select(TaskRow).order_by(TaskRow.id)).all()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(payload: TaskIn, db: Session = Depends(get_db)):
    data = payload.model_dump()
    _validate(db, data)
    row = TaskRow(**data)
    db.add(row)
    add_event(db, "task", f"Task created: {payload.title}")
    db.commit()
    return row


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(task_id: int, payload: TaskPatch, db: Session = Depends(get_db)):
    row = db.get(TaskRow, task_id)
    if row is None:
        raise HTTPException(404, "Task not found")
    data = payload.model_dump(exclude_unset=True)
    _validate(db, data, task_id)
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
    for comment in db.scalars(select(CommentRow).where(CommentRow.task_id == task_id)):
        db.delete(comment)
    db.delete(row)
    db.commit()


@router.post("/{task_id}/run", response_model=RunOut, status_code=202)
def run_task(task_id: int, db: Session = Depends(get_db)):
    row = db.get(TaskRow, task_id)
    if row is None:
        raise HTTPException(404, "Task not found")
    if row.agent_id is None and row.crew_mode != "hierarchical":
        raise HTTPException(422, "Assign an agent before running the task")
    unmet = unmet_dependencies(db, row)
    if unmet:
        raise HTTPException(
            422, f"Blocked by unfinished dependencies: {', '.join(f'#{i}' for i in unmet)}"
        )
    run_id = start_run(task_id)
    return db.get(RunRow, run_id)


@router.get("/{task_id}/runs", response_model=list[RunOut])
def task_runs(task_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(RunRow).where(RunRow.task_id == task_id).order_by(RunRow.id.desc())
    ).all()


@router.post("/{task_id}/approve", response_model=TaskOut)
def approve_task(task_id: int, db: Session = Depends(get_db)):
    row = db.get(TaskRow, task_id)
    if row is None:
        raise HTTPException(404, "Task not found")
    row.status = "done"
    row.feedback = ""
    db.add(CommentRow(task_id=task_id, author="You", body="Approved ✔"))
    add_event(db, "approve", f"Task approved: {row.title}")
    db.commit()
    return row


@router.post("/{task_id}/reject", response_model=TaskOut)
def reject_task(task_id: int, payload: RejectIn, db: Session = Depends(get_db)):
    row = db.get(TaskRow, task_id)
    if row is None:
        raise HTTPException(404, "Task not found")
    row.feedback = payload.feedback
    row.status = "in_progress" if payload.rerun else "todo"
    db.add(CommentRow(task_id=task_id, author="You", body=f"Changes requested: {payload.feedback}"))
    add_event(db, "reject", f"Changes requested on: {row.title}")
    db.commit()
    if payload.rerun and (row.agent_id is not None or row.crew_mode == "hierarchical"):
        start_run(task_id)
    return row


@router.get("/{task_id}/comments", response_model=list[CommentOut])
def list_comments(task_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(CommentRow).where(CommentRow.task_id == task_id).order_by(CommentRow.id)
    ).all()


@router.post("/{task_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(task_id: int, payload: CommentIn, db: Session = Depends(get_db)):
    if db.get(TaskRow, task_id) is None:
        raise HTTPException(404, "Task not found")
    row = CommentRow(task_id=task_id, **payload.model_dump())
    db.add(row)
    db.commit()
    return row
