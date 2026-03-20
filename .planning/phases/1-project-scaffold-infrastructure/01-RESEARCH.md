# Phase 1: Scaffold & Infrastructure - Research

**Researched:** 2026-03-20
**Domain:** Project scaffolding, WebSocket server, REST API, Zoom Apps SDK, nginx proxy
**Confidence:** HIGH

## Summary

Phase 1 sets up the foundational infrastructure: a Next.js 15 panel app that will run inside Zoom's Meeting Side Panel iframe, a Python copilot engine providing both WebSocket (port 8900) and REST API (port 8901) endpoints, and nginx reverse proxy for TLS termination.

The standard approach is: Next.js 15 with `@zoom/appssdk` for the panel, FastAPI for both WebSocket and REST on separate ports (two uvicorn processes), and nginx with WebSocket upgrade headers for TLS. For Phase 1, the Zoom Apps SDK integration is boilerplate only -- actual Zoom app registration and OAuth happen in Phase 4.

**Primary recommendation:** Use FastAPI for both WebSocket and REST (two separate FastAPI apps on ports 8900 and 8901), Next.js 15 App Router with `@zoom/appssdk` v0.16.x, and standard nginx WebSocket proxy config with Let's Encrypt TLS.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `next` | 15.x | Panel UI framework | Project requirement, App Router is stable |
| `react` / `react-dom` | 19.x | UI rendering | Project requirement, pairs with Next.js 15 |
| `@zoom/appssdk` | 0.16.37 | Zoom client communication | Only official SDK for Zoom Apps |
| `fastapi` | 0.135.x | Python WebSocket + REST API | Async-native, built-in WebSocket support, type hints |
| `uvicorn` | 0.34.x | ASGI server | Standard FastAPI production server |
| `websockets` | 14.x | WebSocket protocol (FastAPI dependency) | Used internally by FastAPI/Starlette |
| `pydantic` | 2.x | Data validation / event schemas | Ships with FastAPI, enforces typed event contracts |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `typescript` | 5.x | Type safety for panel | All panel code |
| `tailwindcss` | 4.x | Panel styling | All UI components |
| `python-dotenv` | 1.x | Env config loading | Engine startup config |
| `orjson` | 3.x | Fast JSON serialization | High-throughput WebSocket messages |
| `certbot` | latest | Let's Encrypt TLS certs | Nginx TLS setup on VPS |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI (WebSocket) | `websockets` library standalone | Lower-level, no routing/DI -- FastAPI wraps it anyway |
| FastAPI (REST) | Flask | Flask is sync-first, would need separate async solution for WebSocket |
| Two FastAPI processes | Single FastAPI on one port | Requirement specifies port 8900 for WS and 8901 for REST -- two processes cleanest |
| Tailwind CSS | ShadCN + Tailwind | ShadCN is good but overkill for Phase 1 scaffolding; add in Phase 4 |

**Installation:**

Panel:
```bash
npx create-next-app@latest panel --typescript --tailwind --app --src-dir
cd panel && npm install @zoom/appssdk
```

Engine:
```bash
pip install "fastapi[standard]" uvicorn websockets pydantic orjson python-dotenv
```

## Architecture Patterns

### Recommended Project Structure

```
meeting-copilot/
├── panel/                    # Next.js 15 app (deploys to Vercel)
│   ├── src/
│   │   ├── app/              # App Router pages
│   │   │   ├── layout.tsx    # Root layout
│   │   │   ├── page.tsx      # Main panel page
│   │   │   └── api/          # API routes (health, etc.)
│   │   ├── components/       # React components
│   │   ├── lib/
│   │   │   ├── zoom.ts       # Zoom SDK wrapper
│   │   │   └── ws.ts         # WebSocket client
│   │   └── types/            # Shared TypeScript types
│   ├── public/
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── package.json
├── engine/                   # Python copilot engine (deploys to VPS)
│   ├── copilot/
│   │   ├── __init__.py
│   │   ├── ws_server.py      # WebSocket server (port 8900)
│   │   ├── api_server.py     # REST API server (port 8901)
│   │   ├── events.py         # Event schema definitions
│   │   ├── manager.py        # Connection manager
│   │   └── config.py         # Configuration
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── start.sh              # Starts both servers
├── deploy/
│   ├── nginx/
│   │   └── meeting-copilot.conf  # Nginx config
│   └── systemd/
│       ├── copilot-ws.service    # WebSocket server service
│       └── copilot-api.service   # REST API service
├── shared/
│   └── events.schema.json   # Event schema (source of truth)
├── .env.example
└── scripts/
    ├── dev.sh                # Local development launcher
    └── deploy.sh             # VPS deployment script
```

