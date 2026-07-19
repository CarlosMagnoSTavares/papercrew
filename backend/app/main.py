"""PaperCrew API — Paperclip-style frontend, CrewAI-powered backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .db import AgentRow, SessionLocal, init_db
from .routers import agents, config, runs, tasks

SEED_AGENTS = [
    {
        "name": "Atlas",
        "role": "CEO / Orchestrator",
        "goal": "Break down objectives, delegate work and review results",
        "backstory": "Founder-mode operator that keeps the crew focused and shipping.",
    },
    {
        "name": "Nova",
        "role": "Researcher",
        "goal": "Gather accurate, well-sourced information for any topic",
        "backstory": "Curious analyst that digs deep and summarizes clearly.",
    },
    {
        "name": "Scribe",
        "role": "Writer",
        "goal": "Turn research and ideas into polished, structured documents",
        "backstory": "Technical writer with a knack for clarity and concision.",
    },
]


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        if db.scalars(select(AgentRow)).first() is None:
            for spec in SEED_AGENTS:
                db.add(AgentRow(**spec))
            db.commit()
    finally:
        db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="PaperCrew", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (agents, tasks, runs, config):
        app.include_router(module.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": "papercrew"}

    return app


init_db()
seed_if_empty()
app = create_app()
