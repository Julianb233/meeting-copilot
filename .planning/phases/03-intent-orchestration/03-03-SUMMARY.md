---
phase: 03-intent-orchestration
plan: 03
subsystem: orchestration
tags: [fleet, task-tracking, subprocess, asyncio, agent-selection]

dependency-graph:
  requires: ["03-01"]
  provides: ["FleetSpawner", "TaskTracker", "TrackedTask", "agent-selection"]
  affects: ["03-04", "04-03", "05-01"]

tech-stack:
  added: []
  patterns: ["async subprocess dispatch", "in-memory task lifecycle", "specialization-based agent routing"]

key-files:
  created:
    - engine/orchestration/__init__.py
    - engine/orchestration/task_tracker.py
    - engine/orchestration/fleet_spawner.py
  modified: []

decisions:
  - id: D-0303-1
    summary: "v1 fleet dispatch via iMessage (god mac send) — proper fleet gateway in Phase 6"
  - id: D-0303-2
    summary: "Agent selection prefers idle specialists, falls back to any idle, then queues on first specialist"

metrics:
  duration: ~1 min
  completed: 2026-03-20
---

# Phase 3 Plan 3: Task Orchestration Summary

Fleet agent spawning and in-memory task lifecycle tracking via god CLI async subprocess with specialization-based agent routing.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Task tracker with lifecycle management | bcff82b | engine/orchestration/task_tracker.py |
| 2 | Fleet spawner with agent selection | c59497d | engine/orchestration/fleet_spawner.py |

## What Was Built

### TaskTracker (task_tracker.py)
- `TrackedTask` Pydantic model with full lifecycle: id, intent_action, target, agent, state, timestamps, result, linear_issue_id, process_pid
- `TaskState` enum: PENDING -> RUNNING -> COMPLETED/FAILED
- In-memory dict storage with configurable max_history (default 50)
- `create_task()` from Intent, `start_task()`, `complete_task()`, `fail_task()`
- `get_active_tasks()`, `get_all_tasks()`, `get_agent_status()` for fleet-wide view
- `snapshot()` returns `{active, completed, agents}` dict ready for WebSocket broadcast
- Auto-trims oldest completed/failed tasks when exceeding max_history

### FleetSpawner (fleet_spawner.py)
- Agent specialization map covering all 12 ActionType values
- `select_agent()` scores by: idle specialist > any idle > first specialist (queue)
- `spawn()` dispatches via `god mac send` async subprocess (non-blocking)
- Background `_wait_for_completion()` coroutine monitors process with 5min timeout
- `spawn_batch()` filters `requires_agent=True` intents and dispatches all
- Error handling for missing god binary and OS errors

## Decisions Made

1. **D-0303-1:** v1 dispatch uses iMessage notification via `god mac send`. This is intentionally simple -- proper fleet gateway with bidirectional status comes in Phase 6.
2. **D-0303-2:** Agent selection algorithm: prefer idle specialists for the action type, fall back to any idle agent, then queue on first specialist if all busy.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added missing action type specializations**
- Added `decision`, `follow_up` action types to AGENT_SPECIALIZATIONS
- These exist in ActionType enum but were missing from the routing map

**2. [Rule 3 - Blocking] Added try/except import fallback for task_tracker**
- fleet_spawner.py needed the same import pattern as other modules
- Matches codebase convention (try relative, fallback to absolute)

## Verification Results

- Package imports cleanly
- TaskTracker lifecycle: PENDING -> RUNNING -> COMPLETED/FAILED verified
- FleetSpawner selects agents by specialization with load balancing
- All subprocess calls use asyncio (non-blocking confirmed via source inspection)
- Agent status snapshot ready for WebSocket broadcast

## Next Phase Readiness

- TaskTracker.snapshot() ready for WebSocket integration in 03-04
- FleetSpawner.spawn() ready to be called from intent processing pipeline
- Agent status available for panel display in Phase 4
