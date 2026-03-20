---
phase: 1-project-scaffold-infrastructure
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - engine/pyproject.toml
  - engine/requirements.txt
  - engine/src/__init__.py
  - engine/src/main.py
  - engine/src/ws/__init__.py
  - engine/src/ws/server.py
  - engine/src/ws/protocol.py
  - engine/src/api/__init__.py
  - engine/src/api/routes.py
  - engine/src/models/__init__.py
  - engine/src/models/meeting.py
  - engine/src/models/events.py
  - engine/src/core/__init__.py
  - engine/src/core/event_bus.py
  - engine/src/core/config.py
  - engine/tests/__init__.py
  - engine/tests/test_health.py
  - engine/ruff.toml
autonomous: true

must_haves:
  truths:
    - "FastAPI server starts and responds to health check on port 8901"
    - "WebSocket endpoint accepts connections on /ws path"
    - "REST API returns JSON meeting state snapshot on /api/meeting/current"
    - "Event bus can register handlers and emit typed events"
    - "Python type checking passes with mypy"
  artifacts:
    - path: "engine/src/main.py"
      provides: "FastAPI application entry point serving both WS and REST"
      contains: "FastAPI"
    - path: "engine/src/ws/server.py"
      provides: "WebSocket connection handler"
      contains: "websocket"
    - path: "engine/src/api/routes.py"
      provides: "REST API route definitions"
      contains: "/api/meeting"
    - path: "engine/src/models/events.py"
      provides: "Pydantic models for WebSocket event protocol"
      contains: "ServerEvent"
    - path: "engine/src/models/meeting.py"
      provides: "Pydantic models for meeting domain"
      contains: "MeetingContext"
    - path: "engine/src/core/event_bus.py"
      provides: "Internal async event bus for component decoupling"
      contains: "EventBus"
  key_links:
    - from: "engine/src/main.py"
      to: "engine/src/ws/server.py"
      via: "WebSocket route registration"
      pattern: "websocket"
    - from: "engine/src/main.py"
      to: "engine/src/api/routes.py"
      via: "Router include"
      pattern: "include_router"
    - from: "engine/src/ws/server.py"
      to: "engine/src/core/event_bus.py"
      via: "Event subscription for broadcasting"
      pattern: "event_bus"
---

