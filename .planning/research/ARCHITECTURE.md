# Architecture Patterns

**Domain:** Real-time meeting intelligence + execution system
**Researched:** 2026-03-20

## System Overview

Two-process architecture with five logical components bridged by WebSocket:

```
                         ZOOM DESKTOP CLIENT
                    +---------------------------+
                    |   Meeting Side Panel      |
                    |   (React iframe)          |
                    |   served from Vercel      |
                    +---------------------------+
                              |
                              | WSS (port 443 via nginx)
                              |
+--------------------------------------------------------------+
|                     VPS (Hetzner)                             |
|                                                              |
|  +-----------------+     +------------------+                |
|  | Copilot Engine  |     | WebSocket Server |                |
|  | (Python)        |<--->| (Python/asyncio) |                |
|  |                 |     | port 8900        |                |
|  | - Context Loader|     +------------------+                |
|  | - Classifier    |              ^                          |
|  | - Orchestrator  |              | events                   |
|  | - State Manager |              v                          |
|  +-----------------+     +------------------+                |
|         |                | REST API         |                |
|         |                | port 8901        |                |
|         v                +------------------+                |
|  +-----------------+                                         |
|  | Fleet Agents    |                                         |
|  | agent1-4        |                                         |
|  | (Claude Code)   |                                         |
|  +-----------------+                                         |
+--------------------------------------------------------------+
          |                    |                    |
          v                    v                    v
   +------------+      +------------+      +------------+
   | Fireflies  |      | Linear     |      | Google     |
   | (transcr.) |      | (projects) |      | (contacts, |
   +------------+      +------------+      |  calendar) |
                                           +------------+
```

## Component Boundaries

### Component 1: Zoom Side Panel (Frontend)

**Responsibility:** UI rendered inside Zoom's embedded browser iframe. Displays live task feed, agent status, quick action buttons, meeting context summary.

**Technology:** Next.js on Vercel (static export or SSR)

**Deployed on:** Vercel (HTTPS required by Zoom)

**Communicates with:**
- WebSocket Server on VPS (real-time events)
- REST API on VPS (initial state snapshot on load)
- Zoom Apps SDK (`@zoom/appssdk`) for meeting context

**Zoom Apps SDK Key Facts (HIGH confidence -- from official SDK docs):**
- Must call `zoomSdk.config({ capabilities: [...] })` before any API calls
- `getMeetingParticipantsEmail()` returns participant emails (requires consent)
- `getMeetingContext()` returns meeting UUID and basic info
- `onParticipantChange()` fires when users join/leave
- `onActiveSpeakerChange()` fires on speaker changes
- `postMessage()` for cross-instance communication (512KB limit)
- `sendMessage()` broadcasts to all participants (1KB limit)
- Embedded browser does NOT support Web Notification API (use `zoomSdk` push notifications instead)
- All external domains must be whitelisted in Zoom Marketplace app configuration
- DevTools are disabled by default; enable via `defaults write ZoomChat webview.context.menu true` on macOS

**CSP / Iframe Constraints (MEDIUM confidence):**
- Zoom's embedded browser blocks requests to domains not in the Domain Allow List
- Must whitelist: Vercel app domain, VPS WebSocket domain, `appssdk.zoom.us`
- The app runs in Zoom's custom Chromium, not a standard browser -- some Web APIs may be unavailable
- Session cookies work within the embedded browser
- No `localStorage`/`sessionStorage` persistence guarantee across app restarts

**OAuth Flow for Private/Internal App (MEDIUM confidence):**
1. Register app on marketplace.zoom.us as "Zoom App" type
2. Set app to "Account-level" (private, no marketplace review)
3. Configure Home URL pointing to Vercel deployment
4. Configure OAuth redirect URL to backend on VPS
5. Backend exchanges auth code for access/refresh tokens, stores in Redis or file
6. In-client OAuth: user authorizes within the Zoom embedded browser
7. Session cookie persists auth state for subsequent requests

### Component 2: WebSocket Server

**Responsibility:** Bidirectional real-time communication bridge between VPS engine and Zoom panel. Handles auth, connection lifecycle, message routing.

**Technology:** Python `asyncio` + `websockets` library (matches engine language)

