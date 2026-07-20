"""Companies: create, list, edit, archive. Several run side by side."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import (
    AgentRow,
    ChatMessageRow,
    CommentRow,
    CompanyRow,
    EventRow,
    GoalRow,
    HireRequestRow,
    PlanRow,
    RoutineRow,
    RunRow,
    SkillRow,
    TaskRow,
    add_event,
    get_db,
)
from ..onboarding import create_company
from ..schemas import CompanyCreateIn, CompanyOut, CompanyPatch, CompanySummaryOut

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _summary(db: Session, company: CompanyRow) -> CompanySummaryOut:
    agents = db.scalar(
        select(func.count(AgentRow.id)).where(AgentRow.company_id == company.id)
    )
    active_goals = db.scalar(
        select(func.count(GoalRow.id)).where(
            GoalRow.company_id == company.id, GoalRow.status == "active"
        )
    )
    open_tasks = db.scalar(
        select(func.count(TaskRow.id)).where(
            TaskRow.company_id == company.id, TaskRow.status != "done"
        )
    )
    cost = db.scalar(
        select(func.coalesce(func.sum(RunRow.cost), 0.0))
        .join(TaskRow, TaskRow.id == RunRow.task_id)
        .where(TaskRow.company_id == company.id)
    )
    return CompanySummaryOut(
        id=company.id,
        name=company.name,
        mission=company.mission,
        default_model=company.default_model,
        monthly_budget=company.monthly_budget,
        archived=bool(company.archived),
        created_at=company.created_at,
        agents=agents or 0,
        active_goals=active_goals or 0,
        open_tasks=open_tasks or 0,
        total_cost=round(cost or 0.0, 6),
    )


@router.get("", response_model=list[CompanySummaryOut])
def list_companies(include_archived: bool = False, db: Session = Depends(get_db)):
    query = select(CompanyRow).order_by(CompanyRow.id)
    if not include_archived:
        query = query.where(CompanyRow.archived == 0)
    return [_summary(db, company) for company in db.scalars(query)]


@router.post("", status_code=201)
def create(payload: CompanyCreateIn, db: Session = Depends(get_db)):
    """Build a whole company: crew, skills, first goal and initial tasks."""
    try:
        return create_company(payload.company_name, payload.mission, payload.first_goal)
    except Exception as exc:  # noqa: BLE001 - surface planner failures to the UI
        raise HTTPException(502, f"Company creation failed: {exc}") from exc


@router.get("/{company_id}", response_model=CompanySummaryOut)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.get(CompanyRow, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    return _summary(db, company)


@router.patch("/{company_id}", response_model=CompanyOut)
def patch_company(company_id: int, payload: CompanyPatch, db: Session = Depends(get_db)):
    company = db.get(CompanyRow, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, key, value)
    db.commit()
    return CompanyOut(
        id=company.id,
        name=company.name,
        mission=company.mission,
        default_model=company.default_model,
        monthly_budget=company.monthly_budget,
        archived=bool(company.archived),
        created_at=company.created_at,
    )


@router.post("/{company_id}/archive", response_model=CompanyOut)
def archive_company(company_id: int, db: Session = Depends(get_db)):
    """Archive: the company stops working (autopilot and routines skip it) but
    all of its history stays queryable."""
    company = db.get(CompanyRow, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    company.archived = 1
    for goal in db.scalars(
        select(GoalRow).where(GoalRow.company_id == company_id, GoalRow.status == "active")
    ):
        goal.status = "paused"
    add_event(db, "company", f"Company archived: {company.name}", company_id)
    db.commit()
    return CompanyOut(
        id=company.id,
        name=company.name,
        mission=company.mission,
        default_model=company.default_model,
        monthly_budget=company.monthly_budget,
        archived=True,
        created_at=company.created_at,
    )


@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: int, confirm_name: str | None = None, db: Session = Depends(get_db)
):
    """Permanently delete a company and everything it owns.

    Irreversible — prefer archiving. When `confirm_name` is supplied it must
    match the company name exactly, which is how the UI guards the action.
    A run still executing for a deleted task simply finds its row gone and
    stops writing, so in-flight work cannot resurrect anything.
    """
    company = db.get(CompanyRow, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    if confirm_name is not None and confirm_name != company.name:
        raise HTTPException(422, "confirm_name does not match the company name")

    task_ids = list(
        db.scalars(select(TaskRow.id).where(TaskRow.company_id == company_id))
    )
    agent_ids = list(
        db.scalars(select(AgentRow.id).where(AgentRow.company_id == company_id))
    )
    if task_ids:
        db.query(CommentRow).filter(CommentRow.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )
        db.query(RunRow).filter(RunRow.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )
    if agent_ids:
        db.query(SkillRow).filter(SkillRow.agent_id.in_(agent_ids)).delete(
            synchronize_session=False
        )
    for model in (
        TaskRow, AgentRow, GoalRow, PlanRow, RoutineRow,
        HireRequestRow, ChatMessageRow, EventRow,
    ):
        db.query(model).filter(model.company_id == company_id).delete(
            synchronize_session=False
        )
    db.delete(company)
    db.commit()


@router.post("/{company_id}/restore", response_model=CompanyOut)
def restore_company(company_id: int, db: Session = Depends(get_db)):
    company = db.get(CompanyRow, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    company.archived = 0
    add_event(db, "company", f"Company restored: {company.name}", company_id)
    db.commit()
    return CompanyOut(
        id=company.id,
        name=company.name,
        mission=company.mission,
        default_model=company.default_model,
        monthly_budget=company.monthly_budget,
        archived=False,
        created_at=company.created_at,
    )
