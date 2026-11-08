from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

EventKind = Literal['account', 'sharing', 'deletion', 'history', 'index']
TaskKind = Literal['ingest', 'parsing', 'cleanup', 'search', 'index']
Outcome = Literal['success', 'noop', 'rejected', 'failed', 'started']
TaskStatus = Literal['receiving', 'queued', 'running', 'completed', 'cancelled', 'failed', 'interrupted', 'ready', 'partial', 'deleted']

class AuditQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    since: int | None = Field(None, ge=0, le=253402300799)
    until: int | None = Field(None, ge=1, le=253402300799)
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0, le=1000000)

class EventQuery(AuditQuery):
    category: EventKind | None = None
    actor_id: UUID | None = None
    target_id: UUID | None = None
    outcome: Outcome | None = None

class TaskQuery(AuditQuery):
    kind: TaskKind | None = None
    status: TaskStatus | None = None
    owner_id: UUID | None = None
    document_id: UUID | None = None

class AuditEventItem(BaseModel):
    event_id: str
    category: EventKind
    actor_id: str | None
    target_id: str | None
    actor_type: Literal['user', 'cli', 'system']
    action: str
    outcome: Outcome
    code: str
    occurred_at: float

class AuditTaskItem(BaseModel):
    task_id: str
    kind: TaskKind
    owner_id: str
    document_id: str | None
    status: TaskStatus
    stage: str
    attempt: int
    progress: int | None
    error_code: str | None
    created_at: str | None
    updated_at: str | None

class AuditPage(BaseModel):
    next_offset: int | None
    scope_version: str
    since: int
    until: int

class AuditEventList(AuditPage):
    items: list[AuditEventItem]

class AuditTaskList(AuditPage):
    items: list[AuditTaskItem]
