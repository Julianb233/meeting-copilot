---
phase: 02-context-engine
plan: 05
subsystem: context-engine
tags: [assembler, parallel, asyncio, pydantic, fastapi]

dependency_graph:
  requires: ["02-01", "02-02", "02-03", "02-04"]
  provides: ["unified-context-assembly", "context-api-endpoint", "classifier-prompt"]
  affects: ["03-intent-orchestration", "03-01", "03-02"]

tech_stack:
  added: []
  patterns: ["two-phase-parallel-fanout", "graceful-partial-failure", "gather-return-exceptions"]

file_tracking:
  key_files:
    created:
      - engine/context/assembler.py
    modified:
      - engine/context/__init__.py
      - engine/api.py
      - engine/models.py

decisions:
  - id: D-0205-1
    decision: "Two-phase fan-out: identity+history parallel, then linear+profiles parallel"
    rationale: "Linear lookup needs company name from identity resolution"
  - id: D-0205-2
    decision: "Models defined in assembler.py rather than separate context/models.py"
    rationale: "Existing loaders define models in their own modules; assembler adds AttendeeContext and UnifiedMeetingContext alongside its logic"

metrics:
  duration: "2.6 min"
  completed: "2026-03-20"
---

# Phase 2 Plan 5: Context Assembler Summary

**One-liner:** Two-phase parallel assembler merging contacts, Fireflies, Linear, and client profiles into unified LLM-ready context

## What Was Done

### Task 1: Context assembler with parallel fan-out
Created `engine/context/assembler.py` with:
- `assemble_meeting_context(emails, meeting_title, display_names)` async function
- Phase A: resolves identities and fetches Fireflies history in parallel via `asyncio.gather`
- Phase B: fetches Linear projects and client profiles in parallel (needs company from Phase A)
- `UnifiedMeetingContext` and `AttendeeContext` Pydantic models
- `to_classifier_prompt()` produces readable LLM-ready text
- Partial failure handling: any loader exception captured in `errors` list, not raised
- CLI entry point: `python -m context.assembler sean@hafniafin.com`

Updated `engine/context/__init__.py` with convenience exports for all models and the assembly function.

### Task 2: REST endpoint for context testing
- Added `POST /api/context` endpoint to `engine/api.py`
- Accepts `{emails, meeting_title, display_names}` and returns assembled context JSON
- Added `rich_context` field to `MeetingContext` in `engine/models.py` for future WebSocket integration
- Verified no regression on `/api/health` and `/api/state` endpoints

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adapted imports to actual module structure**
- Plan referenced `context.models` for shared types but models live in their respective modules
- Fixed: imported `AttendeeIdentity` from `context.contacts`, `TranscriptSummary` from `context.fireflies`, etc.

**2. [Rule 3 - Blocking] Adapted function signatures to actual implementations**
- Plan assumed `resolve_attendees(emails, display_names)` but actual signature is `resolve_attendees(emails)`
- Plan assumed `fetch_linear_projects(company_name, email)` but actual signature is `fetch_linear_projects(company_name)`
- Plan assumed `load_client_profile` was sync (needing `asyncio.to_thread`) but it is already async
- Fixed: used actual signatures from the existing modules

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0205-1 | Two-phase fan-out: A(identity+history) then B(linear+profiles) | Linear needs company from identity; Fireflies uses email directly so can parallelize with identity |
| D-0205-2 | Models in assembler.py not separate context/models.py | Consistent with existing pattern where each module defines its own models |

## Verification Results

- Import check: `from context.assembler import assemble_meeting_context` -- OK
- CLI test: `python -m context.assembler sean@hafniafin.com` -- produces full JSON + classifier prompt
- Engine startup: `uvicorn main:app --port 8901` -- starts cleanly
- POST /api/context endpoint: returns unified context with identity + profile data
- GET /api/health: still returns OK (no regression)
- Partial failures handled: Fireflies 500 error captured gracefully, assembly continues

## Next Phase Readiness

Phase 2 context engine is now complete. The unified context object is ready for:
- Phase 3 intent classification (classifier prompt via `to_classifier_prompt()`)
- Phase 3 orchestration (full context available via `assemble_meeting_context()`)
- Panel integration (via POST /api/context for testing, rich_context field for WebSocket)
