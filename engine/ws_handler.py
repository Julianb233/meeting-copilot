"""WebSocket connection manager and message handler."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

from models import EngineConnectionAck, EnginePong, MeetingState

logger = logging.getLogger("copilot.ws")


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.state = MeetingState()

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

            elif msg_type == "quick_action":
                action = message.get("action", "")
                logger.info(f"Quick action received: {action}")
                # TODO: Route to task orchestrator in Phase 3

            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {data[:100]}")


manager = ConnectionManager()
