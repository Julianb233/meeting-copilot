# Phase 1: Scaffold & Infrastructure - Research

**Researched:** 2026-03-20
**Domain:** Next.js 15 + Zoom Apps SDK, Python WebSocket/REST, Nginx TLS proxy
**Confidence:** HIGH

## Summary

Phase 1 scaffolds two separate applications -- a Next.js 15 panel UI (deployed to Vercel) and a Python copilot engine (deployed to Hetzner VPS) -- connected via WebSocket through an nginx TLS proxy. The Zoom Apps SDK (`@zoom/appssdk`) is a lightweight JavaScript bridge that runs in an iframe inside the Zoom client; it does NOT embed video and has no React version conflicts (the official Zoom sample app uses Next.js 15.3.4 + React 19.1.0 successfully). The Python engine should use FastAPI for both WebSocket and REST, running two separate uvicorn server instances on ports 8900 (WebSocket) and 8901 (REST) within the same asyncio event loop.

**Primary recommendation:** Use the official `zoom/zoomapps-nextjs-sample` as the starter template for the panel, and FastAPI with two uvicorn instances for the Python engine. Do NOT confuse the Zoom Meeting SDK (video embedding, has React 19 issues) with the Zoom Apps SDK (iframe bridge, works fine with Next.js 15).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `next` | 15.3.x | Panel UI framework | Official Zoom sample uses 15.3.4; App Router, React 19 support |
| `react` / `react-dom` | ^19.1.0 | UI rendering | Required by Next.js 15; confirmed working with @zoom/appssdk |
| `@zoom/appssdk` | ^0.16.35 | Zoom client communication bridge | Official SDK for Zoom Apps (side panel, popout, etc.) |
| `fastapi` | 0.115.x | Python REST + WebSocket framework | Built-in WebSocket support, Pydantic validation, async-native |
| `uvicorn` | 0.34.x | ASGI server for FastAPI | Standard production server; supports running multiple instances in one process |
| `pydantic` | 2.x | Message schema validation | FastAPI's native validation; use for WebSocket message schemas |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tailwindcss` | ^4 | Panel styling | Official Zoom sample uses it; fast UI development |
| `typescript` | ^5 | Type safety | Both panel code and shared type definitions |
| `python-dotenv` | 1.x | Environment config | Load .env files in Python engine |
| `websocket-client` | 1.x | Python WS client for testing | Test WebSocket connections from CLI |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI (two ports) | `websockets` lib + `aiohttp` | Lower-level, no Pydantic validation, more boilerplate for REST |
| FastAPI (two ports) | Single port for both WS + REST | Simpler but violates the spec (COM-01 on 8900, COM-02 on 8901) |
| Tailwind CSS | CSS Modules | Zoom sample uses Tailwind; switching adds friction for no benefit |
| Next.js App Router | Pages Router | App Router is the standard for Next.js 15; no reason to use Pages |

**Installation (Panel):**
```bash
npx create-next-app@latest panel --typescript --tailwind --eslint --app --src-dir
cd panel
npm install @zoom/appssdk
```

**Installation (Engine):**
```bash
pip install fastapi uvicorn[standard] pydantic python-dotenv
```

## Architecture Patterns

### Recommended Project Structure
```
meeting-copilot/
├── panel/                      # Next.js 15 app (deployed to Vercel)
│   ├── src/
│   │   ├── app/                # App Router pages
│   │   │   ├── layout.tsx      # Root layout
│   │   │   ├── page.tsx        # Home/side panel view
│   │   │   └── api/            # API routes (OAuth callback, health)
│   │   ├── components/         # React components
│   │   ├── lib/                # Utilities (zoom SDK wrapper, WS client)
│   │   └── types/              # Shared TypeScript types
│   ├── public/                 # Static assets
│   ├── next.config.ts          # Next.js config (CSP headers for Zoom)
│   ├── package.json
│   └── tsconfig.json
├── engine/                     # Python copilot engine (deployed to VPS)
│   ├── main.py                 # Entry point — runs both servers
│   ├── ws_server.py            # WebSocket server (port 8900)
│   ├── api_server.py           # REST API server (port 8901)
│   ├── models/                 # Pydantic message schemas
│   │   ├── events.py           # WebSocket event types
│   │   └── state.py            # Meeting state models
│   ├── core/                   # Core logic (connection manager, state)
│   ├── requirements.txt
│   └── .env.example
├── deploy/                     # Deployment configs
│   ├── nginx/                  # Nginx site configs
│   │   └── meeting-copilot.conf
│   └── systemd/               # Systemd service files
│       └── copilot-engine.service
├── shared/                     # Shared type definitions (reference only)
│   └── events.schema.json      # JSON Schema for event types (source of truth)
└── .env.example                # Root env template
```