**Port:** 8900 (proxied through nginx with TLS)

**Architecture pattern:**

```
Panel connects to: wss://copilot.yourdomain.com/ws
nginx terminates TLS, proxies to localhost:8900

Authentication flow:
1. Panel loads, gets meeting UUID from zoomSdk.getMeetingContext()
2. Panel requests auth token from REST API: POST /api/auth { meeting_id, zoom_user_id }
3. REST API validates via Zoom OAuth token, returns short-lived JWT
4. Panel connects to WSS with JWT in query param or first message
5. WebSocket server validates JWT, associates connection with meeting
```

**Why WebSocket on VPS, not Vercel:**
- Vercel serverless functions are stateless and ephemeral -- no persistent WebSocket connections (HIGH confidence, confirmed by Vercel docs and community)
- VPS provides persistent process, can maintain connection state in memory
- nginx reverse proxy handles TLS termination and WebSocket upgrade

**nginx configuration pattern:**
```nginx
location /ws {
    proxy_pass http://127.0.0.1:8900;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400;  # 24h keepalive
}
```

**Message protocol (recommended):**
```json
{
  "type": "event_type",
  "payload": { ... },
  "ts": "2026-03-20T10:30:00Z",
  "meeting_id": "abc123"
}
```

Event types (engine -> panel):
- `transcript.new` -- new classified transcript lines
- `task.created` -- action item detected, Linear issue created
- `task.status` -- agent started/completed/failed work
- `agent.spawned` -- fleet agent started on a task
- `agent.completed` -- fleet agent finished
- `context.loaded` -- meeting context ready (attendees, project, history)
- `decision.logged` -- decision captured
- `meeting.ended` -- meeting concluded, summary available

Event types (panel -> engine):
- `action.delegate` -- user clicked "Delegate Task" with description
- `action.research` -- user clicked "Research This"
- `action.email` -- user clicked "Draft Email"
- `action.proposal` -- user clicked "Create Proposal"
- `action.domain` -- user clicked "Check Domain"
- `action.custom` -- free-form command from panel

### Component 3: Copilot Engine

**Responsibility:** Core intelligence -- polls transcripts, loads context, classifies intents, orchestrates agents, manages meeting state.

**Technology:** Python (extends existing `meeting-watcher.py`)

**Runs on:** VPS as a persistent process (PM2 or systemd)

**Sub-components:**

#### 3a. Transcript Ingestion

**Two options (choose one):**

**Option A: Fireflies polling (current, working)**
- Poll `active_meetings` every 30s
- Fetch new sentences via GraphQL `transcript.sentences`
- Deduplicate by text hash
- Pros: Already built, works, zero Zoom marketplace complexity
- Cons: 30s latency, requires Fireflies bot in meeting, duplicate bot instances

**Option B: Zoom RTMS (Real-Time Media Streams) -- RECOMMENDED for v2**
- WebSocket-based live transcript stream directly from Zoom
- Python SDK: `pip install rtms` (requires Python 3.10+)
- Provides per-participant transcript with speaker attribution
- No third-party bot needed in meeting
- Pros: Lower latency (~2-3s), no bot joining meeting, native Zoom integration
- Cons: Requires Zoom RTMS app registration, additional OAuth scope, beta as of early 2026
- **Confidence:** MEDIUM -- SDK exists, documented, but requires account-level RTMS enablement which may need Zoom admin approval

**Recommendation:** Start with Fireflies (Phase 1-2) since it already works. Add RTMS as Phase 3+ upgrade. The architecture should abstract the transcript source so swapping is easy.

```python
# Abstract interface
class TranscriptSource(ABC):
    async def start(self, meeting_id: str): ...
    async def get_new_sentences(self) -> List[Sentence]: ...
    async def stop(self): ...

class FirefliesSource(TranscriptSource): ...  # Phase 1
class ZoomRTMSSource(TranscriptSource): ...   # Phase 3
```

#### 3b. Context Engine

**Triggers on:** Meeting detected (calendar event or Zoom process active)

**Data loading sequence:**
```
1. Calendar event → extract attendee emails, meeting title
2. Google Contacts → match emails to names, companies, phone numbers
3. Obsidian vault → load client profile if exists
4. Linear API → find projects associated with attendee email/company
5. Fireflies API → fetch last 3 transcripts with these attendees
6. Gmail → recent thread subjects with attendee email
```

