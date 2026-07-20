"""Request-scoped company resolution.

The active company comes from the `X-Company-Id` header (what the UI sends),
falling back to a `company_id` query param and finally to the oldest company,
so single-company setups and direct curl calls keep working untouched.
"""
from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import CompanyRow, get_db


def current_company_id(
    x_company_id: int | None = Header(default=None, alias="X-Company-Id"),
    company_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> int:
    """Resolved company id, or 0 when no company exists yet."""
    requested = x_company_id if x_company_id is not None else company_id
    if requested is not None:
        company = db.get(CompanyRow, requested)
        if company is None or company.archived:
            raise HTTPException(404, f"Company {requested} not found")
        return company.id
    first = db.scalars(
        select(CompanyRow).where(CompanyRow.archived == 0).order_by(CompanyRow.id)
    ).first()
    return first.id if first else 0


def require_company_id(cid: int = Depends(current_company_id)) -> int:
    if not cid:
        raise HTTPException(400, "No company yet — create one first (POST /api/companies)")
    return cid
