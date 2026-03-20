# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-20)

**Core value:** The meeting IS the work — copilot detects needs and executes work during the meeting, not after.
**Current focus:** Phase 2 — Context Engine

## Current Position

Phase: 2 of 6 (Context Engine)
Plan: 3 complete, others in progress
Status: In progress
Last activity: 2026-03-20 — Completed 02-04 (Client profile loader)

Progress: ████████░░ ~35%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: ~2.8 min
- Total execution time: ~16.9 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 4/4 | ~12.4 min | ~3.1 min |
| 2 | 2/? | ~4.5 min | ~2.2 min |

**Recent Trend:**
- Last 5 plans: 01-02 (engine scaffold), 01-03 (integration + deploy), 01-04 (root config + deploy), 02-04 (client profile loader)
- Trend: Fast execution, clean results

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- D-0101-1: Tailwind CSS v4 with @tailwindcss/vite plugin (no PostCSS config needed)
- D-0101-2: Biome for formatting + linting alongside ESLint
- D-0102-1: Python 3.10 target (system constraint, all deps compatible)
- D-0102-2: Use lifespan context manager over deprecated on_event
- D-0103-1: react-use-websocket for WebSocket with auto-reconnect
- D-0103-2: Zustand store actions mirror engine message types 1:1
- D-0104-1: Nginx map block for WebSocket upgrade instead of hardcoded Connection header
- D-0104-2: Separate /health and /state nginx locations proxying to REST port 8901
- D-0204-1: Use pyyaml for YAML frontmatter parsing (reliable, worth the dependency)
- D-0204-2: Search client-profiles/ before Obsidian contacts (richer data first)
- D-0204-3: Trim raw_content to 2000 chars for LLM context injection
- D-0203-1: Use direct `import config` pattern matching existing codebase convention

### Pending Todos

None yet.

### Blockers/Concerns

- Anthropic API key has zero credits (Gemini handles classification currently)
- OpenAI rate limited on current key
- Nginx domain copilot-api.agency.dev is placeholder — needs DNS A record to VPS IP

## Session Continuity

Last session: 2026-03-20 21:24 UTC
Stopped at: Completed 02-03-PLAN.md — Linear project mapper
Resume file: None
