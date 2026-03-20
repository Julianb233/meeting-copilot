# Technology Stack

**Project:** Meeting Copilot
**Researched:** 2026-03-20
**Overall Confidence:** MEDIUM-HIGH

---

## Recommended Stack

### Panel (Zoom Sidebar UI)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Vite | 6.x | Build tool | Zoom Apps run as iframes — pure client-side SPA. Vite produces ~42KB bundles vs Next.js ~92KB. No SSR needed or wanted inside an iframe. Faster HMR, simpler config. Next.js is overkill here — its value (SSR, API routes, middleware) is wasted inside a Zoom iframe where everything is client-rendered. | HIGH |
| React | 19.x | UI framework | Current stable. Same stack as other agency projects. Zoom's own sample apps use React. | HIGH |
| TypeScript | 5.7+ | Type safety | Non-negotiable for a real-time app with WebSocket message schemas, API types, and state management. Catches message shape mismatches at compile time. | HIGH |
| @zoom/appssdk | 0.16.36 | Zoom integration | Official SDK for apps running inside Zoom client. Provides `getMeetingContext()`, event listeners (`onMeeting`, `onParticipantChange`), `openUrl()`, and side panel lifecycle hooks. Latest version as of Dec 2025. | HIGH |
| react-use-websocket | 4.13.0 | WebSocket client | Purpose-built React hook for WebSocket. Handles reconnection, heartbeat, shared connections, message history. 77K+ weekly downloads. Alternative: raw `useEffect` + `WebSocket` — but you'd rewrite everything this library already does. | MEDIUM |
| Zustand | 5.x | State management | Lightweight (~1KB), no boilerplate, works perfectly with React 19. Meeting state (tasks, transcripts, agent status) needs a store but Redux is overkill for a side panel. Zustand's `subscribe` works well with WebSocket message handlers. | HIGH |
| Tailwind CSS | 4.x | Styling | Utility-first, small bundle (purged), fast iteration. Panel is a compact sidebar — no need for a component library. Tailwind gives full control over the constrained layout. | HIGH |
| Lucide React | latest | Icons | Tree-shakeable, consistent, MIT. Lighter than heroicons for a small panel. | HIGH |

**What NOT to use for the panel:**

| Technology | Why Not |
|------------|---------|
| Next.js | SSR/SSG is pointless inside a Zoom iframe. Adds complexity (API routes, middleware, server components) with zero benefit. The panel is a pure client-side SPA. Vercel hosting works fine with static Vite builds too. |
| Socket.IO (client) | Adds ~45KB for features you don't need (room management, fallback transports). Native WebSocket is supported everywhere Zoom runs. `react-use-websocket` wraps native WS cleanly. |
| Redux / Redux Toolkit | Too much boilerplate for a sidebar panel with 5-10 state slices. Zustand does the same job in 1/10th the code. |
| Material UI / Chakra UI | Component libraries add 100KB+ to the bundle. The panel is a narrow sidebar — custom Tailwind components are faster to build and smaller. |
| shadcn/ui | Good library but designed for full apps. For a sidebar panel, you'd use 3-4 components max. Copy the patterns, don't install the framework. |

---

