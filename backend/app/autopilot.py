"""Autopilot: agents keep working toward active goals without human input.

Each tick, per active goal with autopilot on:
1. auto-approve completed results sitting in review (CEO sign-off)
2. retry a failed task once, feeding the error back as reviewer feedback
3. start the next runnable task (deps met, agent assigned, nothing running)
4. when every task is done, evaluate: create complementary tasks for the next
   cycle, or mark the goal achieved (progress 100) and stop

The loop never dies with a prompt — it stops only when the goal is achieved
or the user pauses it. Every action lands in the activity feed.
"""
import os
import threading
import time

from sqlalchemy import select

from .db import CommentRow, CompanyRow, GoalRow, RunRow, SessionLocal, TaskRow, add_event
from .token_optimizer import compress_text

TICK_INTERVAL_SECONDS = 10
MAX_CYCLES = 2  # complementary planning rounds before the goal must conclude
MAX_ATTEMPTS_PER_TASK = 2


def _goal_tasks(db, goal_id: int) -> list[TaskRow]:
    return db.scalars(
        select(TaskRow).where(TaskRow.goal_id == goal_id).order_by(TaskRow.id)
    ).all()


def _has_running(db, tasks: list[TaskRow]) -> bool:
    ids = [t.id for t in tasks]
    if not ids:
        return False
    return (
        db.scalars(
            select(RunRow).where(RunRow.task_id.in_(ids), RunRow.status == "running")
        ).first()
        is not None
    )


def _deps_done(db, task: TaskRow) -> bool:
    from .crew_runner import unmet_dependencies

    return not unmet_dependencies(db, task)


def _auto_approve_reviews(db, goal: GoalRow, tasks: list[TaskRow]) -> int:
    approved = 0
    for task in tasks:
        if task.status != "review":
            continue
        task.status = "done"
        task.feedback = ""
        db.add(CommentRow(task_id=task.id, author="Atlas (CEO)",
                          body="Auto-approved by autopilot ✔"))
        add_event(db, "autopilot", f"Autopilot approved '{task.title}' (goal: {goal.title})",
                  goal.company_id)
        approved += 1
    return approved


def _retry_failed(db, goal: GoalRow, tasks: list[TaskRow]) -> bool:
    from .crew_runner import start_run

    for task in tasks:
        if task.status == "done" or task.agent_id is None:
            continue
        runs = db.scalars(
            select(RunRow).where(RunRow.task_id == task.id).order_by(RunRow.id.desc())
        ).all()
        if not runs or runs[0].status != "failed":
            continue
        if len(runs) >= MAX_ATTEMPTS_PER_TASK:
            continue
        task.feedback = f"Previous attempt failed: {compress_text(runs[0].error, 300)}"
        add_event(db, "autopilot", f"Autopilot retrying failed task '{task.title}'",
                  goal.company_id)
        db.commit()
        start_run(task.id)
        return True
    return False


def _start_next_runnable(db, goal: GoalRow, tasks: list[TaskRow]) -> bool:
    from .crew_runner import start_run

    for task in tasks:
        if task.status != "todo" or task.agent_id is None:
            continue
        if not _deps_done(db, task):
            continue
        add_event(db, "autopilot", f"Autopilot started '{task.title}' (goal: {goal.title})",
                  goal.company_id)
        db.commit()
        start_run(task.id)
        return True
    return False


def _complementary_steps(goal: GoalRow) -> list[dict]:
    topic = compress_text(goal.title, 100)
    return [
        {"title": f"Optimize: {topic}",
         "description": f"Review everything produced so far for '{goal.title}' and improve the weakest part. {goal.description}",
         "specialty": "analysis"},
        {"title": f"Final report: {topic}",
         "description": f"Consolidate all results for '{goal.title}' into a final report with next recommendations.",
         "specialty": "writing"},
    ]


