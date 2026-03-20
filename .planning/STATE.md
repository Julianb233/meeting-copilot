# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-20)

**Core value:** The meeting IS the work — copilot detects needs and executes work during the meeting, not after.
**Current focus:** Phase 3 + Phase 4 (parallel execution)

## Current Position

Phase: 3-4 of 6 (Intent Orchestration + Zoom Panel)
Plan: 03-01 + 03-02 + 03-03 complete, 04-01 done
Status: In progress
Last activity: 2026-03-20 — Completed 03-02 (Project-aware routing)

Progress: █████████████░ ~70%

## Performance Metrics

**Velocity:**
- Total plans completed: 14
- Average duration: ~2.4 min
- Total execution time: ~32.9 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 4/4 | ~12.4 min | ~3.1 min |
| 2 | 6/6 | ~13.1 min | ~2.2 min |
| 3 | 3/4 | ~6.4 min | ~2.1 min |
| 4 | 1/4 | ~1 min | ~1 min |

**Recent Trend:**
- Last 5 plans: 02-06 (git), 04-01 (OWASP + Zoom hook), 03-03 (orchestration), 03-01 (intent detector), 03-02 (routing)
- Trend: Fast execution, sub-minute plans for focused implementation tasks

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
- D-0202-1: try/except import pattern for config — prefers relative import, falls back to direct for runtime flexibility
- D-0202-2: Client-side participant filtering — Fireflies API has no server-side participant filter
- D-0203-1: Use direct `import config` pattern matching existing codebase convention
- D-0201-1: Shell out to gws CLI for Google Contacts (avoids OAuth credential management)
- D-0201-2: Skip default silhouette photos (no useful identity signal)
- D-0201-3: Case-insensitive email matching to confirm fuzzy search results
- D-0205-1: Two-phase fan-out: identity+history parallel, then linear+profiles parallel
- D-0205-2: Models in context/models.py as single source of truth for context types
- D-0401-1: CSP connect-src uses copilot-api.agency.dev (must mirror Zoom Marketplace Domain Allow List)
- D-0401-2: Running context check before getMeetingContext to avoid errors outside meetings
- D-0206-1: Shell out to git log via asyncio subprocess (avoids gitpython dependency)
- D-0206-2: Parse Repo(s) from client-profiles markdown using regex (table and bold formats)
- D-0303-1: v1 fleet dispatch via iMessage (god mac send) — proper fleet gateway in Phase 6
- D-0303-2: Agent selection prefers idle specialists, falls back to any idle, then queues
- D-0301-1: Gemini first in fallback chain (Anthropic has zero credits)
- D-0301-2: details field defaults to empty string for LLM null tolerance
- D-0302-1: 4-level resolution priority: explicit > topic > attendee > default
- D-0302-2: Topic switching requires 3+ consecutive mentions (avoids false positives)
- D-0302-3: Default team ID from existing meeting-watcher hardcoded value

### Pending Todos

None yet.

### Blockers/Concerns

- Anthropic API key has zero credits (Gemini handles classification currently)
- OpenAI rate limited on current key
- Nginx domain copilot-api.agency.dev is placeholder — needs DNS A record to VPS IP

## Session Continuity

Last session: 2026-03-20 21:40 UTC
Stopped at: Completed 03-02-PLAN.md — Project-aware routing
Resume file: None
