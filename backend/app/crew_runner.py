"""Executes a PaperCrew task through a CrewAI crew (or a fake LLM in demo mode)."""
import os
import threading
import time

from .db import AgentRow, RunRow, SessionLocal, SettingRow, TaskRow, utcnow

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def fake_llm_enabled() -> bool:
    return os.getenv("PAPERCREW_FAKE_LLM", "0") == "1"


def get_setting(db, key: str, default: str = "") -> str:
    row = db.get(SettingRow, key)
    return row.value if row and row.value else default


def _append_log(run_id: int, line: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(RunRow, run_id)
        if run is not None:
            run.log = (run.log + "\n" if run.log else "") + line
            db.commit()
    finally:
        db.close()


def _finish(run_id: int, status: str, output: str = "", error: str = "") -> None:
    db = SessionLocal()
    try:
        run = db.get(RunRow, run_id)
        if run is None:
            return
        run.status = status
        run.output = output
        run.error = error
        run.finished_at = utcnow()
        task = db.get(TaskRow, run.task_id)
        if task is not None:
            task.status = "review" if status == "completed" else "in_progress"
        db.commit()
    finally:
        db.close()


def _run_fake(run_id: int, task: TaskRow, agent: AgentRow) -> None:
    _append_log(run_id, f"[demo] Crew assembled with agent '{agent.name}' ({agent.role})")
    time.sleep(0.5)
    _append_log(run_id, f"[demo] Agent working on task: {task.title}")
    time.sleep(0.5)
    output = (
        f"[demo output] {agent.name} completed '{task.title}'.\n\n"
        f"Goal considered: {agent.goal or 'n/a'}\n"
        f"Task description: {task.description or 'n/a'}\n\n"
        "This is a simulated result (PAPERCREW_FAKE_LLM=1). "
        "Set an OpenRouter API key in Settings and disable demo mode for real runs."
    )
    _append_log(run_id, "[demo] Run finished")
    _finish(run_id, "completed", output=output)


def _run_crewai(run_id: int, task: TaskRow, agent: AgentRow, api_key: str, model: str) -> None:
    from crewai import Agent, Crew, LLM, Process, Task

    llm = LLM(model=f"openrouter/{model}", api_key=api_key, base_url=OPENROUTER_BASE)
    crew_agent = Agent(
        role=agent.role,
        goal=agent.goal or f"Complete assigned tasks as {agent.role}",
        backstory=agent.backstory or f"{agent.name}, a diligent {agent.role}.",
        llm=llm,
        verbose=False,
    )
    crew_task = Task(
        description=task.description or task.title,
        expected_output=task.expected_output or "A clear, complete result for the task.",
        agent=crew_agent,
    )
    crew = Crew(
        agents=[crew_agent],
        tasks=[crew_task],
        process=Process.sequential,
        verbose=False,
        step_callback=lambda step: _append_log(run_id, f"[step] {type(step).__name__}"),
        task_callback=lambda out: _append_log(run_id, "[task] completed"),
    )
    _append_log(run_id, f"[crewai] Kickoff with model openrouter/{model}")
    result = crew.kickoff()
    _finish(run_id, "completed", output=str(result))


def _execute(run_id: int, task_id: int) -> None:
    db = SessionLocal()
    try:
        task = db.get(TaskRow, task_id)
        agent = db.get(AgentRow, task.agent_id) if task and task.agent_id else None
        api_key = get_setting(db, "openrouter_api_key", os.getenv("OPENROUTER_API_KEY", ""))
        model = (
            (agent.model if agent and agent.model else "")
            or get_setting(db, "default_model", "")
            or DEFAULT_MODEL
        )
    finally:
        db.close()

    if task is None or agent is None:
        _finish(run_id, "failed", error="Task not found or no agent assigned")
        return

    try:
        if fake_llm_enabled():
            _run_fake(run_id, task, agent)
        elif not api_key:
            _finish(
                run_id,
                "failed",
                error="No OpenRouter API key configured. Add one in Settings "
                "or enable demo mode (PAPERCREW_FAKE_LLM=1).",
            )
        else:
            _run_crewai(run_id, task, agent, api_key, model)
    except Exception as exc:  # noqa: BLE001 - surface any crew failure on the run
        _finish(run_id, "failed", error=str(exc))


def start_run(task_id: int) -> int:
    db = SessionLocal()
    try:
        run = RunRow(task_id=task_id, status="running")
        db.add(run)
        task = db.get(TaskRow, task_id)
        if task is not None:
            task.status = "in_progress"
        db.commit()
        run_id = run.id
    finally:
        db.close()

    thread = threading.Thread(target=_execute, args=(run_id, task_id), daemon=True)
    thread.start()
    return run_id
