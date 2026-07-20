"""PaperCrew API — Paperclip-style control plane, CrewAI-powered backend.

Multi-company: every company owns its crew, goals and history, and their
autopilots run side by side.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .autopilot import start_autopilot
from .db import AgentRow, CompanyRow, SessionLocal, init_db
from .routers import (
    agents,
    chat,
    companies,
    config,
    goals,
    hires,
    meta,
    plans,
    routines,
    runs,
    tasks,
)
from .scheduler import start_scheduler

SEED_AGENTS = [
    {
        "name": "Atlas",
        "role": "CEO / Orchestrator",
        "goal": "Break down objectives, delegate work and review results",
        "backstory": "Founder-mode operator that keeps the crew focused and shipping.",
        "specialty": "general",
        "is_ceo": 1,
    },
    {
        "name": "Nova",
        "role": "Researcher",
        "goal": "Gather accurate, well-sourced information for any topic",
        "backstory": "Curious analyst that digs deep and summarizes clearly.",
        "specialty": "research",
    },
    {
        "name": "Scribe",
        "role": "Writer",
        "goal": "Turn research and ideas into polished, structured documents",
        "backstory": "Technical writer with a knack for clarity and concision.",
        "specialty": "writing",
    },
    {
        "name": "Vector",
        "role": "Engineer",
        "goal": "Design and reason about technical solutions and code",
        "backstory": "Pragmatic engineer that favors simple, working solutions.",
        "specialty": "engineering",
    },
    {
        "name": "Prism",
        "role": "Analyst",
        "goal": "Review deliverables critically and verify quality",
        "backstory": "Detail-oriented reviewer with high standards.",
        "specialty": "analysis",
    },
]


def seed_if_empty() -> None:
    """Demo/test seeding only — real companies are built via POST /api/companies."""
    if os.getenv("PAPERCREW_SEED", "0") != "1":
        return
    db = SessionLocal()
    try:
        if db.scalars(select(CompanyRow)).first() is not None:
            return
        company = CompanyRow(name="Demo Co", mission="Seeded demo company")
        db.add(company)
        db.flush()
        for spec in SEED_AGENTS:
            db.add(AgentRow(company_id=company.id, **spec))
        db.commit()
    finally:
        db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="PaperCrew", version="0.6.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (
        companies, agents, tasks, runs, routines, chat, hires, plans, goals, meta, config
    ):
        app.include_router(module.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": "papercrew"}

    return app


init_db()
seed_if_empty()
start_scheduler()
start_autopilot()
app = create_app()
