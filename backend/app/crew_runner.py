"""Executes a PaperCrew task through a CrewAI crew (or a fake LLM in demo mode).

Every run applies native token optimization (see token_optimizer):
- dependency outputs enter the prompt as a compressed context graph
- terse-mode style rules and a max_tokens cap bound the completion
- prompt/completion tokens and estimated savings are stored on the run
"""
import os
import threading
import time

from sqlalchemy import select

from .db import AgentRow, RunRow, SessionLocal, SettingRow, SkillRow, TaskRow, add_event, utcnow
from .token_optimizer import (
    MAX_COMPLETION_TOKENS,
    TERSE_SUFFIX,
    build_context,
    compress_text,
    dependency_ids,
    estimate_tokens,
)

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def fake_llm_enabled() -> bool:
    return os.getenv("PAPERCREW_FAKE_LLM", "0") == "1"


def get_setting(db, key: str, default: str = "") -> str:
    row = db.get(SettingRow, key)
    return row.value if row and row.value else default


def agent_skills_text(agent_id: int) -> str:
    db = SessionLocal()
    try:
        skills = db.scalars(select(SkillRow).where(SkillRow.agent_id == agent_id)).all()
        return "; ".join(f"{s.name} ({compress_text(s.description, 80)})" for s in skills)
    finally:
        db.close()


def unmet_dependencies(db, task: TaskRow) -> list[int]:
    unmet = []
    for dep_id in dependency_ids(task.depends_on):
        dep = db.get(TaskRow, dep_id)
        if dep is not None and dep.status != "done":
            unmet.append(dep_id)
    return unmet


def _append_log(run_id: int, line: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(RunRow, run_id)
        if run is not None:
            run.log = (run.log + "\n" if run.log else "") + line
            db.commit()
    finally:
        db.close()


def _finish(run_id: int, status: str, output: str = "", error: str = "", **metrics) -> None:
    db = SessionLocal()
    try:
        run = db.get(RunRow, run_id)
        if run is None:
            return
        run.status = status
        run.output = output
        run.error = error
        run.finished_at = utcnow()
        for key, value in metrics.items():
            setattr(run, key, value)
        task = db.get(TaskRow, run.task_id)
        if task is not None:
            task.status = "review" if status == "completed" else "in_progress"
            add_event(
                db,
                "run_" + status,
                f"Run #{run_id} for task '{task.title}' {status}",
            )
        db.commit()
    finally:
        db.close()


def _task_prompt(task: TaskRow, context: str) -> str:
    parts = [task.description or task.title]
    if context:
        parts.append(f"\nContext from completed dependencies (compressed):\n{context}")
    if task.feedback:
        parts.append(f"\nReviewer feedback on previous attempt — address it:\n{task.feedback}")
    return "\n".join(parts)


def _gather_context(task: TaskRow) -> tuple[str, int]:
    db = SessionLocal()
    try:
        def get_task(task_id: int):
            return db.get(TaskRow, task_id)

        def get_latest_output(task_id: int) -> str:
            run = db.scalars(
                select(RunRow)
                .where(RunRow.task_id == task_id, RunRow.status == "completed")
                .order_by(RunRow.id.desc())
            ).first()
            return run.output if run else ""

        return build_context(task, get_task, get_latest_output)
    finally:
        db.close()


def _run_fake(run_id: int, task: TaskRow, agent: AgentRow, prompt: str, saved: int) -> None:
    _append_log(run_id, f"[demo] Crew assembled — agent '{agent.name}' ({agent.role})")
    skills = agent_skills_text(agent.id)
    if skills:
        _append_log(run_id, f"[demo] Applying skills: {compress_text(skills, 200)}")
    if saved:
        _append_log(run_id, f"[optimizer] context graph compressed, ~{saved} tokens saved")
    time.sleep(0.4)
    _append_log(run_id, f"[demo] Working on: {task.title}")
    time.sleep(0.4)
    output = (
        f"[demo output] {agent.name} completed '{task.title}'.\n\n"
        f"Prompt used ({estimate_tokens(prompt)} est. tokens):\n{compress_text(prompt, 400)}\n\n"
        "Simulated result (PAPERCREW_FAKE_LLM=1). Configure an OpenRouter key for real runs."
    )
    _append_log(run_id, "[demo] Run finished")
    _finish(
        run_id,
        "completed",
        output=output,
        prompt_tokens=estimate_tokens(prompt),
        completion_tokens=estimate_tokens(output),
        tokens_saved=saved,
        cost=0.0,
    )


def _build_llm(api_key: str, model: str):
    from crewai import LLM

    return LLM(
        model=f"openrouter/{model}",
        api_key=api_key,
        base_url=OPENROUTER_BASE,
        max_tokens=MAX_COMPLETION_TOKENS,
    )


def _run_crewai(
    run_id: int, task: TaskRow, agent: AgentRow, api_key: str, model: str,
    prompt: str, saved: int,
) -> None:
    from crewai import Agent, Crew, Process, Task

    llm = _build_llm(api_key, model)

    def make_agent(row: AgentRow) -> Agent:
        skills = agent_skills_text(row.id)
        backstory = compress_text(row.backstory or f"{row.name}, diligent {row.role}.", 300)
        if skills:
            backstory += f" Skills: {compress_text(skills, 300)}"
        return Agent(
            role=row.role,
            goal=compress_text(row.goal or f"Complete assigned tasks as {row.role}", 300),
            backstory=backstory,
            llm=llm,
            verbose=False,
        )

    crew_task = Task(
        description=prompt + TERSE_SUFFIX,
        expected_output=compress_text(
            task.expected_output or "A clear, complete, concise result.", 300
        ),
        agent=None,
    )

    if task.crew_mode == "hierarchical":
        db = SessionLocal()
        try:
            workers = [
                make_agent(a)
                for a in db.scalars(select(AgentRow).where(AgentRow.is_ceo == 0)).all()
            ]
        finally:
            db.close()
        crew = Crew(
            agents=workers,
            tasks=[crew_task],
            process=Process.hierarchical,
            manager_llm=llm,
            verbose=False,
        )
        _append_log(run_id, f"[crewai] Hierarchical crew of {len(workers)} agents, model {model}")
    else:
        crew_agent = make_agent(agent)
        crew_task.agent = crew_agent
        crew = Crew(
            agents=[crew_agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=False,
        )
        _append_log(run_id, f"[crewai] Solo crew ({agent.name}), model openrouter/{model}")

    if saved:
        _append_log(run_id, f"[optimizer] context graph compressed, ~{saved} tokens saved")

    result = crew.kickoff()
    usage = getattr(crew, "usage_metrics", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or estimate_tokens(prompt)
    completion_tokens = getattr(usage, "completion_tokens", 0) or estimate_tokens(str(result))
    db = SessionLocal()
    try:
        price = float(get_setting(db, "price_per_1k_tokens", "0") or 0)
    finally:
        db.close()
    _finish(
        run_id,
        "completed",
        output=str(result),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        tokens_saved=saved,
        cost=round((prompt_tokens + completion_tokens) / 1000 * price, 6),
    )


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
        context, saved = _gather_context(task)
        prompt = _task_prompt(task, context)
        if fake_llm_enabled():
            _run_fake(run_id, task, agent, prompt, saved)
        elif not api_key:
            _finish(
                run_id,
                "failed",
                error="No OpenRouter API key configured. Add one in Settings "
                "or enable demo mode (PAPERCREW_FAKE_LLM=1).",
            )
        else:
            _run_crewai(run_id, task, agent, api_key, model, prompt, saved)
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
