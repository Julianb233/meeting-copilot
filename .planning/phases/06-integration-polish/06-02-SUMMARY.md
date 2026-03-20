---
phase: 06-integration-polish
plan: 02
subsystem: deployment
tags: [vercel, nginx, systemd, tls, deployment, vps]
dependency-graph:
  requires: [01-04, 04-04]
  provides: [panel-deployment, engine-deployment, deploy-scripts]
  affects: []
tech-stack:
  added: []
  patterns: [systemd-service, nginx-reverse-proxy, vercel-hosting, certbot-tls]
key-files:
  created: []
  modified:
    - engine/config.py
    - deploy/deploy-engine.sh
    - deploy/meeting-copilot-engine.service
    - panel/vercel.json
decisions:
  - id: D-0602-1
    decision: "Deploy script includes pre-flight validation (env, DNS, TLS) before service deployment"
    reason: "Prevents partial deployments when prerequisites are missing"
  - id: D-0602-2
    decision: "CSP frame-ancestors includes https://*.zoom.us for iframe embedding"
    reason: "Zoom embeds panel in iframe, requires explicit CSP permission"
metrics:
  duration: "3m 37s"
  completed: "2026-03-20"
---

# Phase 6 Plan 2: Vercel + VPS Deployment Summary

**One-liner:** Panel deployed to Vercel with Zoom-compatible CSP, engine deploy script enhanced with pre-flight DNS/TLS/env validation and health checks.

## What Was Done

### Task 1: Prepare deployment configs and deploy engine to VPS
- Added `REST_PORT` to `engine/config.py` for configurable REST API port
- Added `PYTHONPATH` environment to systemd service for flat imports
- Enhanced `deploy/deploy-engine.sh` from 4-step to 5-step with pre-flight validation:
  - Step 0: Check .env exists (exits with helpful message if missing)
  - DNS A record check via `dig +short`
  - TLS cert check + automatic certbot if DNS is ready
  - Step 5: Local and public health checks
- Nginx config verified correct: /ws -> 8900, /api -> 8901, /health and /state direct proxies

### Task 2: Deploy panel to Vercel
- Added `https://copilot-api.agency.dev` to CSP connect-src for REST API calls
- Added `https://*.zoom.us https://zoom.us` to frame-ancestors for Zoom iframe embedding
- Panel builds successfully with Vite
- Deployed to Vercel production: https://panel-ruddy-eight.vercel.app

### Task 3: Human verification checkpoint (needs_human)
- Full end-to-end verification requires:
  - DNS A record for copilot-api.agency.dev pointing to VPS IP
  - TLS cert via certbot after DNS propagation
  - Running deploy script on VPS: `bash deploy/deploy-engine.sh`
  - Verifying WebSocket connectivity from panel to engine

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] CSP frame-ancestors missing Zoom domains**
- **Found during:** Task 2
- **Issue:** frame-ancestors was `'self'` only, which blocks Zoom from embedding the panel in an iframe
- **Fix:** Added `https://*.zoom.us https://zoom.us` to frame-ancestors directive
- **Files modified:** panel/vercel.json

## Human Actions Required

Before the stack is fully connected:

1. **DNS**: Add A record for `copilot-api.agency.dev` pointing to VPS IP
2. **Deploy**: Run `bash /opt/agency-workspace/meeting-copilot/deploy/deploy-engine.sh` on VPS
3. **TLS**: Certbot runs automatically in deploy script if DNS is ready
4. **Env**: Ensure `engine/.env` has `PANEL_ORIGIN=https://panel-ruddy-eight.vercel.app`
5. **Verify**: `curl https://copilot-api.agency.dev/api/health` returns `{"status": "ok"}`

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 36cdc12 | Enhance engine deployment configs |
| 2 | d9f462f | Update deployment configs for panel + engine |
| 2 | (deploy) | Panel deployed to https://panel-ruddy-eight.vercel.app |

## Next Phase Readiness

- Panel is live on Vercel with correct security headers
- Engine deploy script is production-ready with validation
- Blocking: DNS record and VPS deployment needed for full connectivity
- No code blockers for Phase 6 Plan 3
