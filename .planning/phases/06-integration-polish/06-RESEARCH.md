# Phase 6: Integration & Polish - Research

**Researched:** 2026-03-20
**Domain:** System integration (Python bridge, Vercel/VPS deployment, end-to-end testing)
**Confidence:** HIGH

## Summary

Phase 6 connects the existing meeting-watcher v2 Python script to the copilot engine via REST, deploys the panel to Vercel and engine to the Hetzner VPS, and validates the full meeting flow end-to-end. The codebase is mature -- all subsystems exist and work independently. The research focused on (a) the exact bridge interface between watcher and engine, (b) deployment infrastructure state on the VPS, and (c) strategies for simulating a full meeting flow.

The critical finding is an **nginx port mismatch**: the nginx config proxies `/api` to port 8901, but the engine serves both WebSocket AND REST on a single port (8900). This must be fixed before deployment. Additionally, the `copilot-api.agency.dev` DNS record does not exist yet and must be created, and Let's Encrypt certs must be provisioned.

**Primary recommendation:** Fix the nginx dual-port mismatch first (everything goes to 8900), then deploy engine, set up DNS + TLS, deploy panel to Vercel, and run the end-to-end test as a Python script that simulates the watcher's HTTP calls.

## Standard Stack

### Core (Already in place -- no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.12 | Engine REST + WebSocket server | Already used, handles both protocols on one port |
| uvicorn | 0.34.2 | ASGI server | Standard for FastAPI |
| httpx | >=0.28.0 | Async HTTP client (engine outbound) | Already used in context loaders |
| pydantic | >=2.0.0 | Data models/validation | Already used throughout |
| react-use-websocket | 4.13.0 | Panel WebSocket client | Already wired in useEngine hook |
| zustand | 5.0.12 | Panel state management | Already wired in meetingStore |

### Infrastructure (Already available on VPS)

| Tool | Version | Purpose | Status |
|------|---------|---------|--------|
| nginx | 1.18.0 | TLS reverse proxy | Installed, not active for copilot yet |
| certbot | installed | TLS cert provisioning | Available, no cert for copilot-api yet |
| systemd | system | Process management | Available, service file exists |
| Vercel CLI | 50.4.5 | Panel deployment | Installed at /usr/local/bin/vercel |

### Supporting (for watcher bridge -- no new deps)

| Tool | Purpose | Notes |
|------|---------|-------|
| urllib.request | Watcher HTTP calls to engine | Already used in watcher; use for bridge calls |
| json | Payload serialization | Standard library |

**No new packages need to be installed.** The bridge on the watcher side uses urllib.request (already imported). The bridge on the engine side uses existing FastAPI + Pydantic.

## Architecture Patterns

### Pattern 1: REST Bridge (Watcher -> Engine)

**What:** The meeting-watcher v2 sends HTTP POST requests to the engine's `/api/watcher/event` endpoint at key lifecycle moments. The engine processes them through the existing pipeline.

**Why REST, not WebSocket:** The watcher is a polling-based Python script with a 30-second main loop. It doesn't need bidirectional real-time communication. POST requests are simpler, more reliable, and match the watcher's synchronous architecture. The watcher already uses `urllib.request` for all API calls.

**Event flow:**
```
Watcher detects meeting (Fireflies active_meetings API)
  -> POST /api/watcher/event {event_type: "meeting_start", meeting_id, attendee_emails}
     Engine: assemble_meeting_context() -> broadcast to panel

Watcher polls transcript (every 30s)
  -> POST /api/watcher/event {event_type: "transcript_chunk", meeting_id, sentences}
     Engine: _process_transcript() -> intent detection -> routing -> panel broadcast

Meeting ends (Fireflies meeting no longer in active list)
  -> POST /api/watcher/event {event_type: "meeting_end", meeting_id}
     Engine: generate_meeting_summary() + draft_followup_email() -> send
```

### Pattern 2: Single-Port FastAPI

**What:** The engine serves BOTH WebSocket (`/ws`) and REST (`/api/*`) from a single FastAPI app on port 8900. This is standard FastAPI behavior.

