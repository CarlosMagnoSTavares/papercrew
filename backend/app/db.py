"""Database setup and ORM models (SQLite + SQLAlchemy 2.0).

Everything a company owns (agents, tasks, goals, plans, routines, hires, chat,
events) carries a company_id so several companies can run side by side.
Runs, comments and skills inherit their company through their parent row.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Float, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DB_PATH = os.getenv(
    "PAPERCREW_DB", str(Path(__file__).resolve().parent.parent / "papercrew.db")
)
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    mission: Mapped[str] = mapped_column(Text, default="")
    default_model: Mapped[str] = mapped_column(String(200), default="")
    monthly_budget: Mapped[float] = mapped_column(Float, default=0.0)
    archived: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=0)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text, default="")
    backstory: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    specialty: Mapped[str] = mapped_column(String(120), default="")
    is_ceo: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=0)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    expected_output: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    depends_on: Mapped[str] = mapped_column(String(200), default="")  # csv of task ids
    crew_mode: Mapped[str] = mapped_column(String(20), default="solo")  # solo|hierarchical
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    due_date: Mapped[str] = mapped_column(String(40), default="")
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id"), nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")  # from last rejection
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    status: Mapped[str] = mapped_column(String(20), default="running")
    output: Mapped[str] = mapped_column(Text, default="")
    log: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tokens_saved: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[str] = mapped_column(String(40), default=utcnow)
    finished_at: Mapped[str] = mapped_column(String(40), default="")


class CommentRow(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    author: Mapped[str] = mapped_column(String(120), default="You")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class RoutineRow(Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=0)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    auto_run: Mapped[int] = mapped_column(Integer, default=1)
    next_run_at: Mapped[str] = mapped_column(String(40), default=utcnow)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class SkillRow(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class GoalRow(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=0)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|achieved|paused
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    autopilot: Mapped[int] = mapped_column(Integer, default=1)
    cycle: Mapped[int] = mapped_column(Integer, default=0)  # planning iterations done
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class HireRequestRow(Base):
    __tablename__ = "hire_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=0)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text, default="")
    backstory: Mapped[str] = mapped_column(Text, default="")
    specialty: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class PlanRow(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=0)
    title: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|converted
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=0)
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class ChatMessageRow(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=0)
    role: Mapped[str] = mapped_column(String(20))  # user|ceo
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow)


class SettingRow(Base):
    """Global settings shared by every company (OpenRouter key, default model)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


def add_event(db, kind: str, message: str, company_id: int = 0) -> None:
    db.add(EventRow(kind=kind, message=message, company_id=company_id))


# --- schema upkeep ----------------------------------------------------------

SCOPED_TABLES = (
    "agents", "tasks", "goals", "plans", "routines",
    "hire_requests", "events", "chat_messages",
)


def _migrate() -> None:
    """Add company_id to installs created before multi-company support and
    adopt their orphan rows into a company built from the old settings."""
    with engine.begin() as conn:
        existing = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        adopted_any = False
        for table in SCOPED_TABLES:
            if table not in existing:
                continue
            columns = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if "company_id" not in columns:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN company_id INTEGER DEFAULT 0"))
                adopted_any = True

        if not adopted_any or "companies" not in existing:
            return
        orphans = conn.execute(text("SELECT COUNT(*) FROM agents WHERE company_id = 0")).scalar()
        if not orphans:
            return
        name = conn.execute(
            text("SELECT value FROM settings WHERE key = 'company_name'")
        ).scalar() or "My Company"
        mission = conn.execute(
            text("SELECT value FROM settings WHERE key = 'company_mission'")
        ).scalar() or ""
        conn.execute(
            text("INSERT INTO companies (name, mission, default_model, monthly_budget, "
                 "archived, created_at) VALUES (:n, :m, '', 0, 0, :t)"),
            {"n": name, "m": mission, "t": utcnow()},
        )
        company_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
        for table in SCOPED_TABLES:
            if table in existing:
                conn.execute(
                    text(f"UPDATE {table} SET company_id = :cid WHERE company_id = 0"),
                    {"cid": company_id},
                )


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
