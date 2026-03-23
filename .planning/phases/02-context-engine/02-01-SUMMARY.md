---
phase: 02-context-engine
plan: 01
subsystem: context-engine
tags: [contacts, google-people-api, gws-cli, pydantic, asyncio]
dependency-graph:
  requires: [01-02]
  provides: [attendee-identity-resolver, AttendeeIdentity-model]
  affects: [02-05, 03-xx]
tech-stack:
  added: []
  patterns: [subprocess-shell-out, async-parallel-gather, graceful-fallback]
key-files:
  created:
    - engine/context/contacts.py
  modified:
    - engine/context/__init__.py
decisions:
  - id: D-0201-1
    decision: "Shell out to gws CLI rather than using google-api-python-client"
    reason: "gws already handles OAuth; avoids credentials management complexity"
  - id: D-0201-2
    decision: "Skip default silhouette photos (photos[0].default == true)"
    reason: "Default Google avatar provides no useful identity signal"
  - id: D-0201-3
    decision: "Case-insensitive email matching to confirm search results"
    reason: "gws searchContacts returns fuzzy matches; must verify exact email"
metrics:
  duration: ~2 min
  completed: 2026-03-20
---

# Phase 2 Plan 1: Attendee Identity Resolution Summary

Async Google Contacts resolver using gws CLI subprocess with parallel email lookup and graceful email_only fallback.

## What Was Built

### AttendeeIdentity Model
Pydantic model capturing attendee profile data:
- `email` (required), `name`, `company`, `title`, `phone`, `photo_url` (all optional)
- `source` field: `"google_contacts"` for resolved contacts, `"email_only"` for fallback

### resolve_attendee(email) -> AttendeeIdentity
- Shells out to `gws people people searchContacts` with JSON params
- Parses People API response, confirms exact email match (case-insensitive)
- Extracts: displayName, organization name/title, phone, photo URL
- Skips default silhouette photos
- 10-second subprocess timeout
- Returns email_only fallback on any error: timeout, bad exit code, parse failure, no match

### resolve_attendees(emails) -> list[AttendeeIdentity]
- Parallel resolution via `asyncio.gather`
- Preserves input order
- Each lookup fails independently (no all-or-nothing)

### ContactsLoader Class
OOP wrapper for pipeline integration with `.resolve(email)` and `.resolve_many(emails)` methods.

### CLI Entry Point
`python3 -m context.contacts [email]` for manual testing with both known and unknown email resolution.

## Verification Results

- Import test: `from engine.context.contacts import resolve_attendee, resolve_attendees, AttendeeIdentity` succeeds
- Known email (`julianb233@gmail.com`): Resolved to Julian Bradley, Ai Acrobatics, phone (619) 509-0699
- Unknown email (`unknown-test-12345@nowhere.com`): Returned email_only fallback, no crash
- Parallel resolution: Both emails resolved correctly via resolve_attendees

## Deviations from Plan

**1. [Rule 2 - Missing Critical] Added ContactsLoader class wrapper**
- User verification expects `from context.contacts import ContactsLoader`
- Added OOP wrapper class around resolve_attendee/resolve_attendees for pipeline integration

## Commits

| Commit | Description |
|--------|-------------|
| 72a6550 | feat(02-01): add AttendeeIdentity model and Google Contacts resolver |

## Next Phase Readiness

- AttendeeIdentity model available for context assembly (02-05)
- No new pip dependencies introduced
- CTX-01 satisfied: attendee identity loads from Google Contacts via People API
- RTE-03 partially satisfied: cross-reference attendee email with Google Contacts works