**Critical:** The existing nginx config has a bug -- it proxies `/api` to port 8901 and `/ws` to port 8900. There is NO separate REST server on 8901. Both must proxy to 8900.

### Pattern 3: Panel WebSocket Reconnection

**What:** The panel's `useEngine` hook already implements auto-reconnect with exponential backoff. When the engine restarts during deployment, the panel reconnects automatically and receives full state sync via `connection_ack`.

**No changes needed** to the panel's WebSocket handling.

### Recommended Deployment Architecture
```
[Vercel: panel]  ---- wss:// ----> [nginx :443] ----> [uvicorn :8900]
                                        |                    |
                                        |--- /api/ -------->-+  (SAME port)
                                        |--- /ws  --------->-+  (SAME port)

[meeting-watcher v2]  -- POST /api/watcher/event --> [nginx :443] --> [uvicorn :8900]
   (runs on same VPS)     (or localhost:8900 directly)
```

**Watcher can call localhost:8900 directly** since it runs on the same VPS. No TLS overhead for internal calls.

### Anti-Patterns to Avoid
- **Don't create a separate watcher process for the bridge:** Modify the existing watcher in-place. Adding HTTP calls to the existing event handlers is simpler than a separate bridge process.
- **Don't use WebSocket for watcher-to-engine:** The watcher's polling loop is synchronous. Adding asyncio WebSocket would require rewriting the entire watcher.
- **Don't split the engine into two ports:** FastAPI handles both protocols on one port natively. The nginx config referencing port 8901 is wrong.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TLS certificates | Manual cert generation | `certbot --nginx` | Auto-renewal, auto-nginx-config |
| Process management | nohup/screen | systemd service (already exists) | Auto-restart, logging, boot start |
| Panel deployment | Custom build pipeline | `vercel --prod` (CLI already installed) | CDN, HTTPS, zero-config |
| WebSocket reconnection | Custom reconnect logic | react-use-websocket (already used) | Exponential backoff, state sync built in |
| CORS for Zoom iframe | Manual headers | FastAPI CORSMiddleware (already configured) | Handles preflight, credentials |

## Common Pitfalls

### Pitfall 1: Nginx Port Mismatch (CRITICAL - EXISTS NOW)

**What goes wrong:** The nginx config proxies `/api` to port 8901, but the engine only listens on port 8900. All REST API calls through nginx will get "connection refused."
**Why it happens:** The nginx config was written assuming a future dual-port architecture (WS on 8900, REST on 8901) that was never implemented.
**How to avoid:** Change all `proxy_pass` directives in `deploy/nginx/meeting-copilot.conf` to use port 8900.
**Warning signs:** `curl https://copilot-api.agency.dev/api/health` returns 502 Bad Gateway.

### Pitfall 2: DNS Not Configured

**What goes wrong:** `copilot-api.agency.dev` has no DNS A record. Certbot will fail, and the domain won't resolve.
**Why it happens:** DNS was planned but never provisioned.
**How to avoid:** Before running certbot, add an A record for `copilot-api.agency.dev` pointing to the VPS IP. Use the DNS provider's dashboard (likely Cloudflare or Namecheap based on the .dev TLD).
**Warning signs:** `dig +short copilot-api.agency.dev` returns empty.

### Pitfall 3: PANEL_ORIGIN Not Updated for Production

**What goes wrong:** CORS blocks WebSocket connections from the Vercel-deployed panel because the engine's PANEL_ORIGIN still says `http://localhost:5173`.
**Why it happens:** The .env file defaults to localhost for development.
**How to avoid:** After Vercel deployment, update `engine/.env` with `PANEL_ORIGIN=https://<vercel-domain>` and restart the engine service.
**Warning signs:** Browser console shows CORS errors on WebSocket upgrade.

### Pitfall 4: CSP frame-ancestors for Zoom

**What goes wrong:** Zoom iframe refuses to load the panel because `frame-ancestors` in vercel.json CSP doesn't include Zoom's domain.
**Why it happens:** Current CSP has `frame-ancestors 'self'` which blocks Zoom embedding.
**How to avoid:** Update CSP `frame-ancestors` to include `https://*.zoom.us` in both vercel.json and vite.config.ts.
**Warning signs:** Panel loads in browser but shows blank in Zoom client.

