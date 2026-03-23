---
phase: 02-context-engine
plan: 03
subsystem: context-engine
tags: [linear, graphql, httpx, pydantic]
dependency-graph:
  requires: [01-02]
  provides: [linear-project-loader, linear-issue-loader]
  affects: [03-intent-routing, 04-action-agents]
tech-stack:
  added: []
  patterns: [graphql-client, graceful-degradation]
key-files:
  created: []
  modified: [engine/context/linear_client.py]
decisions:
  - id: D-0203-1
    description: "Use direct `import config` pattern matching existing codebase convention"
metrics:
  duration: "2m 28s"
  completed: "2026-03-20"
---

# Phase 2 Plan 3: Linear Project Mapper Summary

**One-liner:** GraphQL client that searches Linear teams by company name and loads open issues with status, priority, and assignee.

## What Was Built

### Linear Project and Issue Loader (`engine/context/linear_client.py`)

- **LinearIssue model:** id, identifier (e.g. "ACRE-42"), title, status, priority (0-4), assignee, url, created_at
- **LinearProject model:** id, name, key, description, open_issues list, issue_count
- **`_graphql_request()` helper:** POSTs to Linear GraphQL API with bare token auth, 15s timeout
- **`fetch_linear_projects(company_name)`:** Searches teams by name, loads top 10 open issues per team sorted by priority
- **Error handling:** Missing API key returns [] with warning; timeouts, GraphQL errors, and unexpected exceptions all return [] with logging
- **CLI entry point:** `python -m context.linear_client [name]` for standalone testing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed relative import to match codebase convention**
- **Found during:** Task 1 verification
- **Issue:** Plan specified `from .. import config` (relative import) but existing codebase uses `import config` (direct import with engine/ on sys.path)
- **Fix:** Changed to `import config` matching the pattern in `engine/context/fireflies.py`
- **Files modified:** engine/context/linear_client.py
- **Commit:** cb318d5

## Verification Results

- Import test: `from context.linear_client import fetch_linear_projects, LinearProject, LinearIssue` -- PASS
- CLI execution: `python -m context.linear_client` -- PASS (returned [] with INFO log, API key was set but no "acre" teams found)
- All three exports verified present and correct types

## Commits

| Hash | Message |
|------|---------|
| cb318d5 | feat(02-03): add Linear project mapper |

## Success Criteria

- [x] CTX-03: Linear projects load for attendee's organization
- [x] CTX-04: Open Linear issues load for matched projects
- [x] RTE-03 partially: cross-reference with Linear projects works
