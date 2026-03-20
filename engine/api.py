"""REST API endpoints for health check, state snapshots, context assembly, tasks, and intents."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel as PydanticBaseModel

from context.assembler import assemble_meeting_context
from intelligence.followup_email import draft_followup_email, send_followup_email
from intelligence.summary_generator import generate_meeting_summary
from intent.models import Intent
from ws_handler import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class ContextRequest(PydanticBaseModel):
    """Request body for POST /api/context."""

    emails: list[str]
    meeting_title: str | None = None
    display_names: dict[str, str] | None = None


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "meeting-copilot-engine",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connections": len(manager.active_connections),
    }


@router.get("/state")
async def get_state() -> dict:
    return manager.state.model_dump(mode="json")


@router.post("/context")
async def load_context(body: ContextRequest) -> dict:
    """Load full attendee context for given emails. Testing/debugging endpoint."""
    ctx = await assemble_meeting_context(
        emails=body.emails,
        meeting_title=body.meeting_title,
        display_names=body.display_names,
    )
    return ctx.model_dump(mode="json")


# --- Task & Intent endpoints ---


@router.get("/tasks")
async def get_tasks() -> list[dict[str, Any]]:
    """Return all tracked tasks from the current session."""
    return [t.model_dump(mode="json") for t in manager.tracker.get_all_tasks()]


@router.get("/intents")
async def get_intents() -> list[dict[str, Any]]:
    """Return all detected intents from the current session."""
    return manager.state.intents


class ProcessRequest(PydanticBaseModel):
    """Request body for POST /api/process."""

    sentences: list[dict[str, Any]]
    meeting_title: str | None = None


@router.post("/process")
async def process_transcript(body: ProcessRequest) -> dict[str, Any]:
    """Run transcript sentences through the full intent pipeline.

    Testing endpoint -- processes sentences without requiring WebSocket.
    Returns the IntentBatch result.
    """
    batch = await manager.detector.process_sentences(
        body.sentences,
        known_projects=[],
        attendee_names=manager.state.context.attendees,
    )

    # Also run through routing/orchestration like the WebSocket path
    if batch.intents:
        await manager._process_intents(batch.intents, body.meeting_title)
        manager.state.intent_count += len(batch.intents)
        manager.state.intents.extend(
            [i.model_dump() for i in batch.intents]
        )

    return {
        "intents": [i.model_dump() for i in batch.intents],
        "classifications": [c.model_dump() for c in batch.classifications],
        "model_used": batch.model_used,
        "processing_time_ms": batch.processing_time_ms,
    }


# --- Post-meeting endpoints ---


class MeetingEndRequest(PydanticBaseModel):
    """Request body for POST /api/meeting/end."""

    meeting_title: str
    attendee_emails: list[str]
    send_followup: bool = True
    display_names: dict[str, str] | None = None


@router.post("/meeting/end")
async def meeting_end(body: MeetingEndRequest) -> dict[str, Any]:
    """Trigger post-meeting processing: summary generation and optional follow-up email.

    Assembles meeting context, extracts action items/decisions from tracked
    intents, generates a project-aware summary, and optionally sends a
    follow-up email to attendees via gws CLI.
    """
    # Assemble full meeting context
    context = await assemble_meeting_context(
        emails=body.attendee_emails,
        meeting_title=body.meeting_title,
        display_names=body.display_names,
    )

    # Convert tracked intent dicts back to Intent models
    intents: list[Intent] = []
    for raw in manager.state.intents:
        try:
            intents.append(Intent.model_validate(raw))
        except Exception as exc:
            logger.warning("Skipping malformed intent: %s", exc)

    active_project = manager.state.active_project

    # Generate project-aware summary
    summary = generate_meeting_summary(context, intents, active_project)

    # Optionally draft and send follow-up email
    followup_result: dict[str, Any] | None = None
    if body.send_followup:
        email = draft_followup_email(
            meeting_title=summary.meeting_title,
            meeting_type=summary.meeting_type,
            attendee_emails=body.attendee_emails,
            action_items=summary.action_items,
            decisions=summary.decisions,
            next_steps=summary.next_steps,
            attendee_names=body.display_names,
        )
        followup_result = await send_followup_email(email)

    return {
        "summary": summary.model_dump(),
        "followup": followup_result,
    }
