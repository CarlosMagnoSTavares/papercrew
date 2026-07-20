"""Test setup.

The app has no demo mode: it always calls a real model. Tests therefore stub
the network boundary itself — `llm.call_text`, `llm.call_json` and
`crew_runner.invoke_crew` — and let every other code path (context graph,
optimizer, run bookkeeping, autopilot, budgets, scoping) run for real.

Stubs are installed at import time so background run threads see them too.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["PAPERCREW_SCHEDULER"] = "0"
os.environ["PAPERCREW_AUTOPILOT"] = "0"
os.environ["PAPERCREW_DB"] = str(
    Path(tempfile.mkdtemp(prefix="papercrew-test-")) / "test.db"
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import crew_runner, llm  # noqa: E402
from app.db import SessionLocal, SettingRow, init_db  # noqa: E402

# A key must exist for the app to work at all.
init_db()
_db = SessionLocal()
try:
    _db.merge(SettingRow(key="openrouter_api_key", value="sk-test-key"))
    _db.commit()
finally:
    _db.close()


def _team_for(mission: str, goal: str) -> dict:
    """A crew shaped by the request, mirroring what a real model returns."""
    text = f"{mission} {goal}".lower()
    crew = [
        {
            "name": "Atlas", "role": "CEO / Orchestrator", "specialty": "general",
            "is_ceo": True, "goal": "Reach the company goal", "backstory": "Operator.",
            "skills": [{"name": "Delegation", "description": "Assign work well"}],
        }
    ]
    if "market" in text or "brand" in text or "campaign" in text:
        crew.append({
            "name": "Mira", "role": "Marketing Lead", "specialty": "marketing",
            "goal": "Win attention", "backstory": "Campaign builder.",
            "skills": [{"name": "Campaign design", "description": "Plan campaigns"}],
        })
    if "revenue" in text or "financ" in text or "pricing" in text or "budget" in text:
        crew.append({
            "name": "Fisk", "role": "Finance Analyst", "specialty": "finance",
            "goal": "Make the numbers work", "backstory": "Numbers person.",
            "skills": [{"name": "Unit economics", "description": "Model margins"}],
        })
    if "developer" in text or "api" in text or "tool" in text or "docs" in text:
        crew.append({
            "name": "Vex", "role": "Engineer", "specialty": "engineering",
            "goal": "Build it", "backstory": "Ships code.",
            "skills": [{"name": "API design", "description": "Design clean APIs"}],
        })
    crew.append({
        "name": "Nova", "role": "Researcher", "specialty": "research",
        "goal": "Find the facts", "backstory": "Digs deep.",
        "skills": [{"name": "Market research", "description": "Map the landscape"}],
    })
    crew.append({
        "name": "Scribe", "role": "Writer", "specialty": "content",
        "goal": "Write it up", "backstory": "Clear writer.",
        "skills": [{"name": "Copywriting", "description": "Audience-fit writing"}],
    })
    return {
        "agents": crew,
        "initial_tasks": [
            {"title": f"Research: {goal}", "description": f"Map constraints for {goal}",
             "specialty": "research"},
            {"title": f"Produce: {goal}", "description": f"Build the deliverable for {goal}",
             "specialty": "content"},
            {"title": f"Review: {goal}", "description": f"Verify the result for {goal}",
             "specialty": "general"},
        ],
    }


def _extract(prompt: str, label: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(label):
            return line[len(label):].strip()
    return ""


def fake_call_json(prompt: str, max_tokens: int = 1500, company_id: int = 0,
                   as_list: bool = False):
    if "must staff it" in prompt:  # onboarding team design
        return _team_for(_extract(prompt, "What it does:"), _extract(prompt, "First goal:"))
    if "Propose 3 concrete new skills" in prompt:
        return [
            {"name": "Prioritization", "description": "Sequence work by impact"},
            {"name": "Concise reporting", "description": "Dense result summaries"},
        ]
    if "Is this goal fully achieved" in prompt:
        goal = _extract(prompt, "Goal:")
        return {
            "achieved": False,
            "next_tasks": [
                {"title": f"Optimize: {goal}", "description": "Improve the weakest part",
                 "specialty": "general"},
                {"title": f"Final report: {goal}", "description": "Consolidate results",
                 "specialty": "content"},
            ],
        }
    objective = _extract(prompt, "Objective:")  # CEO chat / plan conversion
    return [
        {"title": f"Research: {objective}", "description": "Gather facts",
         "specialty": "research"},
        {"title": f"Execute: {objective}", "description": "Produce the deliverable",
         "specialty": "content"},
        {"title": f"Review: {objective}", "description": "Quality-check it",
         "specialty": "general"},
    ]


def fake_call_text(prompt: str, max_tokens: int = 1024, company_id: int = 0) -> str:
    if "markdown execution plan" in prompt:
        return "# Plan\n\n## Objective\nDo the thing.\n\n## Steps\n1. Research (research)\n\n## Risks\n- Scope creep."
    return "Result."


def fake_invoke_crew(task, agent, prompt, api_key, model, log) -> crew_runner.CrewResult:
    log(f"[crewai] {agent.name} ({agent.role}) on openrouter/{model}")
    return crew_runner.CrewResult(
        output=f"{agent.name} completed '{task.title}'.\n\nPrompt was {len(prompt)} chars.",
        prompt_tokens=max(1, len(prompt) // 4),
        completion_tokens=42,
    )


llm.call_json = fake_call_json
llm.call_text = fake_call_text
crew_runner.invoke_crew = fake_invoke_crew

# Modules that imported these names directly must see the stubs too.
import app.ceo as _ceo  # noqa: E402
import app.onboarding as _onboarding  # noqa: E402

_ceo.llm = llm
_onboarding.llm = llm

# There is no seeded company any more: nothing works until one exists. Tests
# that don't send X-Company-Id fall back to this one.
_onboarding.create_company(
    "Test Co", "We test the control plane.", "Prove the platform works"
)
