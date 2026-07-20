from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crew_runner import start_run, unmet_dependencies
from ..db import AgentRow, CommentRow, CompanyRow, RunRow, TaskRow, add_event, get_db
from ..deps import current_company_id, require_company_id
from ..schemas import (
    CREW_MODES,
    PRIORITIES,
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


def _scoped(db: Session, task_id: int, company_id: int) -> TaskRow:
    row = db.get(TaskRow, task_id)
    if row is None or row.company_id != company_id:
        raise HTTPException(404, "Task not found")
    return row


def _check_budget(db: Session, company_id: int) -> None:
    company = db.get(CompanyRow, company_id)
    budget = company.monthly_budget if company else 0.0
    if budget <= 0:
        return
    spent = (
        db.scalar(
            select(func.coalesce(func.sum(RunRow.cost), 0.0))
            .join(TaskRow, TaskRow.id == RunRow.task_id)
            .where(TaskRow.company_id == company_id)
        )
        or 0.0
    )
    if spent >= budget:
        raise HTTPException(
            402, f"Budget exceeded: ${spent:.4f} spent of ${budget:.2f} cap. "
            "Raise this company's budget in Settings to keep running.",
        )


def _validate(db: Session, data: dict, company_id: int, task_id: int | None = None) -> None:
    if "status" in data and data["status"] not in TASK_STATUSES:
        raise HTTPException(422, f"status must be one of {TASK_STATUSES}")
    if "crew_mode" in data and data["crew_mode"] not in CREW_MODES:
        raise HTTPException(422, f"crew_mode must be one of {CREW_MODES}")
    if "priority" in data and data["priority"] not in PRIORITIES:
        raise HTTPException(422, f"priority must be one of {PRIORITIES}")
    if data.get("agent_id") is not None:
        agent = db.get(AgentRow, data["agent_id"])
        if agent is None or agent.company_id != company_id:
            raise HTTPException(422, "agent_id does not exist in this company")
    for dep_id in dependency_ids(data.get("depends_on") or ""):
        if dep_id == task_id:
            raise HTTPException(422, "task cannot depend on itself")
        dep = db.get(TaskRow, dep_id)
        if dep is None or dep.company_id != company_id:
            raise HTTPException(422, f"dependency task {dep_id} does not exist in this company")


@router.get("", response_model=list[TaskOut])
def list_tasks(
    db: Session = Depends(get_db), company_id: int = Depends(current_company_id)
):
    return db.scalars(
        select(TaskRow).where(TaskRow.company_id == company_id).order_by(TaskRow.id)
    ).all()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(require_company_id),
):
    data = payload.model_dump()
    data.pop("goal_id", None)
    _validate(db, data, company_id)
    row = TaskRow(company_id=company_id, **data)
    db.add(row)
    add_event(db, "task", f"Task created: {payload.title}", company_id)
    db.commit()
    return row


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(
    task_id: int,
    payload: TaskPatch,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, task_id, company_id)
    data = payload.model_dump(exclude_unset=True)
    _validate(db, data, company_id, task_id)
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    return row


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, task_id, company_id)
    for run in db.scalars(select(RunRow).where(RunRow.task_id == task_id)):
        db.delete(run)
    for comment in db.scalars(select(CommentRow).where(CommentRow.task_id == task_id)):
        db.delete(comment)
    db.delete(row)
    db.commit()


@router.post("/{task_id}/run", response_model=RunOut, status_code=202)
def run_task(
    task_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, task_id, company_id)
    if row.agent_id is None and row.crew_mode != "hierarchical":
        raise HTTPException(422, "Assign an agent before running the task")
    unmet = unmet_dependencies(db, row)
    if unmet:
        raise HTTPException(
            422, f"Blocked by unfinished dependencies: {', '.join(f'#{i}' for i in unmet)}"
        )
    _check_budget(db, company_id)
    run_id = start_run(task_id)
    return db.get(RunRow, run_id)


@router.get("/{task_id}/runs", response_model=list[RunOut])
def task_runs(
    task_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    _scoped(db, task_id, company_id)
    return db.scalars(
        select(RunRow).where(RunRow.task_id == task_id).order_by(RunRow.id.desc())
    ).all()


@router.post("/{task_id}/approve", response_model=TaskOut)
def approve_task(
    task_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, task_id, company_id)
    row.status = "done"
    row.feedback = ""
    db.add(CommentRow(task_id=task_id, author="You", body="Approved ✔"))
    add_event(db, "approve", f"Task approved: {row.title}", company_id)
    db.commit()
    return row


@router.post("/{task_id}/reject", response_model=TaskOut)
def reject_task(
    task_id: int,
    payload: RejectIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = _scoped(db, task_id, company_id)
    row.feedback = payload.feedback
    row.status = "in_progress" if payload.rerun else "todo"
    db.add(CommentRow(task_id=task_id, author="You", body=f"Changes requested: {payload.feedback}"))
    add_event(db, "reject", f"Changes requested on: {row.title}", company_id)
    db.commit()
    if payload.rerun and (row.agent_id is not None or row.crew_mode == "hierarchical"):
        start_run(task_id)
    return row


@router.get("/{task_id}/comments", response_model=list[CommentOut])
def list_comments(
    task_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    _scoped(db, task_id, company_id)
    return db.scalars(
        select(CommentRow).where(CommentRow.task_id == task_id).order_by(CommentRow.id)
    ).all()


@router.post("/{task_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    task_id: int,
    payload: CommentIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    _scoped(db, task_id, company_id)
    row = CommentRow(task_id=task_id, **payload.model_dump())
    db.add(row)
    db.commit()
    return row
