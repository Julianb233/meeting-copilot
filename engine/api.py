"""REST API endpoints for health check and state snapshots."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ws_handler import manager

router = APIRouter(prefix="/api")


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
