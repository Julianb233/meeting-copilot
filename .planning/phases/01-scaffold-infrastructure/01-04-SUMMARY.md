---
phase: 01-scaffold-infrastructure
plan: 04
subsystem: infra
tags: [concurrently, nginx, systemd, deploy, env]

# Dependency graph
requires:
  - phase: 01-scaffold-infrastructure (01-01)
    provides: Panel app scaffold (Vite + React)
  - phase: 01-scaffold-infrastructure (01-02)
    provides: Python engine with dual-port architecture (WS:8900 + REST:8901)
provides:
  - Root package.json with single-command dev startup (npm run dev)
  - .env.example documenting all environment variables
  - Nginx reverse proxy config for dual-port routing
  - Systemd service for engine process management
  - One-command deploy script
affects: [deployment, engine-updates, production]

# Tech tracking
tech-stack:
  added: [concurrently]
  patterns: [root-workspace-scripts, dual-port-nginx-routing]

key-files:
  created: [package.json, package-lock.json]
  modified: [.env.example, deploy/nginx/meeting-copilot.conf, deploy/meeting-copilot-engine.service, deploy/deploy-engine.sh]

key-decisions:
  - "D-0104-1: Nginx map block for WebSocket upgrade instead of hardcoded Connection header"
  - "D-0104-2: Separate /health and /state nginx locations proxying to REST port 8901"

patterns-established:
  - "Root scripts pattern: npm run dev starts both panel + engine via concurrently"
  - "Dual-port nginx routing: /ws -> 8900, /api + /health + /state -> 8901"

# Metrics
duration: 2min
completed: 2026-03-20
---

# Phase 1 Plan 4: Root Config and Deploy Artifacts Summary

**Root package.json with concurrently for single-command dev, nginx dual-port proxy (WS:8900 + REST:8901), systemd service, and deploy script**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-20T21:18:12Z
- **Completed:** 2026-03-20T21:20:33Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Root package.json with dev/test/lint scripts covering both panel and engine
- Nginx config with proper WebSocket upgrade via map block, dual-port routing, 86400s timeout
- Systemd service for engine lifecycle management with auto-restart
- .env.example updated for dual-port architecture with all required variables

## Task Commits

Each task was committed atomically:

1. **Task 1: Root package.json, .gitignore, and .env.example** - `b42302b` (feat)
2. **Task 2: Nginx config, systemd service, and deploy script** - `20a290f` (feat)

## Files Created/Modified
- `package.json` - Root workspace config with concurrently dev scripts
- `package-lock.json` - Lock file for concurrently dependency
- `.env.example` - Updated with dual-port vars (WS_PORT, API_PORT, PANEL_ORIGIN)
- `deploy/nginx/meeting-copilot.conf` - Nginx reverse proxy with map block, dual-port routing, /health + /state locations
- `deploy/meeting-copilot-engine.service` - Systemd unit with PYTHONUNBUFFERED=1, dual-port description
- `deploy/deploy-engine.sh` - Fixed health check URL

## Decisions Made
- D-0104-1: Used nginx `map $http_upgrade` block for WebSocket Connection header instead of hardcoded "upgrade" string -- more robust for mixed HTTP/WS traffic
- D-0104-2: Added separate `/health` and `/state` nginx locations proxying to port 8901, since the REST API server doesn't use an `/api` prefix for these routes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed nginx /api proxy pointing to wrong port**
- **Found during:** Task 2
- **Issue:** Existing nginx config proxied /api to port 8900 (WebSocket port) instead of 8901 (REST port)
- **Fix:** Changed proxy_pass for /api location to http://127.0.0.1:8901
- **Files modified:** deploy/nginx/meeting-copilot.conf
- **Verification:** grep confirms 8901 for /api location
- **Committed in:** 20a290f

**2. [Rule 1 - Bug] Fixed deploy script health check URL**
- **Found during:** Task 2
- **Issue:** Deploy script used `/api/health` but the REST server serves `/health` directly (no /api prefix)
- **Fix:** Changed URL to `https://copilot-api.agency.dev/health`
- **Files modified:** deploy/deploy-engine.sh
- **Verification:** grep confirms correct URL
- **Committed in:** 20a290f

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correct routing. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 infrastructure fully complete with all 4 plans executed
- Ready for Phase 2 (Context Engine) development
- DNS A record for copilot-api.agency.dev still needed before production deployment

---
*Phase: 01-scaffold-infrastructure*
*Completed: 2026-03-20*
