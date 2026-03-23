"""Bridge between meeting-watcher v2 and the copilot engine.

Receives meeting_start, transcript_chunk, and meeting_end events from the
existing meeting-watcher v2 script and routes them through the full copilot
pipeline (context assembly, intent detection, routing, orchestration,
follow-up email).
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class WatcherEventType(str, Enum):
    MEETING_START = "meeting_start"
    TRANSCRIPT_CHUNK = "transcript_chunk"
    MEETING_END = "meeting_end"


class WatcherEvent(BaseModel):
    """Payload sent by meeting-watcher v2 to the copilot engine."""

    event_type: WatcherEventType
    meeting_id: str
    meeting_title: str | None = None
    attendee_emails: list[str] = Field(default_factory=list)
    sentences: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: str | None = None


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

class WatcherBridge:
    """Processes events from meeting-watcher v2 through the copilot pipeline.

    Holds a reference to the ws_handler manager (imported at call time to
    avoid circular imports) and delegates to context assembly, intent
    detection, and post-meeting processing.
    """

    def __init__(self) -> None:
        self.active_meeting_id: str | None = None
        self.meeting_context: Any = None  # UnifiedMeetingContext once loaded

    # -- helpers --

    def _get_manager(self):
        """Late-import the ConnectionManager singleton to avoid circular imports."""
        from ws_handler import manager
        return manager

    # -- main dispatch --

    async def handle_event(self, event: WatcherEvent) -> dict[str, Any]:
        """Route an incoming watcher event to the appropriate handler."""
        handlers = {
            WatcherEventType.MEETING_START: self._handle_meeting_start,
            WatcherEventType.TRANSCRIPT_CHUNK: self._handle_transcript_chunk,
            WatcherEventType.MEETING_END: self._handle_meeting_end,
        }
        handler = handlers.get(event.event_type)
        if handler is None:
            return {"status": "error", "message": f"Unknown event type: {event.event_type}"}

        try:
            return await handler(event)
        except Exception as exc:
            logger.exception("Error handling watcher event %s", event.event_type)
            return {"status": "error", "message": str(exc)}

    # -- event handlers --

    async def _handle_meeting_start(self, event: WatcherEvent) -> dict[str, Any]:
        """Assemble context for a new meeting and broadcast to panel."""
        from context.assembler import assemble_meeting_context

        self.active_meeting_id = event.meeting_id
        manager = self._get_manager()

        t0 = time.monotonic()
        ctx = await assemble_meeting_context(
            emails=event.attendee_emails,
            meeting_title=event.meeting_title,
        )
        self.meeting_context = ctx

        # Update manager state
        manager.set_meeting_context(ctx)
        manager.state.active = True
        manager.state.context.meeting_id = event.meeting_id

        # Broadcast context_loaded to connected panels
        await manager.broadcast({
            "type": "context_loaded",
            "meeting_id": event.meeting_id,
            "meeting_title": event.meeting_title,
            "attendee_count": len(event.attendee_emails),
            "load_time": ctx.load_time_seconds,
        })

        logger.info(
            "Meeting started: %s (%s attendees, %.2fs context load)",
            event.meeting_title,
            len(event.attendee_emails),
            ctx.load_time_seconds,
        )

        return {
            "status": "context_loaded",
            "meeting_id": event.meeting_id,
            "attendees": len(event.attendee_emails),
            "load_time": ctx.load_time_seconds,
        }

    async def _handle_transcript_chunk(self, event: WatcherEvent) -> dict[str, Any]:
        """Feed transcript sentences into the intent detection pipeline."""
        if self.active_meeting_id is None:
            return {
                "status": "error",
                "message": "No active meeting — send meeting_start first",
            }

        if not event.sentences:
            return {"status": "ok", "sentences": 0}

        manager = self._get_manager()
        title = event.meeting_title or (
            self.meeting_context.meeting_title if self.meeting_context else None
        )

        await manager._process_transcript(event.sentences, title)

        logger.info(
            "Processed %d sentences for meeting %s",
            len(event.sentences),
            event.meeting_id,
        )

        return {"status": "processed", "sentences": len(event.sentences)}

    async def _handle_meeting_end(self, event: WatcherEvent) -> dict[str, Any]:
        """Trigger post-meeting summary and follow-up email."""
        if self.active_meeting_id is None:
            return {"status": "ok", "message": "No active meeting to end"}

        from intelligence.summary_generator import generate_meeting_summary
        from intelligence.followup_email import draft_followup_email, send_followup_email
        from intent.models import Intent

        manager = self._get_manager()

        # Convert tracked intent dicts back to Intent models
        intents: list[Intent] = []
        for raw in manager.state.intents:
            try:
                intents.append(Intent.model_validate(raw))
            except Exception as exc:
                logger.warning("Skipping malformed intent: %s", exc)

        # Generate summary
        active_project = manager.state.active_project
        context = self.meeting_context
        if context is None:
            from context.assembler import assemble_meeting_context
            context = await assemble_meeting_context(
                emails=event.attendee_emails,
                meeting_title=event.meeting_title,
            )

        summary = generate_meeting_summary(context, intents, active_project)

        # Draft and send follow-up email
        email_sent = False
        try:
            email = draft_followup_email(
                meeting_title=summary.meeting_title,
                meeting_type=summary.meeting_type,
                attendee_emails=event.attendee_emails,
                action_items=summary.action_items,
                decisions=summary.decisions,
                next_steps=summary.next_steps,
            )
            result = await send_followup_email(email)
            email_sent = result.get("sent", False) if result else False
        except Exception as exc:
            logger.warning("Follow-up email failed: %s", exc)

        meeting_id = self.active_meeting_id

        # Reset for next meeting
        self.active_meeting_id = None
        self.meeting_context = None
        manager.state = type(manager.state)()  # fresh MeetingState

        logger.info("Meeting ended: %s (email_sent=%s)", event.meeting_title, email_sent)

        return {
            "status": "ended",
            "meeting_id": meeting_id,
            "email_sent": email_sent,
        }


if __name__ == "__main__":
    # Quick smoke test
    event = WatcherEvent(
        event_type=WatcherEventType.MEETING_START,
        meeting_id="test-123",
        meeting_title="Test Meeting",
        attendee_emails=["a@example.com"],
    )
    print(f"Event: {event.model_dump()}")
    bridge = WatcherBridge()
    print(f"Bridge active_meeting: {bridge.active_meeting_id}")
    print("WatcherBridge smoke test passed")
