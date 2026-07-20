"""Plan documents: draft (optionally with the CEO), then convert into tasks."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ceo import convert_plan, draft_plan_content
from ..db import PlanRow, add_event, get_db
from ..schemas import PlanIn, PlanOut

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return db.scalars(select(PlanRow).order_by(PlanRow.id.desc())).all()


@router.post("", response_model=PlanOut, status_code=201)
def create_plan(payload: PlanIn, db: Session = Depends(get_db)):
    content = payload.content
    if payload.draft_with_ceo:
        try:
            content = draft_plan_content(payload.title, payload.objective)
        except Exception as exc:  # noqa: BLE001 - surface planner errors
            raise HTTPException(502, f"CEO could not draft the plan: {exc}") from exc
    row = PlanRow(title=payload.title, objective=payload.objective, content=content)
    db.add(row)
    add_event(db, "plan", f"Plan drafted: {payload.title}")
    db.commit()
    return row


@router.post("/{plan_id}/convert")
def convert(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(PlanRow, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    if plan.status == "converted":
        raise HTTPException(422, "Plan already converted")
    try:
        created = convert_plan(plan_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Could not convert plan: {exc}") from exc
    return {"tasks": created}


@router.delete("/{plan_id}", status_code=204)
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    row = db.get(PlanRow, plan_id)
    if row is None:
        raise HTTPException(404, "Plan not found")
    db.delete(row)
    db.commit()
