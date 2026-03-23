---
phase: 03
plan: 02
subsystem: routing
tags: [linear, graphql, routing, project-resolution]
dependency-graph:
  requires: [03-01]
  provides: [project-aware-routing, linear-issue-creation, topic-switching]
  affects: [03-03, 05-xx]
tech-stack:
  added: []
  patterns: [4-level-resolution-chain, topic-switching-window, graphql-mutations-with-variables]
key-files:
  created:
    - engine/routing/__init__.py
    - engine/routing/project_resolver.py
    - engine/routing/linear_router.py
  modified:
    - engine/config.py
decisions:
  - id: D-0302-1
    summary: "4-level resolution priority: explicit > topic > attendee > default"
  - id: D-0302-2
    summary: "Topic switching requires 3+ consecutive mentions (avoids false positives)"
  - id: D-0302-3
    summary: "Default team ID from existing meeting-watcher hardcoded value"
metrics:
  duration: ~2 min
  completed: 2026-03-20
---

# Phase 3 Plan 2: Project-Aware Routing Summary

**One-liner:** Project resolver with 4-level priority chain and Linear issue creation with rich meeting context via GraphQL variables.

## What Was Built

### ProjectResolver (`engine/routing/project_resolver.py`)
- Resolves intents to Linear teams using 4-level priority: explicit project name > active conversation topic > attendee company > default
- In-memory team cache with 5-minute TTL to reduce API calls
- Topic switching detection using a sliding window of project mentions (3+ consecutive mentions trigger a switch)
- Auto-creation of new Linear teams for unknown clients via `teamCreate` GraphQL mutation
- Fuzzy cache lookup (case-insensitive, substring matching)

### LinearRouter (`engine/routing/linear_router.py`)
- Creates Linear issues routed to the correct project/team
- Issue descriptions include meeting context: speaker, meeting title, urgency, confidence, source transcript
- Action-type prefix mapping: BUILD_FEATURE -> "Build:", FIX_BUG -> "Fix:", etc.
- Urgency-to-priority mapping: now=1(urgent), soon=3(medium), later=4(low)
- Batch routing for multiple intents via `asyncio.gather`
- Falls back to `LINEAR_DEFAULT_TEAM_ID` when no project resolved

### Config Update (`engine/config.py`)
- Added `LINEAR_DEFAULT_TEAM_ID` with existing meeting-watcher default value

## Decisions Made

| ID | Decision | Rationale |
|-----|----------|-----------|
| D-0302-1 | 4-level resolution priority chain | Explicit project name is highest signal, default team is lowest — mirrors how Julian talks about projects in meetings |
| D-0302-2 | 3+ consecutive mentions for topic switch | Avoids false positives from brief project name drops; research pitfall #4 |
| D-0302-3 | Default team from meeting-watcher | Preserves backward compatibility with existing issue creation |

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Hash | Description |
|------|-------------|
| 60b4523 | feat(03-02): add ProjectResolver with 4-level project resolution |
| 711d620 | feat(03-02): add LinearRouter for project-aware issue creation |

## Verification Results

- `from routing.project_resolver import ProjectResolver` — OK
- `from routing.linear_router import LinearRouter` — OK
- Topic tracking returns None until 3 consecutive mentions — OK
- `config.LINEAR_DEFAULT_TEAM_ID` present with correct default — OK
- All GraphQL mutations use variables (no string interpolation) — OK

## Next Phase Readiness

- **03-03 can proceed:** Routing layer is complete, ready for orchestration pipeline integration
- **No blockers:** All exports (ProjectResolver, LinearRouter) are importable
- **Integration point:** Orchestrator will call `LinearRouter.route_intent()` with detected intents