### Engine (Python VPS Backend)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | 3.12+ | Runtime | Meeting watcher already runs Python. All API integrations (Fireflies, Linear, Gmail) have Python clients. 3.12 has significant perf improvements. 3.13 is fine too. | HIGH |
| FastAPI | 0.135.x | HTTP + WebSocket server | First-class WebSocket support via Starlette. Async-native. Built-in OpenAPI docs. Dependency injection for auth. Handles both the WebSocket server (port 8900) and REST snapshot API (port 8901) in one process. | HIGH |
| uvicorn | 0.34.x | ASGI server | Standard production server for FastAPI. WebSocket support, auto-reload in dev. Run with `--workers 1` (WebSocket state is in-process). | HIGH |
| LiteLLM | latest (1.x) | Multi-model AI gateway | Unified interface for Gemini, OpenAI, Claude with automatic fallback. Define fallback chain: `["gemini/gemini-2.0-flash", "openai/gpt-4o-mini", "anthropic/claude-3-haiku"]`. Handles rate limit retries, model switching, cost tracking. 8ms P95 overhead. This is the correct abstraction for a multi-model fallback chain. | HIGH |
| Pydantic | 2.x | Data validation | FastAPI's native model layer. Define WebSocket message schemas, API response models, meeting state models. V2 is significantly faster than V1. | HIGH |
| httpx | 0.28.x | Async HTTP client | For Fireflies GraphQL, Linear GraphQL, Gmail REST, Calendar REST, Contacts REST. Async-native, connection pooling, timeout handling. Replaces `requests` for async code. | HIGH |
| asyncio.Queue | stdlib | Task queue | For agent task dispatching. No need for Celery/Redis when tasks are "spawn a subprocess on this machine." asyncio.Queue + `asyncio.create_subprocess_exec()` handles the fleet agent spawning pattern cleanly. | HIGH |
| python-dotenv | 1.x | Environment config | Load API keys from `.env`. Simple, universal. | HIGH |

**What NOT to use for the engine:**

| Technology | Why Not |
|------------|---------|
| Django | Too heavy. No ORM needed (no database). FastAPI is purpose-built for async APIs + WebSockets. |
| Flask | No native async support. WebSocket support requires flask-sock or flask-socketio — bolted on, not built in. |
| Celery + Redis | Massive overkill. You're spawning 4 Claude Code agents on the same machine, not distributing tasks across a cluster. asyncio subprocess management is the right tool. |
| Socket.IO (Python) | Adds unnecessary abstraction. FastAPI's native WebSocket support is cleaner and avoids the Socket.IO protocol overhead. |
| LangChain | Over-abstracted for this use case. You need to call an LLM with a prompt and parse the response. LiteLLM gives you the model routing; you don't need LangChain's chain/agent framework on top. |
| openai SDK directly | Only talks to OpenAI. LiteLLM wraps all providers with the same interface and adds fallback logic you'd otherwise hand-code. |

---

### AI / Classification Layer

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| LiteLLM | latest | Unified LLM calls | Single `completion()` call with automatic fallback across providers. | HIGH |
| Gemini 2.0 Flash | current | Primary classifier | Free tier, fast (~200ms), good enough for intent classification. 15 RPM / 1M TPD on free tier. Primary model in the fallback chain. | HIGH |
| GPT-4o-mini | current | First fallback | Cheap ($0.15/1M input), fast, reliable. Falls in when Gemini rate-limits. | MEDIUM |
| Claude 3.5 Haiku | current | Second fallback | Excellent at structured output and nuanced classification. When Anthropic credits are available. | LOW (no credits currently) |
| Keyword matcher | custom | Final fallback | Regex/keyword-based classification when all API models fail. Already exists in meeting-watcher.py. Zero cost, instant, offline. | HIGH |

**Fallback chain order (via LiteLLM):**
```python
# LiteLLM handles this with model_list + fallbacks
model_list = [
    {"model_name": "classifier", "litellm_params": {"model": "gemini/gemini-2.0-flash"}},
    {"model_name": "classifier", "litellm_params": {"model": "openai/gpt-4o-mini"}},
    {"model_name": "classifier", "litellm_params": {"model": "anthropic/claude-3-5-haiku-latest"}},
]
# If all fail → keyword matcher (custom code, not LiteLLM)
```

---

### External API Integrations

| Service | Protocol | Python Client | Auth | Free Tier Limits | Confidence |
|---------|----------|---------------|------|-----------------|------------|
| Fireflies.ai | GraphQL | httpx (raw GraphQL) | API Key header | Unlimited reads, `addToLiveMeeting` rate-limited to 3 per 20 min | HIGH |
| Linear | GraphQL | httpx (raw GraphQL) or `linear-api` PyPI | API Key / OAuth | Generous, no hard public limit | MEDIUM |
| Gmail | REST | `google-api-python-client` | OAuth2 (service account or user consent) | 250 quota units/user/second | HIGH |
| Google Calendar | REST | `google-api-python-client` | OAuth2 | 1M queries/day | HIGH |
| Google Contacts / People API | REST | `google-api-python-client` | OAuth2 | 90M queries/day (People API) | HIGH |
| Zoom | REST + Apps SDK | `@zoom/appssdk` (panel), httpx (engine) | OAuth2 (Server-to-Server for API, Zoom App for panel) | Internal app — no marketplace limits | MEDIUM |
| Obsidian | Filesystem | Direct file read/write | None (local vault) | N/A | HIGH |

