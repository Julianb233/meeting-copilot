---
phase: 06-integration-polish
plan: 03
subsystem: testing
tags: [e2e, pytest, integration-test, meeting-lifecycle]
dependency-graph:
  requires: ["06-01", "06-02"]
  provides: ["E2E test suite for full meeting pipeline"]
  affects: []
tech-stack:
  added: [pytest, pytest-asyncio]
  patterns: [mock-patching, TestClient-smoke-test, standalone-runner]
key-files:
  created:
    - engine/tests/__init__.py
    - engine/tests/test_e2e_flow.py
  modified: []
decisions:
  - id: D-0603-1
    decision: "Renamed raw test functions to run_* prefix to avoid pytest double-collection"
  - id: D-0603-2
    decision: "Mock context.assembler and intelligence.followup_email at source module path for late-import compatibility"
metrics:
  duration: "~3 min"
  completed: 2026-03-20
---

# Phase 6 Plan 3: E2E Meeting Lifecycle Test Summary

**One-liner:** Full pipeline E2E test simulating meeting_start -> transcript_chunks -> meeting_end with API smoke tests, using mocked context assembly and real intent detection via Gemini.

## What Was Built

### E2E Meeting Lifecycle Test (`engine/tests/test_e2e_flow.py`)

Two test suites in a single file, runnable both standalone and via pytest:

**1. Full Meeting Flow Test (`test_meeting_lifecycle`)**
- Simulates complete meeting lifecycle through WatcherBridge
- Phase 1: Meeting start with mocked context assembly, verifies context_loaded response, meeting_id set, meeting_type classified as "client"
- Phase 2: Two transcript batches (4 sentences each) processed through real intent detection pipeline (Gemini), verifies 8 chunks stored and >= 1 intent detected
- Phase 3: Meeting end with mocked email sending, verifies "ended" status and bridge state reset
- 11 assertion checks total

**2. REST API Smoke Test (`test_api_smoke`)**
- Tests all 7 REST endpoints via Starlette TestClient
- GET: /api/health, /api/state, /api/tasks, /api/intents
- POST: /api/context, /api/watcher/event, /api/process
- Validates response status codes (200) and response structure (correct keys, list types)
- 12 assertion checks total

### Test Data
- Realistic meeting scenario: "ACRE Project Review" with Julian and Sean
- 8 transcript sentences covering action items, decisions, follow-ups
- External attendee (sean@hafniafin.com) triggers client classification

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0603-1 | Renamed raw test functions to `run_*` prefix | pytest-asyncio auto-collects `test_*` async functions, causing double-execution |
| D-0603-2 | Patch at source module path (`context.assembler.*`) | WatcherBridge uses late imports inside methods, so patching the bridge module attribute fails |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest and pytest-asyncio not installed**
- Found during: Task 1 setup
- Fix: Installed pytest, pytest-asyncio, httpx via pip
- Impact: None, these are dev dependencies

**2. [Rule 1 - Bug] Patch path for mocked context assembly**
- Found during: Task 1 execution
- Issue: `patch("bridge.watcher_bridge.assemble_meeting_context")` failed because the function is late-imported inside `_handle_meeting_start`, not a module-level attribute
- Fix: Changed to `patch("context.assembler.assemble_meeting_context")`

**3. [Rule 1 - Bug] pytest collecting bare async functions as duplicate tests**
- Found during: Task 2 verification
- Issue: `test_full_meeting_flow` and `test_api_endpoints` were collected by pytest-asyncio in addition to the wrapper functions, causing 4 tests instead of 2
- Fix: Renamed to `run_full_meeting_flow` and `run_api_endpoints`

## Verification Results

- `python3 -m tests.test_e2e_flow`: ALL TESTS PASSED (23/23 checks)
- `python3 -m pytest tests/test_e2e_flow.py -v`: 2 passed in ~10s
- Meeting type correctly classified as "client"
- 3-4 intents detected from transcript (varies by Gemini response): build_feature, fix_bug, decision
- Summary generated with action items
- Follow-up email drafted but not sent (mocked)
- Bridge state clean after meeting end

## Commits

| Commit | Description |
|--------|-------------|
| fea3889 | test(engine): add E2E test for full meeting lifecycle |
