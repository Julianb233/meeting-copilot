---
phase: 03-intent-orchestration
plan: 04
subsystem: pipeline-integration
tags: [websocket, rest-api, intent-pipeline, broadcast, real-time, fastapi]
depends_on:
  requires: ["03-01", "03-02", "03-03"]
  provides: ["end-to-end intent pipeline wired into WebSocket and REST API"]
  affects: ["04-02", "04-03"]
tech_stack:
  added: []
  patterns: ["broadcast callback for async task status", "shared _process_intents for transcript and quick_action paths"]
key_files:
  created: []
  modified: ["engine/ws_handler.py", "engine/models.py", "engine/api.py", "engine/orchestration/fleet_spawner.py"]
decisions:
  - id: "D-0304-1"
    decision: "Broadcast intents before routing for low-latency panel feedback"
  - id: "D-0304-2"
    decision: "Pass broadcast_fn callback to FleetSpawner for async task completion broadcasts"
metrics:
  duration: "3.6 min"
  completed: "2026-03-20"
---

# Phase 3 Plan 4: Pipeline Integration Summary

**End-to-end intent pipeline wired into WebSocket handler and REST API with real-time broadcast.**

## What Was Done

### Task 1: WebSocket Message Types and Model Updates
- Added `PanelTranscriptChunk` and `PanelTaskAction` for panel -> engine communication
- Added `EngineIntentsDetected` and `EngineTaskUpdate` for engine -> panel broadcasts
- Extended `MeetingState` with `active_project`, `intent_count`, `task_count` fields
- Verified `LINEAR_DEFAULT_TEAM_ID` already present in config (from 03-02)

### Task 2: Intent Pipeline Integration
- **WebSocket handler** (`ws_handler.py`):
  - `ConnectionManager.__init__` initializes IntentDetector, TaskTracker, FleetSpawner, LinearRouter
  - `transcript_chunk` message type processes sentences through detect -> broadcast -> route -> spawn
  - `quick_action` message type creates Intent objects and routes through same pipeline
  - `task_action` message type handles cancel/retry from panel
  - `_process_transcript` runs full pipeline: detect intents, broadcast to panel, route to Linear, spawn agents
  - `_process_intents` shared logic between transcript and quick_action paths
  - `_broadcast_task_update` callback for async task completion/failure broadcasts
- **REST API** (`api.py`):
  - `GET /api/tasks` returns all tracked tasks from current session
  - `GET /api/intents` returns all detected intents from current session
  - `POST /api/process` testing endpoint for pipeline without WebSocket
- **FleetSpawner** updated to accept `broadcast_fn` callback for real-time task state broadcasts
- Existing ping/pong, health, state endpoints preserved and working

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0304-1 | Broadcast intents to panel before routing to Linear | Low-latency feedback -- panel sees intents immediately while routing/spawning happens in background |
| D-0304-2 | Pass broadcast_fn to FleetSpawner constructor | Clean callback pattern so async process completion can broadcast without circular imports |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] FleetSpawner broadcast callback**
- **Found during:** Task 2
- **Issue:** FleetSpawner._wait_for_completion needed to broadcast task state changes but had no reference to WebSocket broadcast
- **Fix:** Added `broadcast_fn` parameter to FleetSpawner constructor, called from _wait_for_completion on complete/fail/timeout
- **Files modified:** engine/orchestration/fleet_spawner.py, engine/ws_handler.py
- **Commit:** 8482298

## Verification Results

- Pipeline initialized correctly: detector, tracker, spawner, router all present on ConnectionManager
- API routes verified: /api/health, /api/state, /api/context, /api/tasks, /api/intents, /api/process
- End-to-end test: 2 sentences -> 1 intent detected -> 1 task spawned
- Engine app loads without errors: `from main import app` succeeds
- Existing WebSocket ping/pong flow preserved
- Existing REST /api/health and /api/state endpoints preserved

## Phase 3 Completion Status

All Phase 3 success criteria are now met:

1. Intent detector extracts structured intents (03-01)
2. Multi-model fallback chain with Gemini-first (03-01)
3. Intents route to correct Linear project via ProjectResolver (03-02)
4. Fleet agents spawn on execution-ready intents via FleetSpawner (03-03)
5. Agent status tracked and reported via WebSocket broadcasts (03-04)

Requirements covered: INT-02, INT-03, INT-04, RTE-01, RTE-02, ORC-01, ORC-02