**Integration approach:**
- Use `httpx` directly for GraphQL APIs (Fireflies, Linear). Don't install wrapper SDKs unless they add significant value. Raw GraphQL with typed Pydantic models is more maintainable.
- Use `google-api-python-client` for all Google APIs — it's the official client and handles OAuth token refresh.
- Exception: Consider `linear-api` PyPI package if raw GraphQL becomes tedious. It provides Pydantic models and automatic pagination. Evaluate during Phase 2.

---

### Infrastructure

| Component | Technology | Config | Why | Confidence |
|-----------|------------|--------|-----|------------|
| Panel hosting | Vercel | Static site (Vite build output) | Free tier: 100GB bandwidth/month. Static SPA deploy is trivial. Same platform as other agency projects. | HIGH |
| Engine hosting | Hetzner VPS | systemd service | Already running meeting-watcher.py. 48-core, 252GB RAM — wildly overprovisioned for this. | HIGH |
| WebSocket proxy | nginx | `proxy_pass` with `Upgrade` headers | TLS termination for WSS. Zoom iframe requires HTTPS/WSS. nginx on VPS handles this. | HIGH |
| TLS | Let's Encrypt | certbot + nginx | Free, auto-renewing. Required for Zoom Apps (HTTPS-only iframes). | HIGH |
| Process manager | systemd | `meeting-copilot-engine.service` | Production process management on Linux. Auto-restart, logging via journalctl. | HIGH |
| DNS | Existing domain | Subdomain: `copilot-api.yourdomain.com` | Point a subdomain to VPS IP for the WebSocket/API endpoint. | HIGH |

**What NOT to use for infra:**

| Technology | Why Not |
|------------|---------|
| Docker / Kubernetes | Single VPS, single process. Docker adds a layer with no benefit here. |
| PM2 | Node.js process manager. Use systemd for Python. |
| Cloudflare Workers | Can't run WebSocket servers (they're stateless edge functions). |
| Railway / Render | Additional hosting cost and complexity when VPS already exists. |

---

### Dev Tooling

| Tool | Purpose | Why |
|------|---------|-----|
| Biome | Linting + formatting (panel) | Replaces ESLint + Prettier with one tool. Faster, simpler config. Rust-based. |
| Ruff | Linting + formatting (engine) | Replaces flake8 + black + isort for Python. Rust-based, instant. |
| mypy | Type checking (engine) | Catch type errors in WebSocket message handling and API calls. |
| vitest | Testing (panel) | Vite-native test runner. No config needed. |
| pytest + pytest-asyncio | Testing (engine) | Standard Python async testing. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Panel build tool | Vite | Next.js | No SSR needed in iframe. Vite is lighter, faster, simpler for SPA. |
| Panel build tool | Vite | Create React App | Deprecated. Vite is the replacement. |
| State management | Zustand | Jotai | Both fine. Zustand has clearer patterns for WebSocket message → store updates. |
| State management | Zustand | Redux Toolkit | Too much boilerplate for a sidebar panel. |
| WebSocket (panel) | react-use-websocket | Native WebSocket | react-use-websocket handles reconnection, heartbeat, shared connections for free. |
| WebSocket (engine) | FastAPI native | python-socketio | FastAPI's built-in WebSocket is simpler and avoids Socket.IO protocol overhead. |
| AI routing | LiteLLM | Manual fallback code | LiteLLM handles retries, rate limits, provider switching automatically. Hand-rolling this is a waste. |
| AI routing | LiteLLM | OpenRouter | OpenRouter is a proxy service (adds latency, cost). LiteLLM is a local library — zero overhead. |
| Task queue | asyncio.Queue | Celery | Tasks are local subprocess spawns, not distributed work. Celery + Redis is massive overkill. |
| HTTP client (Python) | httpx | aiohttp | httpx has cleaner API, better typing, sync+async in one library. aiohttp is fine but httpx is preferred in 2025/2026. |
| HTTP client (Python) | httpx | requests | requests is sync-only. The engine is fully async. |
| CSS | Tailwind | CSS Modules | Tailwind is faster to iterate with for a compact UI. No context-switching between files. |