<objective>
Scaffold the Python copilot engine with FastAPI serving both WebSocket (path /ws) and REST API (path /api/*) from a single process. Includes Pydantic models for the WebSocket message protocol and meeting domain, an async event bus for internal decoupling, and project configuration.

Purpose: Create the backend foundation that the panel connects to for real-time events and state snapshots. Single FastAPI process with path-based routing (no separate ports) as recommended in STACK.md.

Output: A runnable FastAPI application with WebSocket endpoint, REST health/meeting endpoints, typed event models, and an async event bus.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/research/STACK.md
@.planning/research/ARCHITECTURE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create Python project structure with dependencies</name>
  <files>
    engine/pyproject.toml
    engine/requirements.txt
    engine/ruff.toml
    engine/src/__init__.py
    engine/src/core/__init__.py
    engine/src/core/config.py
    engine/src/ws/__init__.py
    engine/src/api/__init__.py
    engine/src/models/__init__.py
    engine/tests/__init__.py
  </files>
  <action>
    From the project root `/opt/agency-workspace/meeting-copilot/`:

    1. Create the engine directory structure:
       ```
       engine/
         pyproject.toml
         requirements.txt
         ruff.toml
         src/
           __init__.py
           main.py
           core/
             __init__.py
             config.py
             event_bus.py
           ws/
             __init__.py
             server.py
             protocol.py
           api/
             __init__.py
             routes.py
           models/
             __init__.py
             meeting.py
             events.py
         tests/
           __init__.py
           test_health.py
       ```

    2. Create `engine/pyproject.toml`:
       ```toml
       [project]
       name = "meeting-copilot-engine"
       version = "0.1.0"
       description = "Meeting Copilot — AI copilot engine with WebSocket + REST API"
       requires-python = ">=3.12"
       dependencies = [
           "fastapi>=0.115.0",
           "uvicorn[standard]>=0.34.0",
           "litellm>=1.0.0",
           "httpx>=0.28.0",
           "pydantic>=2.0.0",
           "python-dotenv>=1.0.0",
           "websockets>=13.0",
       ]

       [project.optional-dependencies]
       dev = [
           "ruff>=0.8.0",
           "mypy>=1.13.0",
           "pytest>=8.0.0",
           "pytest-asyncio>=0.24.0",
           "httpx",
       ]

       [tool.pytest.ini_options]
       asyncio_mode = "auto"
       testpaths = ["tests"]

       [tool.mypy]
       python_version = "3.12"
       strict = true
       warn_return_any = true
       warn_unused_configs = true
       ```

    3. Create `engine/requirements.txt` (flat list for pip install):
       ```
       fastapi>=0.115.0
       uvicorn[standard]>=0.34.0
       litellm>=1.0.0
       httpx>=0.28.0
       pydantic>=2.0.0
       python-dotenv>=1.0.0
       websockets>=13.0
       ruff>=0.8.0
       mypy>=1.13.0
       pytest>=8.0.0
       pytest-asyncio>=0.24.0
       ```

    4. Create `engine/ruff.toml`:
       ```toml
       target-version = "py312"
       line-length = 100

       [lint]
       select = ["E", "F", "I", "N", "UP", "B", "A", "SIM"]

       [format]
       quote-style = "double"
       ```

    5. Create `engine/src/core/config.py`:
       ```python
       from pydantic_settings import BaseSettings
       # NOTE: If pydantic-settings is not available, use plain pydantic BaseModel
       # and load from os.environ. Keep it simple for Phase 1.

       import os
       from dotenv import load_dotenv

       load_dotenv()


       class Settings:
           """Application settings loaded from environment variables."""

           host: str = os.getenv("ENGINE_HOST", "0.0.0.0")
           port: int = int(os.getenv("ENGINE_PORT", "8901"))
           ws_port: int = int(os.getenv("WS_PORT", "8900"))
           debug: bool = os.getenv("DEBUG", "false").lower() == "true"

           # CORS
           panel_origin: str = os.getenv("PANEL_ORIGIN", "http://localhost:3000")

           # API Keys (loaded but not used until Phase 2+)
           gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
           openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
           anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
           fireflies_api_key: str = os.getenv("FIREFLIES_API_KEY", "")
           linear_api_key: str = os.getenv("LINEAR_API_KEY", "")


       settings = Settings()
       ```

    6. Create virtual environment and install dependencies:
       ```bash
       cd engine
       python3 -m venv .venv
       source .venv/bin/activate
       pip install -r requirements.txt
       ```

    Do NOT install Django, Flask, Celery, Redis, Socket.IO, or LangChain. See STACK.md for rationale.
  </action>
  <verify>
    - `cd engine && source .venv/bin/activate && python -c "import fastapi; print(fastapi.__version__)"` prints a version
    - `cd engine && source .venv/bin/activate && python -c "import uvicorn; print('ok')"` prints ok
    - `ls engine/src/core/config.py engine/src/models/__init__.py engine/src/ws/__init__.py engine/src/api/__init__.py` all exist
    - `cd engine && source .venv/bin/activate && ruff check src/` exits with code 0
  </verify>
  <done>Python project structure created with all dependencies installed in a virtual environment. Config module loads settings from environment variables.</done>
</task>

<task type="auto">
  <name>Task 2: Implement FastAPI app with WebSocket, REST routes, event bus, and Pydantic models</name>
  <files>
    engine/src/main.py
    engine/src/ws/server.py
    engine/src/ws/protocol.py
    engine/src/api/routes.py
    engine/src/models/meeting.py
    engine/src/models/events.py
    engine/src/core/event_bus.py
    engine/tests/test_health.py
  </files>
  <action>
    1. Create `engine/src/models/events.py` — Pydantic models matching the WebSocket protocol from ARCHITECTURE.md:
       ```python
       from datetime import datetime
       from enum import Enum
       from typing import Any
       from pydantic import BaseModel, Field


       class ServerEventType(str, Enum):
           TRANSCRIPT_NEW = "transcript.new"
           TASK_CREATED = "task.created"
           TASK_STATUS = "task.status"
           AGENT_SPAWNED = "agent.spawned"
           AGENT_COMPLETED = "agent.completed"
           CONTEXT_LOADED = "context.loaded"
           DECISION_LOGGED = "decision.logged"
           MEETING_ENDED = "meeting.ended"


       class ClientEventType(str, Enum):
           ACTION_DELEGATE = "action.delegate"
           ACTION_RESEARCH = "action.research"
           ACTION_EMAIL = "action.email"
           ACTION_PROPOSAL = "action.proposal"
           ACTION_DOMAIN = "action.domain"
           ACTION_CUSTOM = "action.custom"


       class ServerEvent(BaseModel):
           type: ServerEventType
           payload: dict[str, Any] = Field(default_factory=dict)
           ts: datetime = Field(default_factory=datetime.utcnow)
           meeting_id: str = ""


       class ClientEvent(BaseModel):
           type: ClientEventType
           payload: dict[str, Any] = Field(default_factory=dict)
           ts: datetime = Field(default_factory=datetime.utcnow)
       ```

    2. Create `engine/src/models/meeting.py` — domain models matching ARCHITECTURE.md MeetingContext:
       ```python
       from datetime import datetime
       from enum import Enum
       from pydantic import BaseModel


       class MeetingType(str, Enum):
           CLIENT = "client"
           INTERNAL = "internal"
           PROSPECT = "prospect"


       class TaskStatus(str, Enum):
           PENDING = "pending"
           RUNNING = "running"
           COMPLETED = "completed"
           FAILED = "failed"


       class AgentStatus(str, Enum):
           IDLE = "idle"
           BUSY = "busy"


       class Attendee(BaseModel):
           name: str
           email: str
           company: str | None = None
           role: str | None = None


       class MeetingTask(BaseModel):
           id: str
           title: str
           status: TaskStatus = TaskStatus.PENDING
           project: str | None = None
           agent_id: str | None = None
           created_at: datetime
           completed_at: datetime | None = None
           result: str | None = None


       class Decision(BaseModel):
           id: str
           text: str
           timestamp: datetime


       class AgentInfo(BaseModel):
           id: str
           status: AgentStatus = AgentStatus.IDLE
           current_task: str | None = None


       class MeetingState(BaseModel):
           meeting_id: str | None = None
           title: str = ""
           meeting_type: MeetingType | None = None
           attendees: list[Attendee] = []
           tasks: list[MeetingTask] = []
           completed_tasks: list[MeetingTask] = []
           decisions: list[Decision] = []
           agents: list[AgentInfo] = [
               AgentInfo(id="agent1"),
               AgentInfo(id="agent2"),
               AgentInfo(id="agent3"),
               AgentInfo(id="agent4"),
           ]
           connected: bool = False
           context_loaded: bool = False
       ```

    3. Create `engine/src/core/event_bus.py` — async event bus (from ARCHITECTURE.md Pattern 2):
       ```python
       import asyncio
       import logging
       from collections import defaultdict
       from typing import Any, Callable, Coroutine

       logger = logging.getLogger(__name__)

       Handler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


       class EventBus:
           """Internal async event bus for decoupling engine components."""

           def __init__(self) -> None:
               self._handlers: dict[str, list[Handler]] = defaultdict(list)

           def on(self, event_type: str, handler: Handler) -> None:
               """Register a handler for an event type."""
               self._handlers[event_type].append(handler)

           def off(self, event_type: str, handler: Handler) -> None:
               """Remove a handler."""
               self._handlers[event_type] = [
                   h for h in self._handlers[event_type] if h != handler
               ]

           async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
               """Emit an event to all registered handlers."""
               handlers = self._handlers.get(event_type, [])
               for handler in handlers:
                   try:
                       await handler(payload)
                   except Exception:
                       logger.exception(f"Error in handler for {event_type}")


       # Singleton event bus instance
       event_bus = EventBus()
       ```

    4. Create `engine/src/ws/protocol.py` — connection manager:
       ```python
       import logging
       from fastapi import WebSocket

       logger = logging.getLogger(__name__)


       class ConnectionManager:
           """Manages active WebSocket connections."""

           def __init__(self) -> None:
               self._connections: list[WebSocket] = []

           async def connect(self, websocket: WebSocket) -> None:
               await websocket.accept()
               self._connections.append(websocket)
               logger.info(f"WebSocket connected. Total: {len(self._connections)}")

           def disconnect(self, websocket: WebSocket) -> None:
               self._connections.remove(websocket)
               logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

           async def broadcast(self, message: dict) -> None:
               """Send message to all connected clients."""
               for connection in self._connections:
                   try:
                       await connection.send_json(message)
                   except Exception:
                       logger.exception("Failed to send to WebSocket client")


       manager = ConnectionManager()
       ```

    5. Create `engine/src/ws/server.py` — WebSocket endpoint:
       ```python
       import json
       import logging
       from fastapi import APIRouter, WebSocket, WebSocketDisconnect
       from .protocol import manager
       from ..core.event_bus import event_bus
       from ..models.events import ClientEvent

       logger = logging.getLogger(__name__)
       router = APIRouter()


       @router.websocket("/ws")
       async def websocket_endpoint(websocket: WebSocket) -> None:
           await manager.connect(websocket)
           try:
               while True:
                   data = await websocket.receive_text()
                   try:
                       event = ClientEvent.model_validate_json(data)
                       logger.info(f"Received client event: {event.type}")
                       await event_bus.emit(event.type.value, event.payload)
                   except Exception:
                       logger.exception(f"Invalid client message: {data[:100]}")
           except WebSocketDisconnect:
               manager.disconnect(websocket)
       ```

    6. Create `engine/src/api/routes.py` — REST endpoints:
       ```python
       from fastapi import APIRouter
       from ..models.meeting import MeetingState

       router = APIRouter(prefix="/api")

       # In-memory meeting state (Phase 1 — single user, single meeting)
       _meeting_state = MeetingState()


       @router.get("/health")
       async def health() -> dict:
           return {"status": "ok", "service": "meeting-copilot-engine"}


       @router.get("/meeting/current")
       async def get_current_meeting() -> MeetingState:
           return _meeting_state
       ```

    7. Create `engine/src/main.py` — FastAPI app assembly:
       ```python
       import logging
       from fastapi import FastAPI
       from fastapi.middleware.cors import CORSMiddleware
       from .core.config import settings
       from .ws.server import router as ws_router
       from .api.routes import router as api_router

       logging.basicConfig(
           level=logging.DEBUG if settings.debug else logging.INFO,
           format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
       )

       app = FastAPI(
           title="Meeting Copilot Engine",
           version="0.1.0",
           description="AI copilot engine with WebSocket + REST API for Zoom companion panel",
       )

       # CORS for panel
       app.add_middleware(
           CORSMiddleware,
           allow_origins=[settings.panel_origin, "http://localhost:3000"],
           allow_credentials=True,
           allow_methods=["*"],
           allow_headers=["*"],
       )

       # Mount routes
       app.include_router(ws_router)
       app.include_router(api_router)


       if __name__ == "__main__":
           import uvicorn
           uvicorn.run(
               "src.main:app",
               host=settings.host,
               port=settings.port,
               reload=settings.debug,
           )
       ```

    8. Create `engine/tests/test_health.py`:
       ```python
       import pytest
       from httpx import AsyncClient, ASGITransport
       from src.main import app


       @pytest.mark.asyncio
       async def test_health_endpoint():
           transport = ASGITransport(app=app)
           async with AsyncClient(transport=transport, base_url="http://test") as client:
               response = await client.get("/api/health")
               assert response.status_code == 200
               data = response.json()
               assert data["status"] == "ok"
               assert data["service"] == "meeting-copilot-engine"


       @pytest.mark.asyncio
       async def test_meeting_current_endpoint():
           transport = ASGITransport(app=app)
           async with AsyncClient(transport=transport, base_url="http://test") as client:
               response = await client.get("/api/meeting/current")
               assert response.status_code == 200
               data = response.json()
               assert data["meeting_id"] is None
               assert data["tasks"] == []
               assert len(data["agents"]) == 4
       ```
  </action>
  <verify>
    - `cd engine && source .venv/bin/activate && python -m pytest tests/ -v` all tests pass
    - `cd engine && source .venv/bin/activate && python -c "from src.main import app; print(app.title)"` prints "Meeting Copilot Engine"
    - `cd engine && source .venv/bin/activate && ruff check src/` exits with code 0
    - `cd engine && source .venv/bin/activate && ruff format --check src/` exits with code 0
    - Start server temporarily: `cd engine && source .venv/bin/activate && timeout 5 uvicorn src.main:app --port 8901 || true` then check logs show startup
  </verify>
  <done>FastAPI application starts, serves /api/health returning {"status": "ok"}, serves /api/meeting/current returning empty meeting state, accepts WebSocket connections on /ws, event bus can register and emit typed events, all tests pass, ruff lint passes.</done>
</task>

</tasks>

<verification>
- `cd engine && source .venv/bin/activate && python -m pytest tests/ -v` — all tests pass
- `cd engine && source .venv/bin/activate && uvicorn src.main:app --port 8901` starts without errors
- `curl http://localhost:8901/api/health` returns `{"status": "ok", ...}`
- `curl http://localhost:8901/api/meeting/current` returns valid JSON MeetingState
- WebSocket connection test: `websocat ws://localhost:8901/ws` connects (or equivalent)
- `ruff check src/` and `ruff format --check src/` pass
</verification>

<success_criteria>
A complete Python FastAPI engine exists in `engine/` with:
1. Virtual environment with all dependencies installed
2. FastAPI app serving both WebSocket and REST from single process
3. Pydantic models for WebSocket protocol events (server + client)
4. Pydantic models for meeting domain (MeetingState, Attendee, Task, etc.)
5. Async event bus for component decoupling
6. WebSocket connection manager with broadcast capability
7. REST endpoints: /api/health, /api/meeting/current
8. Passing test suite
9. Clean ruff lint
</success_criteria>

<output>
After completion, create `.planning/phases/1-project-scaffold-infrastructure/1-02-SUMMARY.md`
</output>