### Pitfall 5: Watcher State File Conflicts

**What goes wrong:** The watcher writes state to `/tmp/meeting-watcher-state.json`. If the bridge modifies watcher behavior, state file format changes can crash the running watcher.
**Why it happens:** The watcher is a long-running process with no restart coordination.
**How to avoid:** The bridge should ADD HTTP calls to the existing watcher code without changing its state format. The watcher's existing behavior (Obsidian notes, iMessage, Linear issues) should remain unchanged. The copilot engine is an ADDITIONAL consumer, not a replacement.

### Pitfall 6: Engine .env Missing on VPS

**What goes wrong:** The systemd service file uses `EnvironmentFile=/opt/agency-workspace/meeting-copilot/engine/.env`, but no .env file exists in the repo (only .env.example).
**How to avoid:** The deploy script must verify .env exists before restarting the service. Copy .env.example and populate with real keys.

## Code Examples

### Watcher Bridge Call (add to meeting-watcher.py)

```python
# Add to meeting-watcher.py -- call copilot engine on meeting events
COPILOT_ENGINE_URL = 'http://localhost:8900'

def notify_copilot(event_type, meeting_id, **kwargs):
    """Send event to copilot engine. Fire-and-forget, never crashes watcher."""
    try:
        payload = {
            'event_type': event_type,
            'meeting_id': meeting_id,
            **kwargs
        }
        req = urllib.request.Request(
            f'{COPILOT_ENGINE_URL}/api/watcher/event',
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        log(f"Copilot notified: {event_type} -> {resp.status}")
    except Exception as e:
        log(f"Copilot notification failed (non-fatal): {e}", 'WARN')
```

**Integration points in the watcher's main loop:**
```python
# In the "NEW MEETING" block (line ~651):
notify_copilot('meeting_start', mid,
    meeting_title=title,
    attendee_emails=state['active_meetings'][mid].get('attendees', []))

# After classify_batch_with_claude (line ~696), send the batch:
notify_copilot('transcript_chunk', mid,
    meeting_title=title,
    sentences=[{'speaker': s.get('speaker_name',''), 'text': s['text'],
                'timestamp': str(s.get('start_time',''))} for s in batch])

# In the "Handle ended meetings" block (line ~718):
notify_copilot('meeting_end', mid, meeting_title=meta.get('title', 'Meeting'))
```

### Engine Bridge Endpoint (add to api.py)

```python
# In engine/api.py
from bridge.watcher_bridge import WatcherBridge, WatcherEvent

watcher_bridge = WatcherBridge()

@router.post("/watcher/event")
async def watcher_event(body: WatcherEvent) -> dict:
    return await watcher_bridge.handle_event(body)
```

### Nginx Fix (all proxy to 8900)

```nginx
# FIX: Both locations proxy to 8900 (single FastAPI app)
location /ws {
    proxy_pass http://127.0.0.1:8900;
    # ... existing WebSocket headers ...
}

location /api {
    proxy_pass http://127.0.0.1:8900;
    # ... existing headers ...
}
```

### End-to-End Test Script Pattern