def _llm_next_steps(db, goal: GoalRow, tasks: list[TaskRow]) -> tuple[bool, list[dict]]:
    """Real mode: CEO judges achievement and proposes next tasks."""
    import json
    import re

    from .ceo import _llm_call

    done_summaries = "\n".join(
        f"- {t.title}" for t in tasks if t.status == "done"
    )
    raw = _llm_call(
        f"Goal: {goal.title}. {goal.description}\nCompleted tasks:\n{done_summaries}\n"
        'Is the goal achieved? Reply ONLY JSON: {"achieved": bool, '
        '"next_tasks": [{"title", "description", "specialty"}] (empty if achieved, max 3)}',
        max_tokens=800,
        company_id=goal.company_id,
    )
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return True, []
    data = json.loads(match.group(0))
    return bool(data.get("achieved")), list(data.get("next_tasks", []))[:3]


def _evaluate_goal(db, goal: GoalRow, tasks: list[TaskRow]) -> None:
    from .ceo import create_tasks_from_steps
    from .crew_runner import fake_llm_enabled

    if fake_llm_enabled():
        achieved = goal.cycle >= MAX_CYCLES
        steps = [] if achieved else _complementary_steps(goal)
    else:
        achieved, steps = _llm_next_steps(db, goal, tasks)
        if not achieved and not steps:
            steps = _complementary_steps(goal)
        if goal.cycle >= MAX_CYCLES + 2:  # hard stop so real mode can't loop forever
            achieved, steps = True, []

    if achieved:
        goal.status = "achieved"
        goal.progress = 100
        add_event(db, "goal", f"🎯 Goal achieved: {goal.title}", goal.company_id)
        db.commit()
        return

    created, _ = create_tasks_from_steps(db, steps, goal.company_id, priority="high")
    for info in created:
        task = db.get(TaskRow, info["id"])
        if task is not None:
            task.goal_id = goal.id
    goal.cycle += 1
    add_event(
        db, "autopilot",
        f"Autopilot planned {len(created)} complementary tasks for '{goal.title}' "
        f"(cycle {goal.cycle})",
        goal.company_id,
    )
    db.commit()


def _plan_initial_tasks(db, goal: GoalRow) -> None:
    """A goal without tasks gets its first plan from the CEO."""
    from .ceo import build_steps, create_tasks_from_steps

    steps = build_steps(f"{goal.title}. {goal.description}".strip(), goal.company_id)
    created, _ = create_tasks_from_steps(db, steps, goal.company_id, priority="high")
    for info in created:
        task = db.get(TaskRow, info["id"])
        if task is not None:
            task.goal_id = goal.id
    add_event(db, "autopilot",
              f"Autopilot planned {len(created)} initial tasks for '{goal.title}'",
              goal.company_id)
    db.commit()


def _update_progress(goal: GoalRow, tasks: list[TaskRow]) -> None:
    if not tasks:
        return
    done = sum(1 for t in tasks if t.status == "done")
    # reserve headroom until achieved: cycles may add more work
    goal.progress = min(95, int(done / len(tasks) * 100))


def autopilot_tick() -> int:
    """One pass over every active goal of every live company (they run in
    parallel — each company's crew works its own goals). Returns actions taken."""
    actions = 0
    db = SessionLocal()
    try:
        goals = db.scalars(
            select(GoalRow)
            .join(CompanyRow, CompanyRow.id == GoalRow.company_id)
            .where(
                GoalRow.status == "active",
                GoalRow.autopilot == 1,
                CompanyRow.archived == 0,
            )
        ).all()
        for goal in goals:
            tasks = _goal_tasks(db, goal.id)
            if not tasks:
                _plan_initial_tasks(db, goal)
                actions += 1
                continue
            if _has_running(db, tasks):
                continue
            approved = _auto_approve_reviews(db, goal, tasks)
            actions += approved
            _update_progress(goal, tasks)
            db.commit()
            if _retry_failed(db, goal, tasks):
                actions += 1
                continue
            if _start_next_runnable(db, goal, tasks):
                actions += 1
                continue
            if tasks and all(t.status == "done" for t in tasks):
                _evaluate_goal(db, goal, tasks)
                actions += 1
    finally:
        db.close()
    return actions


def _loop() -> None:
    while True:
        try:
            autopilot_tick()
        except Exception:  # noqa: BLE001 - autopilot must never die
            pass
        time.sleep(TICK_INTERVAL_SECONDS)


def start_autopilot() -> None:
    if os.getenv("PAPERCREW_AUTOPILOT", "1") != "1":
        return
    threading.Thread(target=_loop, daemon=True).start()
