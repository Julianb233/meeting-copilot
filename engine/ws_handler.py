"""WebSocket connection manager and message handler.

Integrates the intent detection, routing, and orchestration pipeline.
Transcript sentences flow through: detect -> route -> spawn -> broadcast.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

from models import (
    AgentStatus,
    EngineAgentStatus,
    EngineConnectionAck,
    EngineIntentsDetected,
    EnginePong,
    EngineTaskUpdate,
    MeetingState,
    MeetingTask,
    TaskStatus,
)
from intent.detector import IntentDetector
from intent.models import ActionType, Intent
from routing.linear_router import LinearRouter
from orchestration.fleet_spawner import FleetSpawner
from orchestration.task_tracker import TaskTracker

logger = logging.getLogger("copilot.ws")


class ConnectionManager:
    """Manages WebSocket connections and broadcasts.

    Initializes the full intent pipeline:
    IntentDetector -> LinearRouter -> FleetSpawner -> TaskTracker
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.state = MeetingState()

        # Intent pipeline subsystems
        self.detector = IntentDetector()
        self.tracker = TaskTracker()
        self.spawner = FleetSpawner(
            self.tracker, broadcast_fn=self._broadcast_task_update
        )
        self.router = LinearRouter()

    def set_meeting_context(self, context) -> None:
        """Update manager state with assembled meeting context.

        Called by WatcherBridge after context assembly to give the manager
        access to attendee and meeting information without reaching into
        internals.
        """
        self.meeting_context = context
        # Extract attendee names for intent detection
        attendee_names: list[str] = []
        for att in getattr(context, "attendees", []):
            name = getattr(att, "name", None) or getattr(att, "display_name", None)
            if name:
                attendee_names.append(name)
        self.state.context.attendees = attendee_names
        self.state.context.title = getattr(context, "meeting_title", None)
        logger.info(
            "Meeting context set: %d attendees, title=%s",
            len(attendee_names),
            self.state.context.title,
        )

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

        # Send full state on connect (Pattern 2: Reconnection with State Sync)
        ack = EngineConnectionAck(meeting_state=self.state)
        await websocket.send_json(ack.model_dump(mode="json"))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.active_connections.remove(conn)

    async def handle_message(self, websocket: WebSocket, data: str) -> None:
        """Handle incoming message from panel."""
        try:
            message = json.loads(data)
            msg_type = message.get("type", "")

            if msg_type == "ping":
                pong = EnginePong()
                await websocket.send_json(pong.model_dump())

            elif msg_type == "transcript_chunk":
                sentences = message.get("sentences", [])
                meeting_title = message.get("meeting_title")
                if sentences:
                    asyncio.create_task(
                        self._process_transcript(sentences, meeting_title)
                    )

            elif msg_type == "quick_action":
                action = message.get("action", "")
                payload = message.get("payload", {})
                logger.info(f"Quick action received: {action}")
                # Create an intent from the quick action
                try:
                    action_type = ActionType(action)
                except ValueError:
                    action_type = ActionType.GENERAL_TASK
                intent = Intent(
                    action_type=action_type,
                    target=payload.get("target", action),
                    details=payload.get("details", f"Quick action: {action}"),
                    confidence=1.0,
                    source_text=f"Quick action button: {action}",
                    speaker="Julian",
                    requires_agent=action in ("research", "delegate", "check_domain"),
                )
                asyncio.create_task(
                    self._process_intents([intent], message.get("meeting_title"))
                )

            elif msg_type == "task_action":
                task_id = message.get("task_id", "")
                action = message.get("action", "")
                await self._handle_task_action(task_id, action)

            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {data[:100]}")

    # ------------------------------------------------------------------
    # Intent pipeline
    # ------------------------------------------------------------------

    async def _process_transcript(
        self, sentences: list[dict], meeting_title: str | None
    ) -> None:
        """Full intent pipeline: detect -> route -> spawn -> broadcast."""
        try:
            # Get known projects from state context
            known_projects: list[str] = []  # Populated from context engine in Phase 4+
            attendee_names = self.state.context.attendees

            # Stage 1+2: Detect intents
            batch = await self.detector.process_sentences(
                sentences, known_projects, attendee_names
            )

            if batch.intents:
                # Broadcast detected intents to panel first (low-latency feedback)
                msg = EngineIntentsDetected(
                    intents=[i.model_dump() for i in batch.intents],
                    model_used=batch.model_used,
                    processing_time_ms=batch.processing_time_ms,
                )
                await self.broadcast(msg.model_dump(mode="json"))

                # Update state counters
                self.state.intent_count += len(batch.intents)
                self.state.intents.extend(
                    [i.model_dump() for i in batch.intents]
                )

                # Route to Linear and spawn agents
                await self._process_intents(batch.intents, meeting_title)

            # Store transcript chunks in state
            for s in sentences:
                self.state.transcript_chunks.append(s)

        except Exception:
            logger.exception("Error processing transcript chunk")

    async def _process_intents(
        self, intents: list[Intent], meeting_title: str | None
    ) -> None:
        """Route intents to Linear and spawn agents. Shared by transcript and quick_action."""
        try:
            # Route intents to Linear (create issues)
            attendee_companies: list[str] = []  # From context engine when available
            await self.router.route_batch(
                intents, attendee_companies, meeting_title
            )

            # Spawn agents for execution-ready intents
            agent_intents = [i for i in intents if i.requires_agent]
            if agent_intents:
                tasks = await self.spawner.spawn_batch(agent_intents, meeting_title)
                self.state.task_count += len(tasks)

                for task in tasks:
                    # Broadcast task dispatched
                    update = EngineTaskUpdate(
                        task=task.model_dump(mode="json"),
                        event="dispatched",
                    )
                    await self.broadcast(update.model_dump(mode="json"))

                    # Update MeetingState tasks list
                    mt = MeetingTask(
                        id=task.id,
                        title=task.target,
                        status=TaskStatus(task.state.value),
                        agent=task.agent,
                    )
                    self.state.tasks.append(mt)

            # Broadcast updated agent status
            agent_status = self.tracker.get_agent_status()
            status_msg = EngineAgentStatus(
                agents=[AgentStatus(**a) for a in agent_status]
            )
            await self.broadcast(status_msg.model_dump(mode="json"))

        except Exception:
            logger.exception("Error processing intents")

    async def _broadcast_task_update(self, task_data: dict, event: str) -> None:
        """Callback for FleetSpawner to broadcast task state changes."""
        update = EngineTaskUpdate(task=task_data, event=event)
        await self.broadcast(update.model_dump(mode="json"))

        # Also broadcast updated agent status after task state change
        agent_status = self.tracker.get_agent_status()
        status_msg = EngineAgentStatus(
            agents=[AgentStatus(**a) for a in agent_status]
        )
        await self.broadcast(status_msg.model_dump(mode="json"))

    async def _handle_task_action(self, task_id: str, action: str) -> None:
        """Handle task_action messages (cancel/retry)."""
        if action == "cancel":
            task = self.tracker.fail_task(task_id, "Cancelled by user")
            if task:
                update = EngineTaskUpdate(
                    task=task.model_dump(mode="json"), event="failed"
                )
                await self.broadcast(update.model_dump(mode="json"))
        elif action == "retry":
            logger.info(f"Retry requested for task {task_id[:8]} (not yet implemented)")
        else:
            logger.warning(f"Unknown task action: {action}")


manager = ConnectionManager()
