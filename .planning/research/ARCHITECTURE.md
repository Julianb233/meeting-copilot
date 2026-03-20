# Architecture Patterns

**Domain:** AI Meeting Companion Panel (Zoom Sidebar)
**Researched:** 2026-03-20

---

## Recommended Architecture

```
                    ZOOM CLIENT (MacBook Pro)
                    +---------------------------+
                    |  Zoom Meeting Window       |
                    |                            |
                    |  +--------------------+    |
                    |  | COMPANION PANEL    |    |
                    |  | (React SPA)        |    |
                    |  |                    |    |
                    |  | - Task Feed        |    |
                    |  | - Agent Status     |    |
                    |  | - Quick Actions    |    |
                    |  | - Meeting Context  |    |
                    |  +--------+-----------+    |
                    +-----------|---------------+
                                |
                           WSS (TLS)
                                |
                    +-----------v---------------+
                    |  HETZNER VPS               |
                    |                            |
                    |  nginx (TLS termination)   |
                    |      |                     |
                    |      v                     |
                    |  COPILOT ENGINE (FastAPI)   |
                    |  +------------------------+|
                    |  | WebSocket Handler      ||
                    |  | REST API Handler       ||
                    |  |                        ||
                    |  | Meeting State Manager  ||
                    |  |   +------------------+ ||
                    |  |   | Context Engine   | ||
                    |  |   | Intent Classifier| ||
                    |  |   | Task Orchestrator| ||
                    |  |   +------------------+ ||
                    |  +------------------------+|
                    |      |          |          |
                    |  Fireflies   Fleet Agents  |
                    |  (polling)   (subprocess)  |
                    +----------------------------+
                                |
                    +-----------v---------------+
                    |  EXTERNAL SERVICES         |
                    |  - Fireflies (GraphQL)     |
                    |  - Linear (GraphQL)        |
                    |  - Gmail (REST)            |
                    |  - Google Calendar (REST)  |
                    |  - Google Contacts (REST)  |
                    |  - Obsidian (filesystem)   |
                    |  - LLM APIs (via LiteLLM)  |
                    +----------------------------+
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Panel UI** | Display meeting state, task feed, agent status. Send quick action commands. | Engine (via WebSocket) |
| **Engine: WebSocket Handler** | Accept panel connections, broadcast state updates, receive commands. | Panel, Meeting State Manager |
| **Engine: REST API** | Serve snapshot of current meeting state for debugging/monitoring. | External tools, browser |
| **Engine: Meeting State Manager** | Central state machine. Tracks meeting lifecycle, accumulated intents, active tasks. | All engine components |
| **Engine: Context Engine** | On meeting start, load attendee identity, project mapping, meeting history. | Google APIs, Linear, Obsidian, Fireflies |
| **Engine: Intent Classifier** | Process transcript chunks through LLM fallback chain. Classify into actionable intents. | LiteLLM, Meeting State Manager |
| **Engine: Task Orchestrator** | Queue and dispatch tasks to fleet agents. Track task status. Report completions. | Fleet Agents (subprocess), Meeting State Manager |
| **Engine: Transcript Poller** | Poll Fireflies API every 30s for new transcript chunks. Deduplicate. | Fireflies API, Intent Classifier |
| **Fleet Agents** | Execute work: create Linear issues, draft emails, research domains, scaffold code. | Claude Code CLI (subprocess), external APIs |

---

## Data Flow

### Meeting Lifecycle

```
1. MEETING DETECTED
   Calendar event starts OR Zoom process detected
   |
   v
2. CONTEXT LOADING (5-10 seconds)
   - Google Calendar: get event, extract attendee emails
   - Google Contacts: resolve emails to names, companies
   - Linear: find projects associated with attendees
   - Obsidian: load client profiles
   - Fireflies: fetch last 3 transcripts with same attendees
   |
   v
3. FIREFLIES BOT JOINED
   addToLiveMeeting mutation (if not auto-joined)
   |
   v
4. TRANSCRIPT POLLING LOOP (every 30s)
   Fireflies transcript query -> deduplicate -> new chunks
   |
   v
5. INTENT CLASSIFICATION (per chunk)
   New transcript text -> LiteLLM (Gemini -> OpenAI -> Claude -> Keywords)
   -> Classified intent: {type, content, confidence, project}
   |
   v
6. TASK DISPATCH (for actionable intents)
   Intent -> Task Orchestrator -> asyncio.Queue -> Fleet Agent subprocess
   |
   v
7. STATUS BROADCAST (continuous)
   State changes -> WebSocket broadcast -> Panel UI update
   |
   v
8. MEETING ENDED
   - Generate post-meeting summary
   - Draft follow-up email
   - Write Obsidian meeting notes
   - Final status broadcast
```

### WebSocket Message Protocol

```typescript
// Panel -> Engine (commands)
type PanelMessage =
  | { type: "quick_action"; action: "create_issue" | "draft_email" | "research" | "delegate" | "check_domain"; payload?: Record<string, unknown> }
  | { type: "ping" }

// Engine -> Panel (state updates)
type EngineMessage =
  | { type: "meeting_started"; context: MeetingContext }
  | { type: "intent_classified"; intent: ClassifiedIntent }
  | { type: "task_dispatched"; task: Task }
  | { type: "task_completed"; taskId: string; result: TaskResult }
  | { type: "task_failed"; taskId: string; error: string }
  | { type: "agent_status"; agents: AgentStatus[] }
  | { type: "transcript_chunk"; text: string; speaker: string; timestamp: number }
  | { type: "meeting_ended"; summary: MeetingSummary }
  | { type: "connection_ack"; meetingState: MeetingState }
  | { type: "pong" }
