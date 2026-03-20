"""Fleet agent spawning via god CLI subprocess."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

try:
    from intent.models import Intent, ActionType
except ImportError:
    from engine.intent.models import Intent, ActionType

from orchestration.task_tracker import TaskTracker, TrackedTask


# Agent specialization map — maps action types to preferred agents
AGENT_SPECIALIZATIONS: dict[str, list[str]] = {
    "build_feature": ["agent1", "agent2", "agent3"],
    "fix_bug": ["agent1", "agent2"],
    "research": ["agent3", "agent4"],
    "deploy": ["agent1"],
    "check_domain": ["agent4"],
    "create_proposal": ["agent4", "agent3"],
    "send_email": ["agent4"],
    "create_issue": ["agent3", "agent4"],
    "schedule_meeting": ["agent4"],
    "general_task": ["agent2", "agent3"],
}

GOD_BIN = "/usr/local/bin/god"


class FleetSpawner:
    """Spawns fleet agents to execute meeting intents.

    Uses ``god`` CLI via async subprocess. Agent selection
    based on action type specialization and current availability.
    """

    def __init__(self, tracker: TaskTracker):
        self.tracker = tracker
        self.logger = logging.getLogger("copilot.orchestration.spawner")

    def select_agent(self, intent: Intent) -> str:
        """Select the best available agent for an intent.

        Prefers idle agents from the specialization list for the
        intent's action type. Falls back to any idle agent, then
        to the first specialized agent (will queue).
        """
        action = intent.action_type.value
        specialists = AGENT_SPECIALIZATIONS.get(action, ["agent1"])

        # Get current agent availability
        agent_statuses = self.tracker.get_agent_status()
        idle_agents = {a["name"] for a in agent_statuses if a["status"] == "idle"}

        # Prefer idle specialist
        for agent in specialists:
            if agent in idle_agents:
                self.logger.info(
                    "Selected idle specialist %s for %s", agent, action
                )
                return agent

        # Fall back to any idle agent
        for a in agent_statuses:
            if a["status"] == "idle":
                self.logger.info(
                    "Selected idle non-specialist %s for %s", a["name"], action
                )
                return a["name"]

        # All busy — return first specialist (will queue)
        self.logger.warning(
            "All agents busy, queuing on %s for %s", specialists[0], action
        )
        return specialists[0]

    async def spawn(
        self, intent: Intent, meeting_title: Optional[str] = None
    ) -> TrackedTask:
        """Spawn a fleet agent task for an intent.

        Creates a tracked task, selects an agent, dispatches via
        ``god mac send`` (v1 iMessage dispatch), and returns
        immediately. A background coroutine monitors completion.
        """
        task = self.tracker.create_task(intent)
        agent = self.select_agent(intent)

        # Build task prompt
        title = meeting_title or "Active meeting"
        prompt = (
            f"Task from meeting: {title}\n"
            f"Action: {intent.action_type.value}\n"
            f"Target: {intent.target}\n"
            f"Details: {intent.details}\n"
            f"Urgency: {intent.urgency}\n"
            f'Source: "{intent.source_text}" — {intent.speaker}'
        )

        message = (
            f"[Meeting Copilot] Task for {agent}: "
            f"{intent.action_type.value} - {intent.target}\n"
            f"{intent.details}"
        )

        self.logger.info(
            "Spawning task %s on %s: %s - %s",
            task.id[:8],
            agent,
            intent.action_type.value,
            intent.target,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                GOD_BIN,
                "mac",
                "send",
                "+16195090699",
                message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            self.tracker.start_task(task.id, agent, pid=proc.pid)

            # Fire-and-forget: monitor process completion in background
            asyncio.create_task(self._wait_for_completion(task.id, proc))

        except FileNotFoundError:
            self.logger.error("god binary not found at %s", GOD_BIN)
            self.tracker.start_task(task.id, agent)
            self.tracker.fail_task(task.id, f"god binary not found at {GOD_BIN}")
        except OSError as exc:
            self.logger.error("Failed to spawn process: %s", exc)
            self.tracker.start_task(task.id, agent)
            self.tracker.fail_task(task.id, f"Spawn error: {exc}")

        return self.tracker.get_task(task.id) or task

    async def _wait_for_completion(
        self, task_id: str, proc: asyncio.subprocess.Process
    ) -> None:
        """Wait for spawned process to finish and update task status."""
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=300
            )

            if proc.returncode == 0:
                result = stdout.decode().strip() or "Task dispatched"
                self.tracker.complete_task(task_id, result)
                self.logger.info("Task %s completed: %s", task_id[:8], result[:80])
            else:
                error = stderr.decode().strip() or "Process failed"
                self.tracker.fail_task(task_id, error)
                self.logger.error("Task %s failed: %s", task_id[:8], error[:80])

        except asyncio.TimeoutError:
            self.tracker.fail_task(task_id, "Process timed out after 300s")
            self.logger.error("Task %s timed out", task_id[:8])
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    async def spawn_batch(
        self,
        intents: list[Intent],
        meeting_title: Optional[str] = None,
    ) -> list[TrackedTask]:
        """Spawn tasks for all agent-requiring intents.

        Filters to intents with ``requires_agent=True`` and spawns each.
        """
        tasks = []
        agent_intents = [i for i in intents if i.requires_agent]

        for intent in agent_intents:
            task = await self.spawn(intent, meeting_title)
            tasks.append(task)

        return tasks


if __name__ == "__main__":
    # Quick test: agent selection without actually spawning
    tracker = TaskTracker()
    spawner = FleetSpawner(tracker)

    test_cases = [
        (ActionType.BUILD_FEATURE, "landing page"),
        (ActionType.RESEARCH, "competitor analysis"),
        (ActionType.DEPLOY, "staging env"),
        (ActionType.CHECK_DOMAIN, "example.com"),
    ]

    for action, target in test_cases:
        intent = Intent(
            action_type=action,
            target=target,
            details=f"Test {action.value}",
            confidence=0.9,
            source_text=f"Test source for {target}",
            speaker="Julian",
            requires_agent=True,
        )
        agent = spawner.select_agent(intent)
        print(f"  {action.value:20s} -> {agent}")
