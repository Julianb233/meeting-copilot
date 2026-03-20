"""Pydantic models for intent detection output."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    CREATE_ISSUE = "create_issue"
    BUILD_FEATURE = "build_feature"
    FIX_BUG = "fix_bug"
    RESEARCH = "research"
    SEND_EMAIL = "send_email"
    CREATE_PROPOSAL = "create_proposal"
    SCHEDULE_MEETING = "schedule_meeting"
    CHECK_DOMAIN = "check_domain"
    DEPLOY = "deploy"
    DECISION = "decision"
    FOLLOW_UP = "follow_up"
    GENERAL_TASK = "general_task"


class Intent(BaseModel):
    action_type: ActionType
    target: str
    urgency: Literal["now", "soon", "later"] = "soon"
    project: str | None = None
    assignee: str | None = None
    details: str
    confidence: float
    source_text: str
    speaker: str
    requires_agent: bool = False


class ClassifiedSentence(BaseModel):
    index: int
    text: str
    speaker: str
    classification: str  # INFO, ACTION_ITEM, DECISION, FOLLOW_UP, QUESTION


class IntentBatch(BaseModel):
    intents: list[Intent] = Field(default_factory=list)
    classifications: list[ClassifiedSentence] = Field(default_factory=list)
    model_used: str = "keywords"
    processing_time_ms: float = 0.0