### Pattern 1: Dual-Port FastAPI with Shared Event Loop

**What:** Run two separate FastAPI app instances on different ports (8900 for WebSocket, 8901 for REST) in a single Python process using asyncio.gather.
**When to use:** When the spec requires separate ports for WebSocket and REST but they need shared state (e.g., connection manager, meeting state).
**Example:**
```python
# Source: https://gist.github.com/tenuki/ff67f87cba5c4c04fd08d9c800437477
import asyncio
import uvicorn
from ws_server import ws_app
from api_server import api_app

async def run_server(app, port: int):
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        run_server(ws_app, 8900),
        run_server(api_app, 8901),
    )

if __name__ == "__main__":
    asyncio.run(main())
```

### Pattern 2: WebSocket Connection Manager with Typed Events

**What:** A ConnectionManager class that tracks active WebSocket connections and broadcasts typed JSON events validated by Pydantic.
**When to use:** For the WebSocket server handling panel connections.
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/websockets/
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class WSEvent(BaseModel):
    type: Literal["task_update", "agent_status", "decision", "completion", "heartbeat"]
    timestamp: datetime
    payload: dict

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, event: WSEvent):
        data = event.model_dump_json()
        for conn in self.active_connections:
            await conn.send_text(data)

manager = ConnectionManager()

ws_app = FastAPI()

@ws_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            # Validate incoming messages
            event = WSEvent.model_validate_json(raw)
            await manager.broadcast(event)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

### Pattern 3: Zoom Apps SDK Initialization

**What:** Initialize the Zoom Apps SDK in the panel to establish communication with the Zoom client.
**When to use:** On panel load inside the Zoom iframe.
**Example:**
```typescript
// Source: https://www.npmjs.com/package/@zoom/appssdk
// Source: https://github.com/zoom/zoomapps-nextjs-sample
import zoomSdk from "@zoom/appssdk";

export async function initZoomApp() {
  try {
    const configResponse = await zoomSdk.config({
      capabilities: [
        "getMeetingContext",
        "getUserContext",
        "onMeeting",
        "sendAppInvitation",
      ],
    });
    console.log("Zoom App configured:", configResponse);
    return configResponse;
  } catch (error) {
    // Not running inside Zoom — dev/standalone mode
    console.warn("Not in Zoom context, running standalone:", error);
    return null;
  }
}
```

### Pattern 4: WebSocket Client in React (Panel Side)

**What:** Panel connects to VPS engine via WebSocket, receives typed events, and updates UI state.
**When to use:** In the panel's main layout or a context provider.
**Example:**
```typescript
// Panel WebSocket client
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "wss://copilot.yourdomain.com/ws";

export function useWebSocket() {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const parsed: WSEvent = JSON.parse(event.data);
      setEvents((prev) => [...prev, parsed]);
    };

    ws.onclose = () => {
      // Reconnect after delay
      setTimeout(() => { /* reconnect logic */ }, 3000);
    };

    return () => ws.close();
  }, []);

  const send = (event: WSEvent) => {
    wsRef.current?.send(JSON.stringify(event));
  };

  return { events, send };
}
```

### Anti-Patterns to Avoid

