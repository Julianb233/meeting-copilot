---
phase: 05-meeting-intelligence
plan: 02
subsystem: intelligence
tags: [prior-context, meeting-history, fireflies, action-items, llm-prompt]
dependency-graph:
  requires: [02-context-engine]
  provides: [prior-meeting-context, last-discussed-prompt-text]
  affects: [05-03, 06-follow-ups]
tech-stack:
  added: []
  patterns: [lazy-import-for-circular-deps, TYPE_CHECKING-guard]
key-files:
  created:
    - engine/intelligence/prior_context.py
  modified:
    - engine/context/models.py
    - engine/context/assembler.py
decisions:
  - id: D-0502-1
    description: "Lazy import of extract_prior_context in assembler to break circular dependency"
  - id: D-0502-2
    description: "prior_context stored as dict (not Pydantic model) on UnifiedMeetingContext for JSON serialization"
  - id: D-0502-3
    description: "Only populate prior_context when total_prior_meetings > 0 (None otherwise)"
metrics:
  duration: "3m 13s"
  completed: 2026-03-20
---

# Phase 5 Plan 2: Prior Meeting Context Summary

Extract and surface "Last time you discussed..." prior meeting context from Fireflies transcript history for LLM prompt injection at meeting start.

## What Was Built

### Prior Context Extractor (engine/intelligence/prior_context.py)

- `PriorMeetingContext` Pydantic model with last_meeting_date, last_meeting_title, topics_discussed, open_action_items, and total_prior_meetings
- `to_prompt_text()` method generates human-readable summary for LLM context injection
- `extract_prior_context(attendees)` function collects TranscriptSummary objects across all attendees, deduplicates by transcript ID, sorts by date descending, extracts topics (truncated to first sentence/120 chars), and deduplicates action items by normalized text

### Integration into Context Pipeline

- Added `prior_context: dict | None` field to `UnifiedMeetingContext`
- `to_classifier_prompt()` reconstructs `PriorMeetingContext` from dict and appends prompt text
- Assembler calls `extract_prior_context()` after building attendee contexts and passes result to `UnifiedMeetingContext`

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 207cc17 | feat | Add prior meeting context extractor |
| 78d2c5c | feat | Integrate prior context into unified meeting context |
| ec52f05 | fix | Resolve circular import between prior_context and assembler |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import between prior_context and assembler**

- **Found during:** Task 2 verification
- **Issue:** `prior_context.py` imports from `context.fireflies` which triggers `context/__init__.py` which imports `assembler.py` which imports `prior_context.py` — circular
- **Fix:** Used `TYPE_CHECKING` guard for `AttendeeContext` import in prior_context.py and lazy (in-function) import of `extract_prior_context` in assembler.py
- **Files modified:** engine/intelligence/prior_context.py, engine/context/assembler.py
- **Commit:** ec52f05

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0502-1 | Lazy import in assembler | Breaks circular dependency chain without restructuring module hierarchy |
| D-0502-2 | Store prior_context as dict | Pydantic model_dump(mode="json") ensures serialization; reconstruct in to_classifier_prompt() |
| D-0502-3 | None when no prior meetings | Avoids empty object noise in JSON/prompt output |

## Verification Results

- Import from intelligence.prior_context succeeds (circular import resolved)
- PriorMeetingContext.to_prompt_text() produces human-readable prior context
- UnifiedMeetingContext.prior_context populated by assembler pipeline
- to_classifier_prompt() includes prior meeting context when available
- Empty attendee list returns "No prior meeting history found."
- Full pipeline integration verified via assemble_meeting_context()
