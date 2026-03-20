---
phase: 1-project-scaffold-infrastructure
plan: 04
type: execute
wave: 2
depends_on: ["1-01", "1-02"]
files_modified:
  - package.json
  - shared/protocol.ts
  - shared/README.md
  - panel/.env
  - engine/.env
autonomous: true

must_haves:
  truths:
    - "Root package.json has scripts to start both panel and engine together"
    - "Shared protocol file documents the WebSocket message contract between panel and engine"
    - "Local .env files exist so both panel and engine start without manual config"
    - "Panel and engine can start simultaneously from a single command"
  artifacts:
    - path: "package.json"
      provides: "Root workspace config with convenience scripts"
      contains: "dev"
    - path: "shared/protocol.ts"
      provides: "Canonical WebSocket message type definitions shared between panel and engine"
      contains: "ServerEventType"
  key_links:
    - from: "shared/protocol.ts"
      to: "panel/src/types/messages.ts"
      via: "Type contract that panel types must match"
      pattern: "ServerEventType"
    - from: "shared/protocol.ts"
      to: "engine/src/models/events.py"
      via: "Type contract that engine Pydantic models must match"
      pattern: "ClientEventType"
---

<objective>
Create root-level project configuration: workspace package.json with convenience scripts, shared WebSocket protocol type definitions as the canonical contract, and local .env files for development.

Purpose: Enable single-command development startup and establish the shared type contract between panel (TypeScript) and engine (Python) to prevent WebSocket message type drift.

Output: Root package.json, shared protocol definitions, local dev environment files.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/research/STACK.md
@.planning/research/ARCHITECTURE.md
@.planning/phases/1-project-scaffold-infrastructure/1-01-SUMMARY.md
@.planning/phases/1-project-scaffold-infrastructure/1-02-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Root package.json and shared protocol definitions</name>
  <files>
    package.json
    shared/protocol.ts
  </files>
  <action>
    From the project root `/opt/agency-workspace/meeting-copilot/`:

    1. Create root `package.json` — this is NOT an npm workspace. It is a convenience wrapper with scripts to run both panel and engine:
       ```json
       {
         "name": "meeting-copilot",
         "version": "0.1.0",
         "private": true,
         "description": "AI meeting copilot - Zoom companion panel + Python engine",
         "scripts": {
           "dev": "concurrently --names panel,engine --prefix-colors blue,green \"npm run dev:panel\" \"npm run dev:engine\"",
           "dev:panel": "cd panel && npm run dev",
           "dev:engine": "cd engine && source .venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8901 --reload",
           "build:panel": "cd panel && npm run build",
           "test:panel": "cd panel && npx vitest run",
           "test:engine": "cd engine && source .venv/bin/activate && python -m pytest tests/ -v",
           "test": "npm run test:panel && npm run test:engine",
           "lint:panel": "cd panel && npx biome check src/",
           "lint:engine": "cd engine && source .venv/bin/activate && ruff check src/",
           "lint": "npm run lint:panel && npm run lint:engine"
         },
         "devDependencies": {
           "concurrently": "^9.0.0"
         }
       }
       ```

    2. Install the root dev dependency:
       ```bash
       npm install
       ```

    3. Create `shared/protocol.ts` — the canonical WebSocket message contract. This file is the single source of truth for the message types. Both `panel/src/types/messages.ts` and `engine/src/models/events.py` must match these definitions:
       ```typescript
       /**
        * Meeting Copilot — WebSocket Message Protocol
        *
        * CANONICAL SOURCE OF TRUTH for message types between panel and engine.
        *
        * Panel (TypeScript): panel/src/types/messages.ts must match these types
        * Engine (Python): engine/src/models/events.py Pydantic models must match these types
        *
        * When adding new message types:
        * 1. Add here first
        * 2. Update panel/src/types/messages.ts
        * 3. Update engine/src/models/events.py
        * 4. Update message handlers in both panel and engine
        */

       // ============================================================
       // Engine -> Panel (Server Events)
       // ============================================================

       export type ServerEventType =
         | "connection_ack"       // Sent on WebSocket connect, includes full meeting state
         | "meeting_started"      // Meeting detected, context loading begins
         | "context_loaded"       // Attendee context fully loaded
         | "transcript_chunk"     // New transcript text from Fireflies
         | "intent_classified"    // Transcript classified into actionable intent
         | "task_dispatched"      // Task created and sent to agent
         | "task_completed"       // Agent finished task successfully
         | "task_failed"          // Agent task failed
         | "agent_status"         // Agent status update (idle/busy)
         | "decision_logged"      // Decision captured from transcript
         | "meeting_ended"        // Meeting ended, summary available
         | "pong"                 // Heartbeat response

       export interface ServerEvent {
         type: ServerEventType
         payload: Record<string, unknown>
         ts: string              // ISO 8601 timestamp
         meeting_id: string
       }

       // ============================================================
       // Panel -> Engine (Client Events / Commands)
       // ============================================================

       export type ClientEventType =
         | "action.delegate"      // Delegate task to fleet agent
         | "action.research"      // Research a topic
         | "action.email"         // Draft follow-up email
         | "action.proposal"      // Create proposal
         | "action.domain"        // Check domain availability
         | "action.custom"        // Custom action with freeform prompt
         | "ping"                 // Heartbeat

       export interface ClientEvent {
         type: ClientEventType
         payload: Record<string, unknown>
         ts: string              // ISO 8601 timestamp
       }

       // ============================================================
       // Shared Domain Types
       // ============================================================

       export type MeetingType = "client" | "internal" | "prospect"
       export type TaskStatus = "pending" | "running" | "completed" | "failed"
       export type AgentId = "agent1" | "agent2" | "agent3" | "agent4"
       export type AgentStatusValue = "idle" | "busy"

       export interface Attendee {
         name: string
         email: string
         company?: string
         role?: string
       }

       export interface MeetingTask {
         id: string
         title: string
         status: TaskStatus
         project?: string
         agent_id?: AgentId
         created_at: string      // ISO 8601
         completed_at?: string   // ISO 8601
         result?: string
       }

       export interface Decision {
         id: string
         text: string
         timestamp: string       // ISO 8601
       }

       export interface AgentInfo {
         id: AgentId
         status: AgentStatusValue
         current_task?: string
       }

       export interface MeetingState {
         meeting_id: string | null
         title: string
         meeting_type: MeetingType | null
         attendees: Attendee[]
         tasks: MeetingTask[]
         completed_tasks: MeetingTask[]
         decisions: Decision[]
         agents: AgentInfo[]
         connected: boolean
         context_loaded: boolean
       }
       ```

       NOTE: This file uses snake_case for field names to match the Python Pydantic models directly. The panel's internal TypeScript types (panel/src/types/meeting.ts) may use camelCase, but the wire format (JSON over WebSocket) uses snake_case as defined here.
  </action>
  <verify>
    - `ls package.json shared/protocol.ts` both exist
    - `grep "concurrently" package.json` returns a match
    - `grep "dev:panel" package.json` returns a match
    - `grep "dev:engine" package.json` returns a match
    - `grep "ServerEventType" shared/protocol.ts` returns a match
    - `grep "ClientEventType" shared/protocol.ts` returns a match
    - `grep "MeetingState" shared/protocol.ts` returns a match
    - `ls node_modules/.package-lock.json 2>/dev/null || ls node_modules/ 2>/dev/null | head -1` confirms npm install ran
  </verify>
  <done>Root package.json enables `npm run dev` to start both panel and engine simultaneously. Shared protocol file defines the canonical WebSocket message contract.</done>
