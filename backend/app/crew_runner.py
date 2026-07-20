"""Runs a PaperCrew task through a real CrewAI crew on OpenRouter.

Every run applies native token optimization (see token_optimizer):
- dependency outputs enter the prompt as a compressed context graph
- terse-mode style rules and a max_tokens cap bound the completion
- prompt/completion tokens and estimated savings are stored on the run

`invoke_crew` is the only function that reaches the network; tests replace it.
"""
import threading
from dataclasses import dataclass

from sqlalchemy import select

from . import llm
from .db import AgentRow, RunRow, SessionLocal, SkillRow, TaskRow, add_event, utcnow
from .token_optimizer import (
    MAX_COMPLETION_TOKENS,
    TERSE_SUFFIX,
    build_context,
    compress_text,
    dependency_ids,
    estimate_tokens,
)

DEFAULT_MODEL = llm.DEFAULT_MODEL


@dataclass
class CrewResult:
    output: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


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
                task.company_id,
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


def _build_agent(row: AgentRow, crew_llm):
    from crewai import Agent

    skills = agent_skills_text(row.id)
    backstory = compress_text(row.backstory or f"{row.name}, diligent {row.role}.", 300)
    if skills:
        backstory += f" Skills: {compress_text(skills, 300)}"
    return Agent(
        role=row.role,
        goal=compress_text(row.goal or f"Complete assigned tasks as {row.role}", 300),
        backstory=backstory,
        llm=crew_llm,
        verbose=False,
    )


def invoke_crew(task: TaskRow, agent: AgentRow, prompt: str, api_key: str, model: str,
                log) -> CrewResult:
    """Assemble and run the CrewAI crew. The only network boundary of a run."""
    from crewai import Crew, LLM, Process, Task

    crew_llm = LLM(
        model=f"openrouter/{model}",
        api_key=api_key,
        base_url=llm.OPENROUTER_BASE,
        max_tokens=MAX_COMPLETION_TOKENS,
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
                _build_agent(a, crew_llm)
                for a in db.scalars(
                    select(AgentRow).where(
                        AgentRow.is_ceo == 0, AgentRow.company_id == task.company_id
                    )
                ).all()
            ]
        finally:
            db.close()
        crew = Crew(
            agents=workers,
            tasks=[crew_task],
            process=Process.hierarchical,
            manager_llm=crew_llm,
            verbose=False,
        )
        log(f"[crewai] Hierarchical crew of {len(workers)} agents, model {model}")
    else:
        crew_agent = _build_agent(agent, crew_llm)
        crew_task.agent = crew_agent
        crew = Crew(
            agents=[crew_agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=False,
        )
        log(f"[crewai] {agent.name} ({agent.role}) on openrouter/{model}")

    result = crew.kickoff()
    usage = getattr(crew, "usage_metrics", None)
    return CrewResult(
        output=str(result),
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )


def _execute(run_id: int, task_id: int) -> None:
    db = SessionLocal()
    try:
        task = db.get(TaskRow, task_id)
        agent = db.get(AgentRow, task.agent_id) if task and task.agent_id else None
        api_key = llm.get_api_key(db)
        model = llm.resolve_model(
            db, task.company_id if task else 0, agent.model if agent else ""
        )
        price = float(llm.get_setting(db, "price_per_1k_tokens", "0") or 0)
    finally:
        db.close()

    if task is None or agent is None:
        _finish(run_id, "failed", error="Task not found or no agent assigned")
        return
    if not api_key:
        _finish(
            run_id,
            "failed",
            error="No OpenRouter API key configured. Add one in Settings "
            "(free key at https://openrouter.ai/keys).",
        )
        return

    try:
        context, saved = _gather_context(task)
        prompt = _task_prompt(task, context)

        skills = agent_skills_text(agent.id)
        if skills:
            _append_log(run_id, f"[skills] {compress_text(skills, 200)}")
        if saved:
            _append_log(run_id, f"[optimizer] context graph compressed, ~{saved} tokens saved")

        result = invoke_crew(
            task, agent, prompt, api_key, model, lambda line: _append_log(run_id, line)
        )
        prompt_tokens = result.prompt_tokens or estimate_tokens(prompt)
        completion_tokens = result.completion_tokens or estimate_tokens(result.output)
        _append_log(run_id, "[crewai] Run finished")
        _finish(
            run_id,
            "completed",
            output=result.output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_saved=saved,
            cost=round((prompt_tokens + completion_tokens) / 1000 * price, 6),
        )
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