```python
#!/usr/bin/env python3
"""End-to-end test: simulates watcher -> engine -> panel flow."""
import json
import time
import urllib.request
import threading
import websocket  # or use websockets for async

ENGINE = 'http://localhost:8900'

def post_event(event_type, meeting_id, **kwargs):
    payload = {'event_type': event_type, 'meeting_id': meeting_id, **kwargs}
    req = urllib.request.Request(
        f'{ENGINE}/api/watcher/event',
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'}
    )
    return json.loads(urllib.request.urlopen(req, timeout=10).read())

# 1. Health check
health = json.loads(urllib.request.urlopen(f'{ENGINE}/api/health').read())
assert health['status'] == 'ok'

# 2. Simulate meeting start
result = post_event('meeting_start', 'test-e2e-001',
    meeting_title='E2E Test Meeting',
    attendee_emails=['sean@hafniafin.com'])
assert result['status'] == 'context_loaded'

# 3. Simulate transcript chunk with actionable sentence
result = post_event('transcript_chunk', 'test-e2e-001',
    meeting_title='E2E Test Meeting',
    sentences=[
        {'speaker': 'Sean', 'text': 'We need to set up the staging server by Friday', 'timestamp': '00:05:00'},
        {'speaker': 'Julian', 'text': 'Agreed, I will handle the deployment', 'timestamp': '00:05:30'},
    ])
assert result['status'] == 'processed'

# 4. Check state -- intents should be detected
state = json.loads(urllib.request.urlopen(f'{ENGINE}/api/state').read())
assert state['intent_count'] > 0

# 5. Simulate meeting end
result = post_event('meeting_end', 'test-e2e-001')
assert result['status'] == 'ended'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Watcher runs standalone | Watcher + copilot engine as additional consumer | Phase 6 | Watcher behavior unchanged, engine adds intelligence layer |
| Panel on localhost | Panel on Vercel (HTTPS) | Phase 6 | Required for Zoom iframe embedding |
| Engine on localhost | Engine behind nginx + TLS | Phase 6 | Required for panel cross-origin WebSocket |

**Not deprecated:**
- The meeting-watcher v2's existing behavior (Obsidian notes, iMessage alerts, Linear issues) remains fully intact. The copilot engine is additive, not a replacement.

## Open Questions

1. **DNS Provider Access**
   - What we know: `copilot-api.agency.dev` has no A record. The VPS IP is needed.
   - What's unclear: Which DNS provider manages `agency.dev` -- Cloudflare, Namecheap, Google Domains?
   - Recommendation: The deploy plan (06-02) already has a human checkpoint for this. Document the VPS IP in the plan so the operator can create the A record.

2. **Vercel Project Configuration**
   - What we know: Vercel CLI v50.4.5 is installed. `vercel projects ls` output was empty (may need login/token).
   - What's unclear: Whether a Vercel project is already linked for this repo.
   - Recommendation: Plan should include `vercel login` + `vercel link` steps before `vercel --prod`.

3. **Engine Single-Port vs Dual-Port Architecture**
   - What we know: The engine runs on a single port (8900). The nginx config and systemd description reference 8901 as a separate REST port, but this was never implemented.
   - What's unclear: Was dual-port intended for future use?
   - Recommendation: Keep single-port. FastAPI handles both perfectly. Fix nginx to proxy everything to 8900. Update the systemd description to remove the "8901" reference.

4. **Watcher v2 Modification Scope**
   - What we know: The watcher is at `/opt/agency-workspace/scripts/meeting-watcher.py` (not in the meeting-copilot repo).
   - What's unclear: Should the bridge calls be added to the watcher script itself, or should a wrapper/hook system be used?
   - Recommendation: Add `notify_copilot()` calls directly in the watcher script at the three lifecycle points. Simplest approach, no abstraction needed. The calls are fire-and-forget (try/except wrapped) so they never affect watcher reliability.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection of meeting-watcher.py (750 lines) -- full architecture understood
- Direct codebase inspection of engine/ (main.py, api.py, ws_handler.py, config.py, models.py)
- Direct codebase inspection of panel/ (useEngine.ts, meetingStore.ts, vercel.json, vite.config.ts)
- Direct codebase inspection of deploy/ (deploy-engine.sh, systemd service, nginx conf)
- VPS infrastructure checks (nginx installed, certbot installed, no copilot-api cert, no DNS record)

### Secondary (MEDIUM confidence)
- Vercel CLI availability confirmed (v50.4.5 at /usr/local/bin/vercel)
- Nginx version 1.18.0 confirmed (Ubuntu package)

### Tertiary (LOW confidence)
- DNS provider for agency.dev unknown -- affects deployment timeline

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new deps needed
- Architecture: HIGH -- all code inspected, bridge pattern well-defined by existing API surface
- Pitfalls: HIGH -- nginx port mismatch confirmed by code inspection, DNS absence confirmed by dig
- Deployment: MEDIUM -- VPS tools confirmed, but DNS/Vercel project linking needs human steps

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable -- no fast-moving dependencies)
