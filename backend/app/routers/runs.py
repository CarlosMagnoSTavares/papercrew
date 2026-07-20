from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import RunRow, TaskRow, get_db
from ..deps import current_company_id
from ..schemas import RunOut

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
def list_runs(
    db: Session = Depends(get_db), company_id: int = Depends(current_company_id)
):
    return db.scalars(
        select(RunRow)
        .join(TaskRow, TaskRow.id == RunRow.task_id)
        .where(TaskRow.company_id == company_id)
        .order_by(RunRow.id.desc())
    ).all()


@router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    row = db.get(RunRow, run_id)
    if row is None:
        raise HTTPException(404, "Run not found")
    task = db.get(TaskRow, row.task_id)
    if task is None or task.company_id != company_id:
        raise HTTPException(404, "Run not found")
    return row
