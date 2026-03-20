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


class MeetingState(BaseModel):
    active: bool = False
    context: MeetingContext = Field(default_factory=MeetingContext)
    tasks: list[MeetingTask] = Field(default_factory=list)
    intents: list[dict[str, Any]] = Field(default_factory=list)
    transcript_chunks: list[dict[str, Any]] = Field(default_factory=list)
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


class EngineAgentStatus(BaseModel):
    type: str = "agent_status"
    agents: list[AgentStatus]
