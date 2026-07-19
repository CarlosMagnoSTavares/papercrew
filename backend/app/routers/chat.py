from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ceo import handle_message
from ..db import ChatMessageRow, get_db
from ..schemas import ChatIn, ChatMessageOut

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("", response_model=list[ChatMessageOut])
def history(db: Session = Depends(get_db)):
    return db.scalars(select(ChatMessageRow).order_by(ChatMessageRow.id)).all()


@router.post("")
def send(payload: ChatIn):
    try:
        return handle_message(payload.message)
    except Exception as exc:  # noqa: BLE001 - surface planner errors to the UI
        raise HTTPException(502, f"CEO could not build a plan: {exc}") from exc