### Pattern 1: Dual FastAPI Process Architecture

**What:** Run two separate FastAPI applications -- one for WebSocket on port 8900, one for REST on port 8901. Each runs as its own uvicorn process managed by systemd.

**When to use:** When WebSocket and REST need different ports (as specified in requirements).

**Example:**

```python
# engine/copilot/ws_server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from copilot.manager import ConnectionManager
from copilot.events import MeetingEvent

app = FastAPI(title="Copilot WebSocket Server")
manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            event = MeetingEvent.model_validate(data)
            await manager.handle_event(event, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/health")
async def health():
    return {"status": "ok", "connections": manager.connection_count}
```

```python
# engine/copilot/api_server.py
from fastapi import FastAPI
from copilot.events import MeetingState

app = FastAPI(title="Copilot REST API")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "copilot-api"}

@app.get("/state")
async def get_state() -> MeetingState:
    # Returns current meeting state snapshot
    ...
```

```bash
# engine/start.sh
#!/bin/bash
uvicorn copilot.ws_server:app --host 0.0.0.0 --port 8900 &
uvicorn copilot.api_server:app --host 0.0.0.0 --port 8901 &
wait
```

### Pattern 2: Zoom Apps SDK Initialization Wrapper

**What:** A reusable hook/wrapper that initializes the Zoom Apps SDK with `zoomSdk.config()` and provides running context to the app.

**When to use:** Every component that needs Zoom SDK access.

**Example:**

```typescript
// panel/src/lib/zoom.ts
import zoomSdk from "@zoom/appssdk";

let configured = false;

export async function initZoomSdk() {
  if (configured) return;

  const configResponse = await zoomSdk.config({
    capabilities: [
      "getMeetingContext",
      "getMeetingParticipants",
      "onMeeting",
      "getUserContext",
    ],
  });

  configured = true;
  console.log("Zoom SDK configured:", configResponse);
  return configResponse;
}

export function onRunningContextChange(handler: (event: any) => void) {
  zoomSdk.addEventListener("onRunningContextChange", handler);
}
```

### Pattern 3: WebSocket Client with Reconnection

**What:** A WebSocket client class for the panel that auto-reconnects and dispatches typed events.

**When to use:** Panel-to-engine communication.

**Example:**

```typescript
// panel/src/lib/ws.ts
type EventHandler = (event: MeetingEvent) => void;

export class CopilotWebSocket {
  private ws: WebSocket | null = null;
  private handlers: Map<string, EventHandler[]> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private url: string) {}

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      const handlers = this.handlers.get(event.type) || [];
      handlers.forEach(h => h(event));
    };
    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };
  }

  on(type: string, handler: EventHandler) {
    const existing = this.handlers.get(type) || [];
    this.handlers.set(type, [...existing, handler]);
  }

  send(event: MeetingEvent) {
    this.ws?.send(JSON.stringify(event));
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}
```

### Pattern 4: Pydantic Event Schema

**What:** Define all meeting events as Pydantic models with discriminated unions for type safety.

**When to use:** All engine event definitions.

**Example:**