```

---

## Patterns to Follow

### Pattern 1: Event-Driven State Broadcasting

**What:** Engine maintains authoritative meeting state. On any state change, broadcast the delta to all connected panels via WebSocket.

**When:** Every time meeting state changes (new intent, task status change, agent status change).

**Why:** Panel is a thin view layer. It renders what the engine tells it. No business logic in the panel.

**Example:**
```python
# engine/state.py
class MeetingStateManager:
    def __init__(self, ws_handler):
        self.state = MeetingState()
        self.ws = ws_handler

    async def add_intent(self, intent: ClassifiedIntent):
        self.state.intents.append(intent)
        await self.ws.broadcast({
            "type": "intent_classified",
            "intent": intent.model_dump()
        })
```

### Pattern 2: Reconnection with State Sync

**What:** When panel reconnects (WebSocket drops), engine sends full current state as first message.

**When:** Every WebSocket connection open.

**Why:** Zoom may suspend the iframe when panel is minimized. On reopen, panel needs full state, not just new deltas.

**Example:**
```python
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    # Send full state on connect
    await ws.send_json({
        "type": "connection_ack",
        "meetingState": state_manager.state.model_dump()
    })
    # Then stream deltas
    ...
```

### Pattern 3: Subprocess Agent Spawning

**What:** Fleet agents are spawned as OS subprocesses via asyncio.create_subprocess_exec(). Not threads, not in-process.

**When:** Task orchestrator dispatches a classified intent that requires agent execution.

**Why:** Claude Code agents are separate processes with their own context windows. They need isolation. Subprocess gives clean lifecycle management (spawn, monitor, kill).

**Example:**
```python
async def spawn_agent(task: Task):
    proc = await asyncio.create_subprocess_exec(
        "claude", "--print", "--prompt", task.prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    return proc
```

### Pattern 4: Shared Type Definitions

**What:** Define WebSocket message types in a shared location that both panel (TypeScript) and engine (Python/Pydantic) use.

**When:** From day one.

**Why:** WebSocket messages are the contract between panel and engine. Type drift between frontend and backend is the number one source of real-time app bugs.

**Approach:** Define canonical types in Python (Pydantic models). Export JSON Schema. Generate TypeScript types from schema using json-schema-to-typescript or maintain manually (small enough for this project).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Business Logic in the Panel

**What:** Making the panel classify intents, call APIs, or make routing decisions.

**Why bad:** Panel runs in Zoom's iframe with CSP restrictions, limited resources, and no persistent state. If Zoom suspends the iframe, all in-flight logic is lost.

**Instead:** Panel is a display + command layer only. All intelligence lives in the engine.

### Anti-Pattern 2: Polling from the Panel

**What:** Panel polls the REST API for updates instead of using WebSocket.

**Why bad:** Adds latency (poll interval), wastes bandwidth, creates unnecessary load. The REST API exists for debugging/monitoring, not as the primary data channel.

**Instead:** WebSocket for all real-time updates. REST API is a secondary debugging tool.

### Anti-Pattern 3: Shared Database Between Panel and Engine

**What:** Using Supabase/Postgres as the communication layer between panel and engine.

**Why bad:** Adds a database dependency for real-time communication that WebSocket handles natively. Database polling is slower than WebSocket push. Adds hosting cost ($0 budget).

**Instead:** WebSocket for real-time. If persistence is needed later, add SQLite on the VPS (not a hosted database).

### Anti-Pattern 4: Monolithic Agent Tasks

**What:** Spawning a single agent with a massive prompt that does everything (create issue + draft email + update Obsidian).

**Why bad:** Long-running agents block. If one sub-task fails, the whole task fails. No granular status reporting.

**Instead:** One agent per atomic task. "Create Linear issue" is one agent. "Draft email" is another. Parallel execution, independent failure modes, granular status.

### Anti-Pattern 5: Storing Secrets in the Panel

**What:** Embedding API keys in the React app for direct API calls.

**Why bad:** Zoom iframe is a web page. View source exposes everything. CSP will not save you.

**Instead:** All API keys live in the engine's .env. Panel authenticates to the engine only.

---

## Scalability Considerations

| Concern | At 1 user (Julian) | At 5 users | At 50 users |
|---------|---------------------|------------|-------------|
| WebSocket connections | 1 connection, trivial | 5 connections, still trivial | Need connection pooling, consider multiple workers |
| Transcript polling | 1 meeting at a time | Could overlap (5 concurrent meetings) | Need per-meeting polling loops, rate limit management |
| Agent spawning | 4 fleet agents max | Agent contention (4 agents, 5 users) | Need agent pool management, queue priority |
| LLM API calls | ~2/minute (Gemini free tier fine) | ~10/minute (still fine) | Need paid tier, rate limit handling |
| State management | In-memory dict | In-memory dict per meeting | Need Redis or SQLite for state persistence |

**For v1 (Julian only):** In-memory state, single process, no persistence needed. Keep it simple.

---

## Sources

- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) -- WebSocket handler patterns
- [Python asyncio subprocess](https://docs.python.org/3/library/asyncio-subprocess.html) -- Subprocess spawning
- [Zoom Apps SDK reference](https://appssdk.zoom.us/classes/ZoomSdk.ZoomSdk.html) -- Meeting context API
- PROJECT.md -- Infrastructure details, fleet agent architecture