**Output:** `MeetingContext` object:
```python
@dataclass
class MeetingContext:
    meeting_id: str
    title: str
    attendees: List[Attendee]     # name, email, company, role
    meeting_type: str              # "client" | "internal" | "prospect"
    primary_project: LinearProject # most likely project
    related_projects: List[LinearProject]
    prior_meetings: List[MeetingSummary]  # last 3 with this group
    open_issues: List[LinearIssue]        # assigned/recent in project
    client_profile: Optional[dict]        # from Obsidian
```

**Meeting type detection heuristic:**
- If attendee emails contain `@aiacrobatics.com` or known team emails (Hitesh, etc.) -> `internal`
- If attendee matched to existing client profile -> `client`
- If attendee has no prior meeting history -> `prospect`

**Project association strategy:**
1. Check Linear for projects where attendee email appears as member/subscriber
2. Check Obsidian client profile for linked Linear project IDs
3. Fuzzy match meeting title against Linear project names
4. If no match found and attendee is a known client, use their primary project
5. For internal meetings, default to a "General" project but allow multi-project switching

#### 3c. Intent Detector (upgraded classifier)

**Current state:** Sentence-level classification into 5 categories (ACTION_ITEM, DECISION, FOLLOW_UP, QUESTION, INFO) using LLM with keyword fallback.

**Upgraded architecture:**

```
Raw transcript lines (batched every 30s)
    |
    v
+-------------------+
| Context-Aware     |
| Intent Classifier |
|                   |
| Input:            |
| - 8 sentences     |
| - MeetingContext   |
| - conversation    |
|   history         |
|                   |
| Output:           |
| - classification  |
| - extracted_task   |
| - assignee        |
| - project_hint    |
| - urgency         |
| - dependencies    |
+-------------------+
    |
    v
IntentEvent -> pushed to orchestrator queue
```

**Key upgrade:** The classifier prompt now includes meeting context:
```
You are classifying transcript lines from a meeting with {attendee_names}.
This meeting is about project: {project_name}.
Known open issues: {issue_titles}.
Meeting type: {client/internal}.

When someone says "fix the login page", route it to project {project_name}.
When someone says "now about the copilot", switch active project context.
```

**Project-switching detection:** For internal meetings, detect phrases like:
- "Now about [project]...", "Moving on to [project]...", "Regarding [client]..."
- Emit a `context.switch` event that updates the active project routing

#### 3d. Task Orchestrator

**Pattern: Event-driven queue with worker pool**

**Why event-driven queue, not direct spawn:**
- Multiple intents may be detected in the same batch -- need ordering
- Some tasks depend on others ("research X then draft email about it")
- Agent slots are limited (agent1-4 = 4 concurrent)
- Need retry/failure handling
- Panel needs status updates at each stage

```
IntentEvent
    |
    v
+-------------------+      +--------------------+
| Task Queue        |----->| Agent Pool         |
| (in-memory deque  |      | agent1: busy/idle  |
|  or Redis list)   |      | agent2: busy/idle  |
|                   |      | agent3: busy/idle  |
| Priority:         |      | agent4: busy/idle  |
| 1. Delegate Task  |      +--------------------+
| 2. ACTION_ITEM    |              |
| 3. FOLLOW_UP      |              | spawn
| 4. Research        |              v
| 5. Draft Email    |      +--------------------+
+-------------------+      | Claude Code        |
                           | (subprocess)       |
                           | with task prompt    |
                           +--------------------+
                                   |
                                   | status events
                                   v
                           WebSocket -> Panel
```

**Agent spawn mechanism:**
```python
async def spawn_agent(agent_id: str, task: Task):
    # Prepare task prompt with full context
    prompt = build_agent_prompt(task, meeting_context)

    # Spawn Claude Code as subprocess
    proc = await asyncio.create_subprocess_exec(
        'claude', '--print', '--dangerously-skip-permissions',
        '-p', prompt,
        '--model', 'sonnet',
        cwd=task.working_directory,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Stream status updates to panel
    await ws_broadcast({
        'type': 'agent.spawned',
        'agent_id': agent_id,
        'task': task.summary
    })

    # Wait for completion
    stdout, stderr = await proc.communicate()

    await ws_broadcast({
        'type': 'agent.completed',
        'agent_id': agent_id,
        'result': parse_result(stdout)
    })
```