- **Using Zoom Meeting SDK instead of Zoom Apps SDK:** The Meeting SDK embeds video and has React 19 compatibility issues. The Apps SDK is a lightweight iframe bridge with zero React conflicts.
- **Single FastAPI app on one port for both WS and REST:** Violates the architecture spec (COM-01 on 8900, COM-02 on 8901). Use two uvicorn instances.
- **Polling instead of WebSocket for real-time events:** The whole point of COM-01 and COM-03 is real-time streaming. Do not use REST polling for events.
- **Using `proxy_read_timeout 60s` (nginx default) for WebSocket:** Connections will drop after 60 seconds of no traffic. Set to hours/days and implement application-level ping/pong.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket message validation | Manual JSON parsing + type checking | Pydantic models with `model_validate_json()` | Edge cases: missing fields, wrong types, extra fields |
| WebSocket reconnection (panel) | Custom retry logic from scratch | Established reconnection pattern with exponential backoff | Race conditions, state sync after reconnect |
| TLS termination | Application-level TLS in Python | Nginx TLS termination + proxy to plain WS | Cert management, performance, renewal automation |
| Process management (engine) | Custom daemon/screen/tmux | Systemd service unit | Auto-restart, logging, boot startup |
| Zoom SDK initialization | Manual postMessage to Zoom iframe | `@zoom/appssdk` with `zoomSdk.config()` | Protocol is complex, SDK handles handshake |
| CORS for Zoom iframe | Manual header setting | Next.js config `headers()` in next.config.ts | Must match Zoom's CSP requirements exactly |

**Key insight:** The Zoom Apps SDK handles all iframe communication complexity. The Python engine's only job is WebSocket + REST. nginx handles TLS. Do not try to combine these responsibilities.

## Common Pitfalls

### Pitfall 1: Confusing Zoom Meeting SDK with Zoom Apps SDK
**What goes wrong:** Developer installs `@zoomus/websdk` or `@zoom/meetingsdk` thinking they need it for the side panel. These are for embedding Zoom video into a web page. They have known React 19 / Next.js 15 compatibility issues.
**Why it happens:** "Zoom SDK" is ambiguous. Multiple Zoom SDKs exist for different purposes.
**How to avoid:** Only install `@zoom/appssdk`. The panel runs as a standard web page loaded in Zoom's iframe. It does NOT need to embed video.
**Warning signs:** Seeing `@zoomus/websdk` or `@zoom/meetingsdk` in package.json; "ReactCurrentOwner" errors.

### Pitfall 2: Nginx Drops WebSocket After 60 Seconds
**What goes wrong:** WebSocket connection silently dies after ~60 seconds of no messages.
**Why it happens:** Nginx `proxy_read_timeout` defaults to 60 seconds. If no data flows, nginx closes the connection.
**How to avoid:** Set `proxy_read_timeout 86400s` (24 hours) and implement application-level ping/pong every 30 seconds.
**Warning signs:** WebSocket works in dev but drops in production behind nginx.

### Pitfall 3: Missing WebSocket Upgrade Headers in Nginx
**What goes wrong:** WebSocket handshake fails with 400 or connection drops silently.
**Why it happens:** Nginx strips `Upgrade` and `Connection` headers by default. Without the `map` block and explicit header forwarding, the HTTP-to-WebSocket upgrade never happens.
**How to avoid:** Always include the `map $http_upgrade $connection_upgrade` block and set `proxy_http_version 1.1`.
**Warning signs:** 400 errors on WebSocket connect; works without nginx but fails behind it.

### Pitfall 4: Zoom App Home URL Missing Required Headers
**What goes wrong:** Zoom rejects the app or shows a blank iframe.
**Why it happens:** Zoom requires specific OWASP response headers on the Home URL. Missing `X-Frame-Options`, incorrect CSP, or missing `Content-Security-Policy` that allows Zoom's iframe embedding.
**How to avoid:** Configure Next.js response headers in `next.config.ts` to allow iframe embedding from Zoom domains. Do NOT set `X-Frame-Options: DENY`.
**Warning signs:** Blank panel in Zoom, console errors about frame-ancestors.

