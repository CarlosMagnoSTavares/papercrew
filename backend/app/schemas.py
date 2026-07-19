"""Pydantic request/response schemas."""
from pydantic import BaseModel, Field

TASK_STATUSES = ("todo", "in_progress", "review", "done")
CREW_MODES = ("solo", "hierarchical")


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=200)
    goal: str = ""
    backstory: str = ""
    model: str = ""
    specialty: str = ""
    is_ceo: bool = False


class AgentOut(AgentIn):
    id: int
    created_at: str


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    expected_output: str = ""
    status: str = "todo"
    agent_id: int | None = None
    depends_on: str = ""
    crew_mode: str = "solo"


class TaskOut(TaskIn):
    id: int
    feedback: str
    created_at: str


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    expected_output: str | None = None
    status: str | None = None
    agent_id: int | None = None
    depends_on: str | None = None
    crew_mode: str | None = None


class RejectIn(BaseModel):
    feedback: str = Field(min_length=1)
    rerun: bool = True


class RunOut(BaseModel):
    id: int
    task_id: int
    status: str
    output: str
    log: str
    error: str
    prompt_tokens: int
    completion_tokens: int
    tokens_saved: int
    cost: float
    started_at: str
    finished_at: str


class CommentIn(BaseModel):
    body: str = Field(min_length=1)
    author: str = "You"


class CommentOut(CommentIn):
    id: int
    task_id: int
    created_at: str


class RoutineIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    agent_id: int | None = None
    interval_minutes: int = Field(default=60, ge=1)
    enabled: bool = True
    auto_run: bool = True


class RoutineOut(RoutineIn):
    id: int
    next_run_at: str
    created_at: str


class EventOut(BaseModel):
    id: int
    kind: str
    message: str
    created_at: str


class ChatIn(BaseModel):
    message: str = Field(min_length=1)


class ChatMessageOut(BaseModel):
    id: int
    role: str
    body: str
    created_at: str


class SettingsIn(BaseModel):
    openrouter_api_key: str | None = None
    default_model: str | None = None
    company_name: str | None = None
    price_per_1k_tokens: str | None = None


class SettingsOut(BaseModel):
    openrouter_api_key_set: bool
    default_model: str
    company_name: str
    price_per_1k_tokens: str
    fake_llm: bool


class StatsOut(BaseModel):
    total_runs: int
    prompt_tokens: int
    completion_tokens: int
    tokens_saved: int
    total_cost: float