**For in-memory queue (Phase 1):** Use Python `asyncio.Queue` -- simple, no external deps.
**For persistent queue (Phase 2+):** Use Redis list with `BRPOP` -- survives engine restart, supports priority.

### Component 4: REST API

**Responsibility:** Stateless snapshot endpoint for panel initialization and OAuth callbacks.

**Technology:** Python `aiohttp` (same event loop as WebSocket server)

**Port:** 8901 (proxied through nginx)

**Endpoints:**
```
GET  /api/meeting/current    -> current meeting state, context, active tasks
GET  /api/meeting/:id/tasks  -> task list with statuses for a meeting
POST /api/auth               -> exchange Zoom OAuth for session JWT
POST /api/action             -> trigger action (fallback if WS disconnected)
GET  /api/health             -> healthcheck for monitoring
```

### Component 5: Linear Project Router

**Responsibility:** Match transcript mentions and detected intents to the correct Linear project for issue creation.

**Strategy (multi-signal):**

```
Signal 1: Attendee-based (highest weight)
  - Meeting with client X -> their Linear project
  - Loaded in Context Engine at meeting start

Signal 2: Explicit mention
  - "for the Axel Towing project" -> fuzzy match against project names
  - "on the pick a partner app" -> fuzzy match

Signal 3: Project switch detection
  - "Now about the copilot..." -> search Linear projects for "copilot"
  - Updates active_project in meeting state

Signal 4: Content similarity
  - Issue title mentions "login page" -> check which project has login-related issues
  - Lower confidence, used as tiebreaker

Fallback: active_project (set at meeting start from attendee context)
```

**Linear API queries needed:**
```graphql
# Find projects by team
query { teams { nodes { id name projects { nodes { id name } } } } }

# Search issues (for content matching)
query { issueSearch(query: "login page") { nodes { id title project { id name } } } }

# Create issue in specific project
mutation { issueCreate(input: { title: "...", projectId: "...", teamId: "..." }) { ... } }
```

## Data Flow: End-to-End

```
1. MEETING DETECTED
   Calendar event fires 5min before meeting
   OR Zoom process detected on MacBook Pro
   |
   v
2. CONTEXT LOADING (5-10 seconds)
   Google Calendar -> attendee emails
   Google Contacts -> attendee profiles
   Obsidian vault  -> client profile
   Linear API      -> associated projects + open issues
   Fireflies API   -> prior meeting summaries
   |
   v
   MeetingContext object assembled
   Panel notified: { type: "context.loaded", payload: MeetingContext }
   |
   v
3. TRANSCRIPT POLLING (every 30 seconds)
   Fireflies GraphQL -> new sentences
   Deduplicate by text hash
   Append to conversation buffer
   |
   v
4. CLASSIFICATION (batches of 8 sentences)
   Context-injected LLM prompt
   Gemini (primary) -> Claude (fallback) -> Keywords (last resort)
   |
   v
   Classified sentences with: category, task, assignee, project_hint
   |
   v
5. ROUTING
   Non-INFO classifications -> Task Queue
   Project determined by: attendee context > explicit mention > active project
   |
   v
6. EXECUTION
   ACTION_ITEM -> Create Linear issue in correct project
                  If complex ("build a landing page") -> spawn fleet agent
   FOLLOW_UP   -> Create Linear issue + queue email draft
   DECISION    -> Log to Obsidian meeting notes
   QUESTION    -> If researchable, spawn research agent
   |
   v
7. PANEL UPDATE (real-time via WebSocket)
   { type: "task.created", payload: { title, project, status } }
   { type: "agent.spawned", payload: { agent_id, task_summary } }
   { type: "agent.completed", payload: { agent_id, result_summary } }
   |
   v
8. MEETING END
   Generate full summary (Fireflies API or local from conversation buffer)
   Draft follow-up email
   Close WebSocket connection
   Archive meeting state
```

## Build Order (Dependency-Driven)