---

## Installation

### Panel (React SPA)

```bash
# Scaffold
npm create vite@latest meeting-copilot-panel -- --template react-ts
cd meeting-copilot-panel

# Core
npm install @zoom/appssdk react-use-websocket zustand

# Styling
npm install tailwindcss @tailwindcss/vite

# Icons
npm install lucide-react

# Dev tools
npm install -D @biomejs/biome vitest @testing-library/react
```

### Engine (Python)

```bash
cd engine

# Create venv
python3.12 -m venv .venv
source .venv/bin/activate

# Core
pip install fastapi uvicorn[standard] litellm httpx pydantic python-dotenv

# Google APIs
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Dev tools
pip install ruff mypy pytest pytest-asyncio
```

### nginx WebSocket Proxy

```nginx
# /etc/nginx/sites-available/meeting-copilot
server {
    listen 443 ssl;
    server_name copilot-api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/copilot-api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/copilot-api.yourdomain.com/privkey.pem;

    # WebSocket endpoint
    location /ws {
        proxy_pass http://127.0.0.1:8900;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;  # Keep WebSocket alive for 24h
    }

    # REST API endpoint
    location /api {
        proxy_pass http://127.0.0.1:8901;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # CORS headers for Zoom iframe
    add_header Access-Control-Allow-Origin "https://your-panel.vercel.app" always;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Authorization, Content-Type" always;

    # CSP for Zoom compatibility
    add_header Content-Security-Policy "
        default-src 'self';
        connect-src 'self' wss://copilot-api.yourdomain.com *.zoom.us;
        script-src 'self' *.zoom.us 'unsafe-eval';
        frame-ancestors *.zoom.us;
    " always;
}
```

---

## Architecture Decision: Why NOT Next.js for the Panel

This deserves extra explanation because Next.js is the default choice for the agency's other projects.

**The Zoom iframe context changes everything:**

1. **No server rendering.** The panel loads inside Zoom's embedded Chromium browser. There's no SEO, no initial HTML to crawl, no benefit from SSR/SSG.

2. **No API routes.** The panel talks to the VPS engine via WebSocket. Next.js API routes would be a second backend — unnecessary complexity.

3. **No middleware.** Auth is handled by Zoom's OAuth flow (SDK-side) and the engine's WebSocket auth. Next.js middleware has nothing to do.

4. **Bundle size matters.** Zoom's sidebar is narrow (300-400px) and loads in the meeting client. A 42KB Vite bundle loads faster than a 92KB Next.js bundle. Every millisecond matters when a user opens the panel during a meeting.

5. **Deployment is simpler.** `vite build` produces a static `dist/` folder. Deploy to Vercel as a static site. No server functions, no edge runtime, no cold starts.

**When to reconsider:** If the panel ever needs its own API (e.g., for webhooks from Zoom), add a lightweight Vercel serverless function rather than switching to Next.js.

---

## Architecture Decision: Single FastAPI Process vs Separate Services

**Recommendation: Single FastAPI process serving both WebSocket (port 8900) and REST (port 8901).**

Actually, use a single port with path-based routing:
- `wss://copilot-api.yourdomain.com/ws` -- WebSocket
- `https://copilot-api.yourdomain.com/api/...` -- REST

FastAPI handles both natively. One process = shared state (meeting context, task queue, agent status). No need for Redis or IPC between services.

