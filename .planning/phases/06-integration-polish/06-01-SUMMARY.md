---
phase: 06-integration-polish
plan: 01
subsystem: bridge
tags: [watcher, bridge, rest-api, integration]
dependency-graph:
  requires: [01-scaffold, 02-context, 03-orchestration, 05-intelligence]
  provides: [watcher-bridge, watcher-event-endpoint]
  affects: [06-02, 06-03]
tech-stack:
  added: []
  patterns: [event-bridge, late-import-circular-avoidance]
key-files:
  created:
    - engine/bridge/__init__.py
    - engine/bridge/watcher_bridge.py
  modified:
    - engine/api.py
    - engine/ws_handler.py
decisions:
  - id: D-0601-1
    decision: "Late-import ws_handler.manager in WatcherBridge to avoid circular imports"
    rationale: "bridge imports from ws_handler which imports from models; manager singleton must be resolved at call time"
  - id: D-0601-2
    decision: "set_meeting_context() method on ConnectionManager for clean state updates"
    rationale: "Gives bridge a public interface instead of reaching into manager internals"
metrics:
  duration: ~2 min
  completed: 2026-03-20
---

# Phase 6 Plan 1: Bridge Meeting-Watcher v2 to Copilot Engine Summary

**One-liner:** REST bridge receives meeting_start/transcript_chunk/meeting_end events from meeting-watcher v2 and routes them through the full copilot pipeline (context assembly, intent detection, orchestration, follow-up email).

## What Was Done

### Task 1: Create WatcherBridge module
- Created `engine/bridge/watcher_bridge.py` with:
  - `WatcherEventType` enum (meeting_start, transcript_chunk, meeting_end)
  - `WatcherEvent` Pydantic model accepting meeting_id, attendee_emails, sentences, etc.
  - `WatcherBridge` class with `handle_event()` dispatch method
- meeting_start: calls `assemble_meeting_context()`, updates manager state, broadcasts to panel
- transcript_chunk: validates active meeting, feeds sentences into `manager._process_transcript()`
- meeting_end: generates summary, drafts/sends follow-up email, resets state
- All handlers wrapped in try/except for resilience
- Commit: `77d4834`

### Task 2: Add POST /api/watcher/event endpoint
- Added `WatcherBridge` and `WatcherEvent` imports to `engine/api.py`
- Created module-level `watcher_bridge` instance
- Added `POST /api/watcher/event` endpoint that accepts WatcherEvent and delegates to bridge
- Added `set_meeting_context()` method on `ConnectionManager` in `ws_handler.py`
  - Extracts attendee names from UnifiedMeetingContext
  - Updates `manager.state.context.attendees` and `manager.state.context.title`
- All existing endpoints unchanged
- Commit: `77d4834` (same commit -- both tasks are tightly coupled)

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

- `from bridge.watcher_bridge import WatcherBridge, WatcherEvent` -- passes
- POST /api/watcher/event registered in router (confirmed in route list)
- WatcherBridge handles all three event types
- Engine starts cleanly with `uvicorn main:app`
- All existing endpoints still present: /health, /state, /context, /tasks, /intents, /process, /meeting/end

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0601-1 | Late-import manager in WatcherBridge | Avoids circular import (bridge -> ws_handler -> models) |
| D-0601-2 | set_meeting_context() on ConnectionManager | Clean public interface for external state updates |

## Next Phase Readiness

Bridge is ready for the meeting-watcher v2 to POST events. The watcher script itself needs a small addition to HTTP POST events to the engine (e.g., `urllib.request.Request("http://localhost:8901/api/watcher/event", ...)`). This is expected to be handled in 06-02 or 06-03.
