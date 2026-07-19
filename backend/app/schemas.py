"""Pydantic request/response schemas."""
from pydantic import BaseModel, Field

TASK_STATUSES = ("todo", "in_progress", "review", "done")


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=200)
    goal: str = ""
    backstory: str = ""
    model: str = ""


class AgentOut(AgentIn):
    id: int
    created_at: str


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    expected_output: str = ""
    status: str = "todo"
    agent_id: int | None = None


class TaskOut(TaskIn):
    id: int
    created_at: str


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    expected_output: str | None = None
    status: str | None = None
    agent_id: int | None = None


class RunOut(BaseModel):
    id: int
    task_id: int
    status: str
    output: str
    log: str
    error: str
    started_at: str
    finished_at: str


class SettingsIn(BaseModel):
    openrouter_api_key: str | None = None
    default_model: str | None = None


class SettingsOut(BaseModel):
    openrouter_api_key_set: bool
    default_model: str
    fake_llm: bool
