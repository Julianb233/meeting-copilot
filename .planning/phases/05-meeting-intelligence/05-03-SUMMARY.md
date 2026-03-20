---
phase: 05-meeting-intelligence
plan: 03
subsystem: intelligence
tags: [followup-email, summary-generator, post-meeting, gws-cli]
dependency-graph:
  requires: [05-01, 05-02]
  provides: [followup-email-drafting, meeting-summary-generation, meeting-end-endpoint]
  affects: [06-fleet-integration]
tech-stack:
  added: []
  patterns: [subprocess-cli-integration, tone-aware-templating, intent-extraction]
key-files:
  created:
    - engine/intelligence/followup_email.py
    - engine/intelligence/summary_generator.py
  modified:
    - engine/api.py
    - engine/intelligence/prior_context.py
decisions:
  - id: D-0503-1
    decision: "Tone-based email templating — client gets professional tone, internal gets casual"
    context: "Meeting type from classifier drives email greeting, section headers, and sign-off"
  - id: D-0503-2
    decision: "gws CLI subprocess for email sending (consistent with contacts pattern)"
    context: "Reuses same GWS_BIN path and subprocess pattern from contacts.py"
metrics:
  duration: ~3 min
  completed: 2026-03-20
---

# Phase 5 Plan 3: Follow-up Email and Summary Generator Summary

Post-meeting follow-up email drafter with tone adjustment (client=professional, internal=casual) plus project-aware summary generator extracting action items, decisions, and next steps from detected intents.

## What Was Done

### Task 1: Follow-up Email Drafter and Sender
- Created `FollowupEmail` Pydantic model with to, subject, body, meeting_title, meeting_type
- `draft_followup_email()` adjusts tone based on meeting_type: professional greeting/sign-off for client, casual for internal
- Julian's emails (julian@aiacrobatics.com, julianb233@gmail.com) auto-filtered from recipients
- Empty sections (no action items, no decisions, etc.) omitted from email body
- `send_followup_email()` shells out to `gws gmail send` with 30s timeout
- Commit: `bff9b2e`

### Task 2: Summary Generator and REST Endpoint
- Created `MeetingSummary` model with structured fields for action items, decisions, next steps, topics, project context
- `generate_meeting_summary()` extracts from Intent objects: action items (GENERAL_TASK, BUILD_FEATURE, FIX_BUG, FOLLOW_UP, CREATE_ISSUE), decisions (DECISION), next steps (urgent + requires_agent)
- Topics aggregated from intent.project fields + active_project
- Project context pulled from attendee Linear projects
- POST `/api/meeting/end` endpoint triggers full pipeline: context assembly, summary generation, optional follow-up email
- Commit: `0d76ca7`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed duplicate __future__ import in prior_context.py**
- **Found during:** Task 2 (import chain triggered SyntaxError)
- **Issue:** `from __future__ import annotations` appeared twice (lines 7 and 10), causing SyntaxError
- **Fix:** Removed duplicate import on line 10
- **Files modified:** engine/intelligence/prior_context.py
- **Commit:** 0d76ca7

## Verification Results

- Client email: correct professional tone, "Follow-up:" subject, "Thank you" greeting, Julian filtered from recipients
- Internal email: casual tone, "Notes:" subject, "Hey" greeting
- Summary generator: extracts action items and decisions from Intent objects, includes project context
- API routes verified: all 7 endpoints compile including new `/api/meeting/end`
- Existing endpoints (/health, /state, /context, /tasks, /intents, /process) unchanged

## Next Phase Readiness

All Phase 5 intelligence modules (classifier, prior context, follow-up email, summary) are complete and integrated. The post-meeting pipeline is ready for end-to-end testing with live meetings.
