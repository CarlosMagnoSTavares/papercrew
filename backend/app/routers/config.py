from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..crew_runner import DEFAULT_MODEL, fake_llm_enabled, get_setting
from ..db import SettingRow, get_db
from ..schemas import SettingsIn, SettingsOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _set(db: Session, key: str, value: str) -> None:
    row = db.get(SettingRow, key)
    if row is None:
        db.add(SettingRow(key=key, value=value))
    else:
        row.value = value


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return SettingsOut(
        openrouter_api_key_set=bool(get_setting(db, "openrouter_api_key")),
        default_model=get_setting(db, "default_model", DEFAULT_MODEL),
        fake_llm=fake_llm_enabled(),
    )


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    if payload.openrouter_api_key is not None:
        _set(db, "openrouter_api_key", payload.openrouter_api_key)
    if payload.default_model is not None:
        _set(db, "default_model", payload.default_model)
    db.commit()
    return get_settings(db)