Components have clear dependencies that dictate phase ordering:

```
Phase 1: Engine Core (no Zoom dependency)
  [Context Engine] -> [Upgraded Classifier] -> [WebSocket Server]

  WHY FIRST: These components work without the Zoom panel.
  Test with iMessage output (already working).
  Context Engine needs to be solid before routing works.

Phase 2: Panel + WebSocket Bridge
  [Zoom App Registration] -> [Panel UI] -> [WebSocket Client]

  WHY SECOND: Depends on WebSocket server from Phase 1.
  Zoom app registration has its own lead time.
  Panel is display-only initially (no action buttons yet).

Phase 3: Task Orchestration + Fleet
  [Task Queue] -> [Agent Pool Manager] -> [Agent Spawn Logic]

  WHY THIRD: Depends on working classifier (Phase 1)
  and panel for status display (Phase 2).
  Most complex component -- benefits from stable foundation.

Phase 4: Project Router + Quick Actions
  [Multi-Project Router] -> [Panel Action Buttons] -> [RTMS Integration]

  WHY FOURTH: Depends on all prior components.
  Project routing is refinement of working system.
  RTMS is optimization replacing Fireflies polling.
```

**Critical path:** Context Engine -> Classifier -> WebSocket -> Panel -> Orchestrator

**Parallelizable:** Zoom App Registration can happen during Phase 1 (it is admin config, not code). Panel UI wireframing can happen during Phase 1.

## Patterns to Follow

### Pattern 1: Abstract Transcript Source
**What:** Interface over transcript ingestion so Fireflies and RTMS are interchangeable.
**When:** From Phase 1 onward.
**Why:** Avoids rewrite when adding RTMS. Test with mock transcript source.

### Pattern 2: Event Bus (Internal)
**What:** All components communicate through typed events on an internal bus, not direct function calls.
**When:** Core engine design.
**Why:** Decouples classifier from orchestrator from panel updates. Makes testing easy (inject events, assert outputs).

```python
class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def on(self, event_type: str, handler: Callable):
        self._handlers.setdefault(event_type, []).append(handler)

    async def emit(self, event_type: str, payload: dict):
        for handler in self._handlers.get(event_type, []):
            await handler(payload)

# Usage
bus = EventBus()
bus.on('transcript.classified', orchestrator.handle_classified)
bus.on('task.created', ws_server.broadcast_to_panel)
bus.on('task.created', obsidian.log_to_meeting_notes)
```

### Pattern 3: Meeting State Machine
**What:** Explicit state transitions for meeting lifecycle.
**When:** Engine state management.
**Why:** Prevents race conditions, makes debugging clear.

```
IDLE -> DETECTED -> CONTEXT_LOADING -> ACTIVE -> ENDING -> SUMMARIZING -> IDLE
```

### Pattern 4: Reconnecting WebSocket Client (Panel Side)
**What:** Panel auto-reconnects with exponential backoff on disconnect.
**When:** Panel WebSocket implementation.
**Why:** Zoom meetings last 30-60+ minutes. Network blips happen. Panel must recover gracefully.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Polling from Panel to VPS
**What:** Panel uses `setInterval` to poll REST API for updates.
**Why bad:** High latency (seconds vs milliseconds), unnecessary load, poor UX.
**Instead:** WebSocket push from engine to panel. REST only for initial state load.

### Anti-Pattern 2: Storing Auth Tokens in Panel Frontend
**What:** Zoom OAuth tokens stored in browser/iframe state.
**Why bad:** Zoom's embedded browser has unreliable storage. Token refresh is server-side concern.
**Instead:** Backend holds all tokens. Panel gets a session JWT for WebSocket auth.

### Anti-Pattern 3: Tight Coupling Engine to Panel
**What:** Engine code directly sends WebSocket messages instead of going through event bus.
**Why bad:** Engine becomes untestable without panel. Can't run engine in "headless" mode (iMessage only).
**Instead:** Engine emits events. WebSocket handler subscribes to events and forwards to panel.

### Anti-Pattern 4: One Agent Per Transcript Line
**What:** Spawning a fleet agent for every ACTION_ITEM detected.
**Why bad:** Agents take 30-120 seconds to complete. 4 agents max. Queue fills instantly.
**Instead:** Queue with priority. Simple items (create Linear issue) handled inline. Only complex tasks ("build a landing page") get agent spawning.

