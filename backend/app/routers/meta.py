"""Activity feed and token/cost statistics."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import EventRow, RunRow, get_db
from ..schemas import EventOut, StatsOut

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
