from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import RunRow, get_db
from ..schemas import RunOut

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db)):
    return db.scalars(select(RunRow).order_by(RunRow.id.desc())).all()


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    row = db.get(RunRow, run_id)
    if row is None:
        raise HTTPException(404, "Run not found")
    return row