</task>

<task type="auto">
  <name>Task 2: Create local .env files for development and verify full startup</name>
  <files>
    panel/.env
    engine/.env
  </files>
  <action>
    1. Create `panel/.env` from the template in panel/.env.example (created by plan 1-03):
       ```bash
       VITE_WS_URL=ws://localhost:8901/ws
       VITE_API_URL=http://localhost:8901/api
       ```

    2. Create `engine/.env` from the template in engine/.env.example (created by plan 1-03):
       ```bash
       ENGINE_HOST=0.0.0.0
       ENGINE_PORT=8901
       DEBUG=true
       PANEL_ORIGIN=http://localhost:3000
       ```

    3. Verify that `.gitignore` (created by plan 1-03) excludes `.env` files:
       ```bash
       grep "\.env" .gitignore
       ```
       If .gitignore does not exist yet (plan 1-03 hasn't run), create a minimal one:
       ```
       .env
       .env.local
       .env.*.local
       node_modules/
       ```

    4. Verify the full development startup works:
       - Start the engine in background: `cd engine && source .venv/bin/activate && timeout 5 uvicorn src.main:app --host 0.0.0.0 --port 8901 2>&1 || true`
       - Confirm health check: `curl -s http://localhost:8901/api/health`
       - Start the panel in background: `cd panel && timeout 5 npm run dev 2>&1 || true`
       - Confirm both processes output startup messages

    5. Verify the root `npm run dev` script works (starts both):
       ```bash
       timeout 10 npm run dev 2>&1 || true
       ```
       Confirm output shows both panel and engine starting.
  </action>
  <verify>
    - `ls panel/.env engine/.env` both exist
    - `grep "VITE_WS_URL" panel/.env` returns a match
    - `grep "ENGINE_PORT" engine/.env` returns a match
    - `grep "\.env" .gitignore` confirms .env is gitignored
    - Engine starts: `cd engine && source .venv/bin/activate && timeout 3 uvicorn src.main:app --port 8901 2>&1 | grep -i "started\|running\|uvicorn"` shows startup
    - Root dev command runs: `timeout 5 npm run dev 2>&1 | head -20` shows both panel and engine output
  </verify>
  <done>Local .env files enable zero-config development startup. Both panel and engine start from `npm run dev` at the project root. Environment files are gitignored.</done>
</task>

</tasks>

<verification>
- `npm run dev` from project root starts both panel (port 3000) and engine (port 8901)
- `curl http://localhost:8901/api/health` returns {"status": "ok"}
- Panel loads at http://localhost:3000 and shows "Meeting Copilot"
- `shared/protocol.ts` defines all message types from ARCHITECTURE.md
- `.env` files are present but gitignored
</verification>

<success_criteria>
Project-level integration is complete with:
1. Root package.json with `npm run dev` starting both panel and engine
2. Shared protocol definitions as canonical WebSocket message contract
3. Local .env files for zero-config development
4. Both panel and engine can start simultaneously
5. Convenience scripts for test, lint, and build across both projects
</success_criteria>

<output>
After completion, create `.planning/phases/1-project-scaffold-infrastructure/1-04-SUMMARY.md`
</output>
