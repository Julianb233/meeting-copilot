"""Pydantic models for WebSocket messages and meeting state."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# --- Enums ---

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QuickAction(str, Enum):
    CREATE_ISSUE = "create_issue"
    DRAFT_EMAIL = "draft_email"
    RESEARCH = "research"
    DELEGATE = "delegate"
    CHECK_DOMAIN = "check_domain"


# --- Meeting State ---

class MeetingTask(BaseModel):
    id: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    agent: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    result: str | None = None
    error: str | None = None


class AgentStatus(BaseModel):
    name: str
    status: str = "idle"
    current_task: str | None = None


class MeetingContext(BaseModel):
    meeting_id: str | None = None
    title: str | None = None
    attendees: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    rich_context: dict[str, Any] | None = None  # Populated by context assembler


class MeetingState(BaseModel):
    active: bool = False
    context: MeetingContext = Field(default_factory=MeetingContext)
    tasks: list[MeetingTask] = Field(default_factory=list)
    intents: list[dict[str, Any]] = Field(default_factory=list)
    transcript_chunks: list[dict[str, Any]] = Field(default_factory=list)
    active_project: str | None = None  # Currently detected project name
    intent_count: int = 0  # Total intents detected this session
    task_count: int = 0  # Total tasks spawned this session
    agents: list[AgentStatus] = Field(default_factory=lambda: [
        AgentStatus(name="agent1"),
        AgentStatus(name="agent2"),
        AgentStatus(name="agent3"),
        AgentStatus(name="agent4"),
    ])


# --- WebSocket Messages: Panel -> Engine ---

class PanelPing(BaseModel):
    type: str = "ping"


class PanelQuickAction(BaseModel):
    type: str = "quick_action"
    action: QuickAction
    payload: dict[str, Any] = Field(default_factory=dict)


class PanelTranscriptChunk(BaseModel):
    """Panel sends transcript sentences for intent processing."""
    type: str = "transcript_chunk"
    sentences: list[dict[str, Any]]  # Each has "text", "speaker", "speaker_name"
    meeting_title: str | None = None


class PanelTaskAction(BaseModel):
    """Panel requests action on a tracked task (cancel, retry)."""
    type: str = "task_action"
    task_id: str
    action: str  # "cancel" or "retry"


# --- WebSocket Messages: Engine -> Panel ---

class EngineConnectionAck(BaseModel):
    type: str = "connection_ack"
    meeting_state: MeetingState


class EnginePong(BaseModel):
    type: str = "pong"


class EngineMeetingStarted(BaseModel):
    type: str = "meeting_started"
    context: MeetingContext


class EngineTaskDispatched(BaseModel):
    type: str = "task_dispatched"
    task: MeetingTask


class EngineTaskCompleted(BaseModel):
    type: str = "task_completed"
    task_id: str
    result: str


class EngineTaskFailed(BaseModel):
    type: str = "task_failed"
    task_id: str
    error: str


class EngineIntentsDetected(BaseModel):
    """Broadcast when new intents are extracted from transcript."""
    type: str = "intents_detected"
    intents: list[dict[str, Any]]  # Intent.model_dump() for each
    model_used: str
    processing_time_ms: float


class EngineTaskUpdate(BaseModel):
    """Broadcast when a task changes state."""
    type: str = "task_update"
    task: dict[str, Any]  # TrackedTask.model_dump()
    event: str  # "dispatched", "started", "completed", "failed"


class EngineAgentStatus(BaseModel):
    type: str = "agent_status"
    agents: list[AgentStatus]
