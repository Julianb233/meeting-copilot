"""REST API endpoints for health check, state snapshots, and context assembly."""

from __future__ import annotations

from datetime import datetime, timezone

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
