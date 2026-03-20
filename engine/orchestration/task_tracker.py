"""In-memory task lifecycle tracking for fleet agent work."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

try:
    from intent.models import Intent
except ImportError:
    from engine.intent.models import Intent


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TrackedTask(BaseModel):
    id: str
    intent_action: str  # ActionType value
    target: str  # What the task acts on
    agent: Optional[str] = None  # Which fleet agent is assigned
    state: TaskState = TaskState.PENDING
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None  # Output or error message
    linear_issue_id: Optional[str] = None  # Linked Linear issue if created
    process_pid: Optional[int] = None  # PID of spawned subprocess


# Fleet agent names
FLEET_AGENTS = ["agent1", "agent2", "agent3", "agent4"]


class TaskTracker:
    """In-memory task lifecycle tracker.

    Keeps all tasks from the current meeting session. Provides
    snapshot for WebSocket broadcast and status queries.
    """

    def __init__(self, max_history: int = 50):
        self._tasks: dict[str, TrackedTask] = {}  # id -> task
        self._max_history = max_history
        self.logger = logging.getLogger("copilot.orchestration.tracker")

    def create_task(
        self, intent: Intent, agent: Optional[str] = None
    ) -> TrackedTask:
        """Create a new tracked task from an intent."""
        task_id = str(uuid.uuid4())
        task = TrackedTask(
            id=task_id,
            intent_action=intent.action_type.value,
            target=intent.target,
            agent=agent,
        )
        self._tasks[task_id] = task
        self.logger.info(
            "Created task %s: %s -> %s", task_id[:8], task.intent_action, task.target
        )
        self._trim_history()
        return task

    def start_task(
        self, task_id: str, agent: str, pid: Optional[int] = None
    ) -> Optional[TrackedTask]:
        """Mark task as running with assigned agent."""
        task = self._tasks.get(task_id)
        if task is None:
            self.logger.warning("start_task: task %s not found", task_id[:8])
            return None
        task.state = TaskState.RUNNING
        task.agent = agent
        task.started_at = datetime.now(timezone.utc)
        task.process_pid = pid
        self.logger.info("Started task %s on %s (pid=%s)", task_id[:8], agent, pid)
        return task

    def complete_task(
        self, task_id: str, result: str
    ) -> Optional[TrackedTask]:
        """Mark task as completed with result."""
        task = self._tasks.get(task_id)
        if task is None:
            self.logger.warning("complete_task: task %s not found", task_id[:8])
            return None
        task.state = TaskState.COMPLETED
        task.result = result
        task.completed_at = datetime.now(timezone.utc)
        self.logger.info("Completed task %s: %s", task_id[:8], result[:80])
        return task

    def fail_task(
        self, task_id: str, error: str
    ) -> Optional[TrackedTask]:
        """Mark task as failed with error message."""
        task = self._tasks.get(task_id)
        if task is None:
            self.logger.warning("fail_task: task %s not found", task_id[:8])
            return None
        task.state = TaskState.FAILED
        task.result = error
        task.completed_at = datetime.now(timezone.utc)
        self.logger.error("Failed task %s: %s", task_id[:8], error[:80])
        return task

    def get_task(self, task_id: str) -> Optional[TrackedTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_active_tasks(self) -> list[TrackedTask]:
        """Return tasks with state PENDING or RUNNING."""
        return [
            t
            for t in self._tasks.values()
            if t.state in (TaskState.PENDING, TaskState.RUNNING)
        ]

    def get_all_tasks(self) -> list[TrackedTask]:
        """Return all tasks sorted by created_at descending."""
        return sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )

    def get_agent_status(self) -> list[dict]:
        """Return status of each fleet agent.

        An agent is 'busy' if it has a RUNNING task, 'idle' otherwise.
        """
        # Build map of agent -> running task
        running: dict[str, str] = {}
        for task in self._tasks.values():
            if task.state == TaskState.RUNNING and task.agent:
                running[task.agent] = task.target

        return [
            {
                "name": agent,
                "status": "busy" if agent in running else "idle",
                "current_task": running.get(agent),
            }
            for agent in FLEET_AGENTS
        ]

    def snapshot(self) -> dict:
        """Return snapshot for WebSocket broadcast.

        Returns dict with active tasks, completed tasks, and agent statuses.
        """
        active = []
        completed = []
        for task in self.get_all_tasks():
            data = task.dict()
            if task.state in (TaskState.PENDING, TaskState.RUNNING):
                active.append(data)
            else:
                completed.append(data)

        return {
            "active": active,
            "completed": completed,
            "agents": self.get_agent_status(),
        }

    def _trim_history(self) -> None:
        """Remove oldest completed/failed tasks if exceeding max_history."""
        if len(self._tasks) <= self._max_history:
            return
        # Sort finished tasks by created_at, oldest first
        finished = sorted(
            [
                t
                for t in self._tasks.values()
                if t.state in (TaskState.COMPLETED, TaskState.FAILED)
            ],
            key=lambda t: t.created_at,
        )
        # Remove oldest finished until within limit
        while len(self._tasks) > self._max_history and finished:
            oldest = finished.pop(0)
            del self._tasks[oldest.id]
            self.logger.debug("Trimmed old task %s", oldest.id[:8])
