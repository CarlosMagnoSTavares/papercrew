"""Plan documents: draft (optionally with the CEO), then convert into tasks."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ceo import convert_plan, draft_plan_content
from ..db import PlanRow, add_event, get_db
from ..deps import current_company_id, require_company_id
from ..schemas import PlanIn, PlanOut

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _scoped(db: Session, plan_id: int, company_id: int) -> PlanRow:
    row = db.get(PlanRow, plan_id)
    if row is None or row.company_id != company_id:
        raise HTTPException(404, "Plan not found")
    return row


@router.get("", response_model=list[PlanOut])
def list_plans(
    db: Session = Depends(get_db), company_id: int = Depends(current_company_id)
):
    return db.scalars(
        select(PlanRow).where(PlanRow.company_id == company_id).order_by(PlanRow.id.desc())
    ).all()


@router.post("", response_model=PlanOut, status_code=201)
def create_plan(
    payload: PlanIn,
    db: Session = Depends(get_db),
    company_id: int = Depends(require_company_id),
):
    from .. import llm

    content = payload.content
    if payload.draft_with_ceo:
        try:
            content = draft_plan_content(payload.title, payload.objective, company_id)
        except llm.LLMNotConfigured as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - surface planner errors
            raise HTTPException(502, f"CEO could not draft the plan: {exc}") from exc
    row = PlanRow(
        company_id=company_id,
        title=payload.title,
        objective=payload.objective,
        content=content,
    )
    db.add(row)
    add_event(db, "plan", f"Plan drafted: {payload.title}", company_id)
    db.commit()
    return row


@router.post("/{plan_id}/convert")
def convert(
    plan_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    plan = _scoped(db, plan_id, company_id)
    if plan.status == "converted":
        raise HTTPException(422, "Plan already converted")
    try:
        created = convert_plan(plan_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Could not convert plan: {exc}") from exc
    return {"tasks": created}


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    company_id: int = Depends(current_company_id),
):
    db.delete(_scoped(db, plan_id, company_id))
    db.commit()
