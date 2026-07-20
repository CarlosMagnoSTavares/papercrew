"""Routine scheduler: fires enabled routines when due, creating (and optionally
auto-running) a task per occurrence. Simple daemon loop — no external deps."""
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .db import CompanyRow, RoutineRow, SessionLocal, TaskRow, add_event

CHECK_INTERVAL_SECONDS = 15


def _due(routine: RoutineRow, now: datetime) -> bool:
    try:
        next_at = datetime.fromisoformat(routine.next_run_at)
    except ValueError:
        return True
    return next_at <= now


def fire_due_routines() -> int:
    """Create tasks for all due routines. Returns number fired."""
    from .crew_runner import start_run

    now = datetime.now(timezone.utc)
    fired = 0
    db = SessionLocal()
    try:
        routines = db.scalars(
            select(RoutineRow)
            .join(CompanyRow, CompanyRow.id == RoutineRow.company_id)
            .where(RoutineRow.enabled == 1, CompanyRow.archived == 0)
        ).all()
        for routine in routines:
            if not _due(routine, now):
                continue
            task = TaskRow(
                company_id=routine.company_id,
                title=f"[routine] {routine.title}",
                description=routine.description,
                agent_id=routine.agent_id,
            )
            db.add(task)
            db.flush()
            routine.next_run_at = (
                now + timedelta(minutes=routine.interval_minutes)
            ).isoformat()
            add_event(db, "routine", f"Routine '{routine.title}' fired → task #{task.id}",
                      routine.company_id)
            db.commit()
            fired += 1
            if routine.auto_run and routine.agent_id:
                start_run(task.id)
    finally:
        db.close()
    return fired


def _loop() -> None:
    while True:
        try:
            fire_due_routines()
        except Exception:  # noqa: BLE001 - scheduler must never die
            pass
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_scheduler() -> None:
    if os.getenv("PAPERCREW_SCHEDULER", "1") != "1":
        return
    threading.Thread(target=_loop, daemon=True).start()
