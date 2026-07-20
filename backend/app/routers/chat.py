from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ceo import handle_message
from ..db import ChatMessageRow, get_db
from ..deps import current_company_id, require_company_id
from ..schemas import ChatIn, ChatMessageOut

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("", response_model=list[ChatMessageOut])
def history(
    db: Session = Depends(get_db), company_id: int = Depends(current_company_id)
):
    return db.scalars(
        select(ChatMessageRow)
        .where(ChatMessageRow.company_id == company_id)
        .order_by(ChatMessageRow.id)
    ).all()


@router.post("")
def send(payload: ChatIn, company_id: int = Depends(require_company_id)):
    from .. import llm

    try:
        return handle_message(payload.message, company_id)
    except llm.LLMNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface planner errors to the UI
        raise HTTPException(502, f"CEO could not build a plan: {exc}") from exc
