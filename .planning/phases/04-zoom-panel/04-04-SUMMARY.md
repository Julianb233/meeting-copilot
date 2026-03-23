---
phase: 04-zoom-panel
plan: 04
subsystem: deployment-integration
tags: [vercel, zoom-marketplace, deployment, owasp]
dependency-graph:
  requires: ["04-03"]
  provides: ["vercel-deployment", "zoom-marketplace-registration-instructions"]
  affects: []
tech-stack:
  added: []
  patterns: ["vercel-static-deploy", "owasp-security-headers"]
key-files:
  created: []
  modified: []
decisions:
  - id: D-0404-1
    decision: "Panel deployed to panel-ruddy-eight.vercel.app (Vercel prod alias)"
    context: "First production deploy of the Zoom Meeting Side Panel"
metrics:
  duration: "~2 min"
  completed: "2026-03-20"
---

# Phase 04 Plan 04: Zoom Marketplace Registration Summary

**One-liner:** Panel deployed to Vercel with all 4 OWASP headers; Zoom Marketplace registration pending human action.

## What Was Done

### Task 1: Deploy panel to Vercel and verify OWASP headers -- COMPLETE

Deployed the panel to Vercel production using `npx vercel --prod --yes`.

**Deployment URLs:**
- Production alias: https://panel-ruddy-eight.vercel.app
- Deployment: https://panel-4o30oazyf-ai-acrobatics.vercel.app

**OWASP Headers Verified (all 4 present):**
1. `Strict-Transport-Security: max-age=63072000; includeSubDomains`
2. `X-Content-Type-Options: nosniff`
3. `Referrer-Policy: same-origin`
4. `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://appssdk.zoom.us; ...`

**Page Content:** HTML loads correctly with React app root div, JS bundle (292.88 KB gzipped to 84.50 KB), and CSS bundle.

### Task 2: Register Zoom App on Marketplace -- REQUIRES HUMAN ACTION

Julian must register the Meeting Copilot app on the Zoom Marketplace. Steps:

1. **Go to** https://marketplace.zoom.us/ > Develop > Build App
2. **Select** "General App" > Create
3. **App name:** "Meeting Copilot" (User-managed)
4. **Basic Information:** Fill required fields (name, description, developer contact). No OAuth redirect URL needed.
5. **Features:** Enable "Zoom Apps SDK" feature. Under Surface: select "Meeting" (enables Meeting Side Panel). Client support: Desktop.
6. **Scopes:** Add `zoomapp:inmeeting`
7. **Surface Configuration:**
   - Home URL: `https://panel-ruddy-eight.vercel.app`
   - Domain Allow List:
     - `panel-ruddy-eight.vercel.app`
     - `appssdk.zoom.us`
     - `copilot-api.agency.dev`
8. **Local Test:** Go to "Local Test" page > Click "Add" to add app to your Zoom account
9. **Verify:** Open Zoom desktop client > Join/start meeting > Look for "Meeting Copilot" in Apps panel

### Task 3: Domain Allow List (covered in Task 2 instructions above)

The Domain Allow List must include three domains that mirror the CSP connect-src in `panel/vercel.json`:
- `panel-ruddy-eight.vercel.app` (the Vercel deployment)
- `appssdk.zoom.us` (Zoom Apps SDK)
- `copilot-api.agency.dev` (engine WebSocket)

## Deviations from Plan

None - Task 1 executed exactly as written. Tasks 2-3 are human-action tasks documented above.

## Verification Status

| Check | Status |
|-------|--------|
| Panel deployed to Vercel with HTTPS | PASS |
| All 4 OWASP headers present | PASS |
| Zoom app registered as General App | PENDING (human action) |
| App added to Julian's account via Local Test | PENDING (human action) |
| Panel renders inside Zoom sidebar | PENDING (human action) |

## Next Steps

Julian needs to complete the Zoom Marketplace registration (Task 2 above) to enable the panel inside the Zoom client sidebar. Until then, the panel is a standalone web app accessible at the Vercel URL.