**When to split:** If WebSocket connections grow beyond ~100 concurrent (they won't -- this is a single-user app), or if the REST API needs independent scaling.

---

## Cost Analysis ($0 Budget Verification)

| Component | Cost | Notes |
|-----------|------|-------|
| Vercel (panel hosting) | $0 | Free tier, static site, well under 100GB bandwidth |
| VPS (engine) | $0 additional | Already paid for, running agents |
| Gemini API | $0 | Free tier: 15 RPM, 1M tokens/day |
| OpenAI API | ~$0.01/meeting | GPT-4o-mini fallback only. $0.15/1M input tokens. ~5K tokens/meeting = fractions of a cent |
| Claude API | $0 | No credits, lowest-priority fallback |
| Fireflies API | $0 | Free with existing subscription |
| Linear API | $0 | Free with existing plan |
| Google APIs | $0 | Free tier, well under quotas |
| Let's Encrypt | $0 | Free TLS |
| Domain | $0 | Subdomain on existing domain |
| **Total per month** | **~$0** | OpenAI fallback costs negligible |

---

## Sources

- [@zoom/appssdk npm](https://www.npmjs.com/package/@zoom/appssdk) -- v0.16.36, latest as of Dec 2025 (HIGH confidence)
- [Zoom Apps SDK reference](https://appssdk.zoom.us/) -- Official API docs (HIGH)
- [Zoom Apps Advanced React Sample](https://github.com/zoom/zoomapps-advancedsample-react) -- Official starter (HIGH)
- [FastAPI WebSockets docs](https://fastapi.tiangolo.com/advanced/websockets/) -- Official (HIGH)
- [FastAPI latest v0.135.x](https://pypi.org/project/fastapi/) -- PyPI (HIGH)
- [LiteLLM docs](https://docs.litellm.ai/) -- Official, actively updated March 2026 (HIGH)
- [LiteLLM PyPI](https://pypi.org/project/litellm/) -- Latest release March 2026 (HIGH)
- [react-use-websocket npm](https://www.npmjs.com/package/react-use-websocket) -- v4.13.0 (MEDIUM -- last published ~1 year ago, may not support React 19 officially)
- [Fireflies API docs](https://docs.fireflies.ai/) -- GraphQL reference (HIGH)
- [Fireflies addToLiveMeeting](https://docs.fireflies.ai/graphql-api/mutation/add-to-live) -- Rate limit: 3/20min (HIGH)
- [Linear API docs](https://linear.app/developers/graphql) -- GraphQL API (HIGH)
- [linear-api PyPI](https://pypi.org/project/linear-api/) -- Python wrapper with Pydantic models (MEDIUM)
- [Vite getting started](https://vite.dev/guide/) -- Official docs (HIGH)
- [Vercel limits](https://vercel.com/docs/limits) -- Free tier specs (HIGH)
- [Zoom CSP requirements](https://devforum.zoom.us/t/what-is-an-appropiate-content-security-policy-csp-for-embedding-an-application-on-the-zoom-client/73158) -- Community-confirmed CSP directives (MEDIUM)
- [Gmail API quotas](https://developers.google.com/workspace/gmail/api/reference/quota) -- Official (HIGH)
- [Google Calendar API quotas](https://developers.google.com/workspace/calendar/api/guides/quota) -- Official (HIGH)

---

## Open Questions / Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `react-use-websocket` may not officially support React 19 | LOW | Library uses standard hooks; likely works fine. Test early. Fallback: custom `useWebSocket` hook (~50 lines). |
| Zoom Apps SDK `getMeetingContext()` may not return attendee emails | MEDIUM | Zoom privacy restrictions may limit attendee data. May need to cross-reference with Calendar API invite list instead. Test during Zoom app registration. |
| Fireflies live transcript polling has 30s lag | LOW | Acceptable for this use case. No real-time streaming alternative exists in Fireflies API. |
| LiteLLM adds dependency weight | LOW | Worth it for the fallback chain logic. Alternative is ~200 lines of custom retry/fallback code. |
| Vercel CSP headers for Zoom iframe compatibility | MEDIUM | Need to configure `vercel.json` headers for `frame-ancestors *.zoom.us`. Test during panel deployment. |
| Single FastAPI process WebSocket state loss on restart | LOW | Single-user app. Meeting context can be reconstructed from Fireflies + Calendar on reconnect. Add reconnection logic to panel. |
