"""Company onboarding and status."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..crew_runner import get_setting
from ..db import get_db
from ..onboarding import onboard_company
from ..schemas import CompanyOut, OnboardIn

router = APIRouter(prefix="/api/company", tags=["company"])


@router.get("", response_model=CompanyOut)
def company_status(db: Session = Depends(get_db)):
    return CompanyOut(
        onboarded=get_setting(db, "onboarded") == "1",
        company_name=get_setting(db, "company_name", ""),
        company_mission=get_setting(db, "company_mission", ""),
    )


@router.post("/onboard")
def onboard(payload: OnboardIn, db: Session = Depends(get_db)):
    if get_setting(db, "onboarded") == "1":
        raise HTTPException(422, "Company already onboarded")
    try:
        return onboard_company(payload.company_name, payload.mission, payload.first_goal)
    except Exception as exc:  # noqa: BLE001 - surface planner failures
        raise HTTPException(502, f"Onboarding failed: {exc}") from exc