### Anti-Pattern 5: Hardcoded Project Routing
**What:** `if "axel" in text: project = AXEL_PROJECT_ID`
**Why bad:** Doesn't scale, breaks with new clients, fragile.
**Instead:** Dynamic routing via Linear API search + attendee context + fuzzy matching.

## Scalability Considerations

| Concern | Julian-only (v1) | Multi-user (v2+) |
|---------|-------------------|-------------------|
| WebSocket connections | 1 concurrent | Need connection manager per meeting |
| Meeting state | Single `dict` in memory | Redis with meeting_id keys |
| Agent pool | agent1-4 shared | Per-user agent allocation |
| Auth | Single Zoom OAuth token | Token store per user |
| Linear routing | Julian's teams only | Multi-workspace support |
| Transcript source | Fireflies (Julian's account) | RTMS (per-meeting, no account needed) |

For v1 (Julian-only), in-memory state and a single WebSocket connection are sufficient. Do not over-engineer for multi-user until v2.

## Technology Choices (Architecture-Relevant)

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Panel framework | Next.js 15 + React 19 | Same stack as all other projects, Vercel native |
| Panel hosting | Vercel | Free tier, HTTPS by default, required by Zoom |
| WebSocket server | Python `websockets` + `asyncio` | Same language as engine, native async |
| REST API | Python `aiohttp` | Same event loop as WebSocket, lightweight |
| Event bus | Custom (50 lines of Python) | No external dependency needed at this scale |
| Task queue | `asyncio.Queue` (Phase 1), Redis (Phase 2+) | Start simple, add persistence later |
| State persistence | JSON file (Phase 1), Redis (Phase 2+) | Meeting watcher already uses JSON state file |
| TLS termination | nginx | Already running on VPS for other services |
| Auth tokens | JWT (short-lived, for WS auth) | Stateless validation, no session store needed |

## Zoom RTMS: Future Architecture Note

RTMS (HIGH confidence it exists -- official Zoom SDK) provides direct WebSocket transcript streaming from Zoom meetings without needing Fireflies. Architecture implications:

**If/when RTMS is adopted (Phase 3+):**
1. Engine receives transcript directly from Zoom via RTMS WebSocket
2. Fireflies bot no longer needed in meetings
3. Latency drops from ~30s (polling) to ~2-3s (streaming)
4. Speaker attribution comes from Zoom (more accurate than Fireflies)
5. No duplicate bot instances problem
6. Requires RTMS-enabled Zoom app type and account admin approval

**Architecture is designed to support this swap** via the `TranscriptSource` abstraction. The classifier, orchestrator, and panel are all transcript-source-agnostic.

## Sources

- [Zoom Apps SDK Reference v0.16.36](https://appssdk.zoom.us/classes/ZoomSdk.ZoomSdk.html) -- HIGH confidence
- [Zoom Apps Advanced React Sample](https://github.com/zoom/zoomapps-advancedsample-react) -- HIGH confidence
- [Zoom RTMS Documentation](https://developers.zoom.us/docs/rtms/) -- HIGH confidence (exists, details need verification)
- [Zoom RTMS Python/Node SDK](https://github.com/zoom/rtms) -- HIGH confidence
- [Fireflies Realtime API Overview](https://docs.fireflies.ai/realtime-api/overview) -- MEDIUM confidence (beta)
- [Vercel WebSocket Limitations](https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections) -- HIGH confidence
- [Zoom CSP Forum Discussion](https://devforum.zoom.us/t/what-is-an-appropiate-content-security-policy-csp-for-embedding-an-application-on-the-zoom-client/73158) -- MEDIUM confidence
- [Zoom App Build Flow](https://developers.zoom.us/docs/build-flow/) -- HIGH confidence
- [Zoom Private App Distribution](https://developers.zoom.us/docs/distribute/app-submission/enabling-publishing-for-private-and-beta-apps/) -- MEDIUM confidence
- [MeetStream NLP Action Extraction](https://blog.meetstream.ai/extracting-action-items-and-tasks-using-nlp/) -- LOW confidence (third party)