### Pitfall 5: FastAPI WebSocket and REST State Not Shared
**What goes wrong:** REST API cannot see current WebSocket connections or active meeting state.
**Why it happens:** If running as separate processes, they don't share memory.
**How to avoid:** Run both in the same asyncio process using the dual-uvicorn pattern. Share state via a Python module-level singleton (ConnectionManager, MeetingState).
**Warning signs:** REST health endpoint returns "0 connections" when panels are connected.

### Pitfall 6: Vercel Does Not Support WebSocket
**What goes wrong:** Trying to run WebSocket server on Vercel.
**Why it happens:** Vercel is serverless, it does not support persistent WebSocket connections.
**How to avoid:** Panel (Vercel) connects as a WebSocket CLIENT to the VPS engine. The WebSocket SERVER runs only on the VPS. Panel's Next.js API routes are for OAuth/config only, not WebSocket.
**Warning signs:** Attempting to put WebSocket server code in `/api/` routes on Vercel.

## Code Examples

### Nginx WebSocket Proxy with TLS (Production Config)
```nginx
# Source: https://oneuptime.com/blog/post/2025-12-16-nginx-websocket-proxy-ssl/view

map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 443 ssl http2;
    server_name copilot.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/copilot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/copilot.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # WebSocket proxy (port 8900)
    location /ws {
        proxy_pass http://127.0.0.1:8900;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
    }

    # REST API proxy (port 8901)
    location /api {
        proxy_pass http://127.0.0.1:8901;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP redirect to HTTPS
server {
    listen 80;
    server_name copilot.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

### FastAPI REST API with Health Check (Port 8901)
```python
# engine/api_server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

api_app = FastAPI(title="Meeting Copilot API", version="0.1.0")

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@api_app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }

@api_app.get("/state")
async def meeting_state():
    # Will be populated in later phases
    return {
        "active_meeting": None,
        "connected_panels": 0,
        "tasks": [],
    }
```

### Systemd Service for Engine
```ini
# deploy/systemd/copilot-engine.service
[Unit]
Description=Meeting Copilot Engine
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/agency-workspace/meeting-copilot/engine
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/opt/agency-workspace/meeting-copilot/engine/.env

[Install]
WantedBy=multi-user.target
```

### Next.js Config for Zoom Iframe Embedding
```typescript
// panel/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          // Allow Zoom to embed this app in an iframe
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors https://*.zoom.us https://*.zoomgov.com",
          },
          // Do NOT set X-Frame-Options: DENY -- Zoom needs iframe access
        ],
      },
    ];
  },
};