```python
# engine/copilot/events.py
from pydantic import BaseModel
from enum import Enum
from typing import Literal
from datetime import datetime

class EventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    DECISION_LOGGED = "decision_logged"
    AGENT_STATUS = "agent_status"
    MEETING_STATE = "meeting_state"
    TRANSCRIPT_CHUNK = "transcript_chunk"

class BaseEvent(BaseModel):
    type: EventType
    timestamp: datetime
    meeting_id: str | None = None

class TaskCreatedEvent(BaseEvent):
    type: Literal[EventType.TASK_CREATED] = EventType.TASK_CREATED
    task_id: str
    title: str
    assigned_agent: str | None = None

class AgentStatusEvent(BaseEvent):
    type: Literal[EventType.AGENT_STATUS] = EventType.AGENT_STATUS
    agent_id: str
    status: str  # idle, working, completed, error
    current_task: str | None = None

class MeetingState(BaseModel):
    meeting_id: str
    active: bool
    tasks: list[dict]
    decisions: list[dict]
    agents: list[dict]
```

### Anti-Patterns to Avoid

- **Single process for both ports:** Do not try to bind one FastAPI app to two ports. Use two processes.
- **Polling instead of WebSocket:** The panel must use WebSocket for real-time updates, not REST polling.
- **Zoom SDK in SSR:** The `@zoom/appssdk` only works in browser context (Zoom's embedded browser). Never import it in server components or API routes -- use `"use client"` directive.
- **Hardcoded URLs:** All service URLs (WebSocket endpoint, REST API, Zoom config) must come from environment variables.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket connection management | Custom socket handling | FastAPI WebSocket + ConnectionManager pattern | Handles accept, disconnect, broadcast correctly |
| JSON schema validation | Manual dict parsing | Pydantic models | Type-safe, auto-validation, serialization |
| ASGI server | Custom event loop | uvicorn | Production-grade, handles signals, reloading |
| TLS termination | Python-level SSL | nginx + Let's Encrypt | Standard, performant, auto-renewal |
| WebSocket reconnection | Manual retry logic | Reconnection class with exponential backoff | Edge cases around state sync on reconnect |
| Process management | Shell scripts with `&` | systemd services | Restart on crash, logging, boot startup |
| Environment config | Hardcoded values | python-dotenv + Next.js .env.local | Standard, 12-factor app |

**Key insight:** Every infrastructure concern in this phase has a well-established solution. The value is in wiring them together correctly, not building custom solutions.

## Common Pitfalls

### Pitfall 1: Zoom SDK Client-Only Import

**What goes wrong:** Importing `@zoom/appssdk` in a Server Component or during SSR causes build failures because the SDK expects `window` and Zoom's embedded browser APIs.
**Why it happens:** Next.js 15 App Router defaults to Server Components.
**How to avoid:** Only import `@zoom/appssdk` in files marked with `"use client"` at the top. Create a wrapper component/hook.
**Warning signs:** Build error mentioning `window is not defined` or `document is not defined`.

### Pitfall 2: Missing WebSocket Upgrade Headers in Nginx

**What goes wrong:** WebSocket connections fail silently or return 400. Client sees connection close immediately.
**Why it happens:** Nginx defaults to HTTP/1.0 for proxy and strips Upgrade headers.
**How to avoid:** Always include all three directives: `proxy_http_version 1.1`, `proxy_set_header Upgrade $http_upgrade`, `proxy_set_header Connection "upgrade"`.
**Warning signs:** WebSocket connects locally but fails through nginx.

### Pitfall 3: Nginx Proxy Timeout Kills WebSocket

**What goes wrong:** WebSocket connections drop after 60 seconds of inactivity.
**Why it happens:** Default `proxy_read_timeout` is 60s. WebSocket connections are long-lived.
**How to avoid:** Set `proxy_read_timeout 86400s` (24h) and implement application-level ping/pong at 30s intervals.
**Warning signs:** Connection drops during quiet meeting periods.

### Pitfall 4: CORS Between Vercel Panel and VPS Engine

**What goes wrong:** WebSocket or REST calls from the panel (on Vercel) to the engine (on VPS) are blocked by browser CORS policy.
**Why it happens:** Different origins (vercel.app vs your VPS domain).
**How to avoid:** Configure CORS middleware in both FastAPI apps. For WebSocket, CORS is checked on the initial HTTP upgrade handshake.
**Warning signs:** Browser console shows CORS errors, WebSocket upgrade fails.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-panel.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Pitfall 5: CSP Headers for Zoom Embedded Browser

**What goes wrong:** Zoom's embedded browser blocks resources or WebSocket connections.
**Why it happens:** Zoom enforces CSP and the Marketplace domain allowlist.
**How to avoid:** Set proper CSP headers in Next.js config. Importantly, `script-src` must include `https://appssdk.zoom.us/sdk.min.js`. All external domains must be registered in Zoom Marketplace app config. Do NOT load libraries from public CDNs -- bundle everything locally.
**Warning signs:** Blank panel in Zoom, console errors about CSP violations.

### Pitfall 6: FastAPI WebSocket JSON Parsing

**What goes wrong:** `receive_json()` silently fails or raises unexpected errors on malformed messages.
**Why it happens:** No validation layer between raw WebSocket data and application logic.
**How to avoid:** Use `receive_text()` + explicit `json.loads()` + Pydantic validation, wrapped in try/except.
**Warning signs:** Unhandled exceptions crash the WebSocket handler loop.

## Code Examples

### Nginx WebSocket Proxy with TLS

```nginx
# deploy/nginx/meeting-copilot.conf
# Source: nginx official WebSocket proxy docs + Let's Encrypt

map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

# WebSocket server
upstream copilot_ws {
    server 127.0.0.1:8900;
}

# REST API server
upstream copilot_api {
    server 127.0.0.1:8901;
}

server {
    listen 443 ssl;
    server_name copilot.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/copilot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/copilot.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # WebSocket endpoint
    location /ws {
        proxy_pass http://copilot_ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # REST API endpoint
    location /api {
        proxy_pass http://copilot_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://copilot_api/health;
    }
}

server {
    listen 80;
    server_name copilot.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

### Systemd Service Files

```ini
# deploy/systemd/copilot-ws.service
[Unit]
Description=Copilot WebSocket Server
After=network.target

[Service]
Type=simple
User=agency
WorkingDirectory=/opt/agency-workspace/meeting-copilot/engine
ExecStart=/usr/bin/uvicorn copilot.ws_server:app --host 127.0.0.1 --port 8900
Restart=always
RestartSec=5
EnvironmentFile=/opt/agency-workspace/meeting-copilot/.env

[Install]
WantedBy=multi-user.target
```

```ini
# deploy/systemd/copilot-api.service
[Unit]
Description=Copilot REST API Server
After=network.target

[Service]
Type=simple
User=agency
WorkingDirectory=/opt/agency-workspace/meeting-copilot/engine
ExecStart=/usr/bin/uvicorn copilot.api_server:app --host 127.0.0.1 --port 8901
Restart=always
RestartSec=5
EnvironmentFile=/opt/agency-workspace/meeting-copilot/.env

[Install]
WantedBy=multi-user.target
```

### Next.js CSP Headers for Zoom

```typescript
// panel/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' https://appssdk.zoom.us",
              "style-src 'self' 'unsafe-inline'",
              "connect-src 'self' wss://copilot.yourdomain.com https://copilot.yourdomain.com",
              "img-src 'self' data:",
              "font-src 'self'",
              "frame-ancestors 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
```

### Environment Configuration

```bash
# .env.example

# Panel (Next.js)
NEXT_PUBLIC_WS_URL=wss://copilot.yourdomain.com/ws
NEXT_PUBLIC_API_URL=https://copilot.yourdomain.com/api
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
ZOOM_REDIRECT_URL=http://localhost:3000/api/auth/callback

# Engine (Python)
WS_HOST=127.0.0.1
WS_PORT=8900
API_HOST=127.0.0.1
API_PORT=8901
ALLOWED_ORIGINS=https://your-panel.vercel.app,http://localhost:3000
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Next.js Pages Router | App Router (default in Next.js 13+) | 2023 | Use `app/` dir, Server Components by default |
| Flask + eventlet | FastAPI + uvicorn | 2020+ | Native async, no monkey-patching |
| Pydantic v1 | Pydantic v2 | 2023 | Faster validation, `model_validate` replaces `parse_obj` |
| `@zoomus/websdk` | `@zoom/appssdk` | 2022 | Meeting SDK is separate from Apps SDK -- use `appssdk` for in-client apps |
| Manual cert management | certbot + auto-renewal | Standard | Use `certbot --nginx` for automated TLS |

**Deprecated/outdated:**
- `@zoomus/websdk`: This is the Meeting SDK (for embedding Zoom meetings), NOT the Apps SDK. Do not confuse them.
- Flask-SocketIO: Replaced by FastAPI WebSocket for async-first architectures.
- Pydantic v1 `BaseModel.parse_obj()`: Use `BaseModel.model_validate()` in v2.

## Open Questions

1. **Zoom App Registration Timing**
   - What we know: Phase 4 handles actual Zoom app registration and OAuth.
   - What's unclear: Whether Phase 1 should create a placeholder app in Marketplace for early testing.
   - Recommendation: Phase 1 should only scaffold the SDK boilerplate. No Marketplace registration needed yet. The panel can be developed and tested as a standalone web app initially.

2. **Domain for VPS TLS**
   - What we know: Engine runs on Hetzner VPS, needs TLS for WebSocket.
   - What's unclear: What domain/subdomain will point to the VPS.
   - Recommendation: Plans should use a placeholder domain (e.g., `copilot.yourdomain.com`) and note that DNS setup is a prerequisite. Could also use a Tailscale HTTPS cert for internal dev.

3. **Shared State Between WS and REST Processes**
   - What we know: Two separate FastAPI processes need access to the same meeting state.
   - What's unclear: Best approach for Phase 1 (shared file, Redis, in-memory with IPC).
   - Recommendation: For Phase 1, use a simple shared JSON file or in-memory state in the WS server with the REST server making internal HTTP calls to the WS server's health endpoint. Add Redis in a later phase if needed.

4. **Next.js 15 + Zoom Apps SDK Compatibility**
   - What we know: There was a community report of issues with Next.js 15 + Zoom SDK. The Zoom sample repo uses Next.js (unknown version).
   - What's unclear: Whether there are actual breaking issues or just SSR import problems.
   - Recommendation: Use `"use client"` for all Zoom SDK code. This is the standard pattern and avoids SSR issues entirely.

## Sources

### Primary (HIGH confidence)
- `@zoom/appssdk` v0.16.37 - GitHub repo and NPM, SDK initialization and capabilities
- FastAPI 0.135.x - Official WebSocket documentation at fastapi.tiangolo.com
- Nginx WebSocket proxy - Official patterns from websocket.org and nginx docs

### Secondary (MEDIUM confidence)
- Zoom zoomapps-nextjs-sample GitHub repo - Project structure and OAuth setup patterns
- Zoom Developer Forum CSP discussion - CSP header requirements for Zoom embedded browser
- Zoom Developer Docs (developers.zoom.us) - App creation flow, OAuth scopes (`zoomapp:inmeeting`)

### Tertiary (LOW confidence)
- Next.js 15 + Zoom compatibility report - Community forum, unable to verify specifics
- FastAPI two-process port separation - GitHub discussions, straightforward but undocumented officially

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official sources, versions confirmed
- Architecture: HIGH - Dual FastAPI process pattern is well-established, nginx WS proxy is standard
- Pitfalls: HIGH - CSP, CORS, nginx timeout, SSR import issues are all well-documented
- Event schema: MEDIUM - Pattern is standard Pydantic, but specific event types will evolve

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days -- stack is stable)
