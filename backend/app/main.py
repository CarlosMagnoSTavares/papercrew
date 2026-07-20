"""PaperCrew API — Paperclip-style control plane, CrewAI-powered backend.

Multi-company: every company owns its crew, goals and history, and their
autopilots run side by side. Every crew is designed by the model for that
specific business — there is no built-in roster and no simulated mode.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .autopilot import start_autopilot
from .db import init_db
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


def create_app() -> FastAPI:
    app = FastAPI(title="PaperCrew", version="0.7.0")
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
start_scheduler()
start_autopilot()
app = create_app()
