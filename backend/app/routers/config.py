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
        company_name=get_setting(db, "company_name", "PaperCrew Inc."),
        company_mission=get_setting(db, "company_mission", ""),
        price_per_1k_tokens=get_setting(db, "price_per_1k_tokens", "0"),
        monthly_budget=get_setting(db, "monthly_budget", "0"),
        fake_llm=fake_llm_enabled(),
    )


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    fields = {
        "openrouter_api_key": payload.openrouter_api_key,
        "default_model": payload.default_model,
        "company_name": payload.company_name,
        "company_mission": payload.company_mission,
        "price_per_1k_tokens": payload.price_per_1k_tokens,
        "monthly_budget": payload.monthly_budget,
    }
    for key, value in fields.items():
        if value is not None:
            _set(db, key, value)
    db.commit()
    return get_settings(db)