export default nextConfig;
```

## Event Schema Design

The WebSocket event protocol between panel and engine should use a typed envelope pattern:

```json
{
  "type": "task_update",
  "timestamp": "2026-03-20T14:30:00Z",
  "payload": {
    "task_id": "task_abc123",
    "status": "running",
    "title": "Create landing page for Better Together",
    "agent": "agent2",
    "progress": 45
  }
}
```

### Event Types (COM-03)

| Type | Direction | Purpose |
|------|-----------|---------|
| `heartbeat` | Engine -> Panel | Keep-alive, connection health |
| `task_update` | Engine -> Panel | Task status change (pending, running, completed, failed) |
| `task_created` | Engine -> Panel | New task spawned |
| `completion` | Engine -> Panel | Task finished with result |
| `decision` | Engine -> Panel | Meeting decision detected |
| `agent_status` | Engine -> Panel | Fleet agent status change |
| `meeting_state` | Engine -> Panel | Full state snapshot |
| `quick_action` | Panel -> Engine | User triggered a quick action button |
| `panel_connect` | Panel -> Engine | Panel connected, request initial state |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Next.js Pages Router | App Router (default) | Next.js 13+ (stable in 15) | Use `app/` directory, Server Components by default |
| `@zoomus/websdk` | `@zoom/appssdk` for Zoom Apps | 2023+ | Different package, different purpose -- Apps SDK for iframe apps |
| Flask + SocketIO | FastAPI + native WebSocket | 2023+ | Async-native, Pydantic validation, no SocketIO overhead |
| Pydantic v1 `.parse_obj()` | Pydantic v2 `.model_validate_json()` | Pydantic v2 (2023) | Use v2 API everywhere |
| Manual TLS in Python | Nginx TLS termination | Standard practice | Let nginx handle certs, proxy plain HTTP/WS to backend |

**Deprecated/outdated:**
- `@zoomus/websdk`: Legacy package name for Meeting SDK. Do not use for Zoom Apps.
- Pydantic v1 API (`parse_obj`, `schema()`): Use v2 API (`model_validate`, `model_json_schema`).
- `proxy_read_timeout 60s`: Default is far too short for WebSocket. Always override.

## Open Questions

1. **Zoom App Registration Details**
   - What we know: Private/internal app, need to register on marketplace.zoom.us, requires OAuth, need `zoomapp:inmeeting` scope.
   - What's unclear: Exact Home URL format requirements, full list of OWASP headers Zoom validates, whether free Zoom accounts can create Zoom Apps.
   - Recommendation: Phase 4 handles ZOM-01/02/03. For Phase 1, scaffold the Next.js app with correct CSP headers but defer Zoom registration to Phase 4.

2. **Domain for VPS nginx**
   - What we know: Need a domain pointing to VPS for TLS cert (Let's Encrypt). VPS has Tailscale networking.
   - What's unclear: Which domain to use, whether to use a subdomain of an existing domain.
   - Recommendation: Use a subdomain like `copilot.aiacrobatics.com` or similar. This should be decided before Plan 01-03. Can use Tailscale IP for dev but need real domain for Zoom (HTTPS required).

3. **WebSocket Authentication**
   - What we know: Panel connects to engine via WebSocket. In production, this should be authenticated.
   - What's unclear: What auth mechanism (API key? JWT? Zoom token passthrough?).
   - Recommendation: For Phase 1, use a simple shared secret / API key in the WebSocket connection query params. Upgrade to proper auth in later phases.

## Sources

### Primary (HIGH confidence)
- Zoom Apps Next.js Sample: https://github.com/zoom/zoomapps-nextjs-sample -- Confirms Next.js 15.3.4 + React 19.1.0 + @zoom/appssdk ^0.16.35 work together
- FastAPI WebSocket docs: https://fastapi.tiangolo.com/advanced/websockets/ -- ConnectionManager pattern, lifecycle
- Nginx WebSocket proxy guide: https://oneuptime.com/blog/post/2025-12-16-nginx-websocket-proxy-ssl/view -- Full production config

### Secondary (MEDIUM confidence)
- Multiple uvicorn instances pattern: https://gist.github.com/tenuki/ff67f87cba5c4c04fd08d9c800437477 -- asyncio.gather approach
- Zoom Apps SDK npm: https://www.npmjs.com/package/@zoom/appssdk -- Capabilities, config API
- Zoom App creation docs: https://developers.zoom.us/docs/zoom-apps/create/ -- Home URL requirements, OAuth scopes

### Tertiary (LOW confidence)
- WebSocket + Pydantic validation patterns: https://hexshift.medium.com/implementing-custom-websocket-message-protocols-in-fastapi -- Community pattern, not official
- Zoom + Next.js 15 compatibility issues: https://community.zoom.com/t5/Zoom-App-Marketplace/zoom-does-not-work-with-next-js-15/m-p/217538 -- This is about Meeting SDK, NOT Apps SDK

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Verified against official Zoom sample repo (Next.js 15.3.4 + @zoom/appssdk 0.16.35) and FastAPI official docs
- Architecture: HIGH - Dual-uvicorn pattern verified, nginx WebSocket proxy well-documented
- Pitfalls: HIGH - Zoom SDK confusion verified via community posts; nginx timeout issue well-known; Vercel WS limitation documented
- Event schema: MEDIUM - Based on standard WebSocket message protocol patterns; will be refined in Phase 3

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days - stable technologies, no fast-moving APIs)
