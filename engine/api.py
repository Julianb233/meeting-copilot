"""REST API endpoints for health check, state snapshots, context assembly, tasks, and intents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel as PydanticBaseModel

from context.assembler import assemble_meeting_context
from ws_handler import manager

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
