"""Activity feed, token/cost statistics, inbox and work products."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import AgentRow, EventRow, HireRequestRow, RunRow, TaskRow, get_db
from ..schemas import EventOut, InboxItem, StatsOut, WorkProductOut

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/events", response_model=list[EventOut])
def list_events(limit: int = 30, db: Session = Depends(get_db)):
    return db.scalars(
        select(EventRow).order_by(EventRow.id.desc()).limit(min(limit, 100))
    ).all()


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    row = db.execute(
        select(
            func.count(RunRow.id),
            func.coalesce(func.sum(RunRow.prompt_tokens), 0),
            func.coalesce(func.sum(RunRow.completion_tokens), 0),
            func.coalesce(func.sum(RunRow.tokens_saved), 0),
            func.coalesce(func.sum(RunRow.cost), 0.0),
        )
    ).one()
    return StatsOut(
        total_runs=row[0],
        prompt_tokens=row[1],
        completion_tokens=row[2],
        tokens_saved=row[3],
        total_cost=round(row[4], 6),
    )


@router.get("/inbox", response_model=list[InboxItem])
def inbox(db: Session = Depends(get_db)):
    items: list[InboxItem] = []
    for task in db.scalars(select(TaskRow).where(TaskRow.status == "review")):
        items.append(
            InboxItem(kind="review", ref_id=task.id, title=task.title,
                      detail="Result ready for your review — approve or request changes")
        )
    for hire in db.scalars(select(HireRequestRow).where(HireRequestRow.status == "pending")):
        items.append(
            InboxItem(kind="hire", ref_id=hire.id, title=f"{hire.name} ({hire.role})",
                      detail=hire.reason or "Hire request pending approval")
        )
    failed_task_ids = set()
    for run in db.scalars(select(RunRow).where(RunRow.status == "failed").order_by(RunRow.id.desc())):
        task = db.get(TaskRow, run.task_id)
        if task is None or task.status == "done" or task.id in failed_task_ids:
            continue
        latest = db.scalars(
            select(RunRow).where(RunRow.task_id == task.id).order_by(RunRow.id.desc())
        ).first()
        if latest is not None and latest.status == "failed":
            failed_task_ids.add(task.id)
            items.append(
                InboxItem(kind="failure", ref_id=task.id, title=task.title,
                          detail=f"Last run failed: {latest.error[:160]}")
            )
    for task in db.scalars(
        select(TaskRow).where(TaskRow.agent_id.is_(None), TaskRow.status.in_(("todo", "in_progress")))
    ):
        items.append(
            InboxItem(kind="unassigned", ref_id=task.id, title=task.title,
                      detail="No agent assigned — assign one so it can run")
        )
    return items


@router.get("/work-products", response_model=list[WorkProductOut])
def work_products(db: Session = Depends(get_db)):
    products = []
    for task in db.scalars(
        select(TaskRow).where(TaskRow.status == "done").order_by(TaskRow.id.desc())
    ):
        run = db.scalars(
            select(RunRow)
            .where(RunRow.task_id == task.id, RunRow.status == "completed")
            .order_by(RunRow.id.desc())
        ).first()
        if run is None or not run.output:
            continue
        agent = db.get(AgentRow, task.agent_id) if task.agent_id else None
        products.append(
            WorkProductOut(
                task_id=task.id,
                title=task.title,
                agent=agent.name if agent else "—",
                output=run.output,
                approved_at=run.finished_at,
            )
        )
    return products
