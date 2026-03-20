# Roadmap: Meeting Copilot

## Overview

Build a Zoom companion panel that executes work during meetings. Six phases: scaffold infrastructure → build context engine → add intent detection & task orchestration → create Zoom panel UI → layer in meeting intelligence → integrate and polish.

## Phases

- [ ] **Phase 1: Scaffold & Infrastructure** - Next.js project, Python engine, WebSocket, REST API
- [ ] **Phase 2: Context Engine** - Load full attendee context from all data sources at meeting start
- [ ] **Phase 3: Intent Detection & Task Orchestration** - Understand intents, route to projects, spawn agents
- [ ] **Phase 4: Zoom Companion Panel UI** - React sidebar with live tasks, status, quick actions
- [ ] **Phase 5: Meeting Intelligence** - Internal/client detection, prior context, follow-up emails
- [ ] **Phase 6: Integration & Polish** - E2E testing, deployment, watcher v2 bridge

## Phase Details

### Phase 1: Scaffold & Infrastructure
**Goal**: Project scaffolding, WebSocket server, REST API, deployment config
**Depends on**: Nothing (first phase)
**Requirements**: COM-01, COM-02, COM-03
**Success Criteria** (what must be TRUE):
  1. Next.js 15 app builds and runs locally
  2. Python engine starts with WebSocket server on port 8900
  3. REST API responds on port 8901 with health check
  4. WebSocket messages flow bidirectionally between panel and engine
  5. Nginx config proxies WebSocket with TLS
**Plans**: 4 plans

Plans:
- [ ] 01-01: Scaffold Next.js 15 + React 19 app with Zoom Apps SDK boilerplate
- [ ] 01-02: Scaffold Python copilot engine with WebSocket server (port 8900) and REST API (port 8901)
- [ ] 01-03: Nginx reverse proxy config for WebSocket TLS on VPS
- [ ] 01-04: Basic project structure — shared types, env config, deployment scripts

### Phase 2: Context Engine
**Goal**: On meeting start, load full attendee context from all data sources
**Depends on**: Phase 1
**Requirements**: CTX-01, CTX-02, CTX-03, CTX-04, CTX-05, CTX-06, RTE-03
**Success Criteria** (what must be TRUE):
  1. Given attendee emails from Calendar, Google Contacts returns identity info
  2. Fireflies API returns last 3 transcripts for matched attendee
  3. Linear projects and open issues load for attendee's organization
  4. Obsidian client profile loads if one exists
  5. Unified context object assembles all sources for the classifier prompt
**Plans**: 5 plans

Plans:
- [ ] 02-01: Attendee identity resolution — Google Contacts API lookup by email
- [ ] 02-02: Meeting history loader — Fireflies API for last 3 transcripts
- [ ] 02-03: Linear project mapper — map attendee to projects and open issues
- [ ] 02-04: Client profile loader — read from Obsidian vault
- [ ] 02-05: Context assembler — merge all sources into unified context object

### Phase 3: Intent Detection & Task Orchestration
**Goal**: Upgrade classification to intent understanding, route to projects, spawn fleet agents
**Depends on**: Phase 2
**Requirements**: INT-02, INT-03, INT-04, RTE-01, RTE-02, ORC-01, ORC-02
**Success Criteria** (what must be TRUE):
  1. Intent detector extracts structured intents (action type, target, urgency, project) from transcript
  2. Classification uses Claude → Gemini → OpenAI → Keywords fallback chain
  3. Detected intents route to correct Linear project based on meeting context
  4. Fleet agents spawn via god-mcp when execution-ready intents are detected
  5. Agent status tracked and reported back via WebSocket
**Plans**: 4 plans

Plans:
- [ ] 03-01: Intent detector — structured intent extraction from transcript
- [ ] 03-02: Project-aware routing — route intents to correct Linear project
- [ ] 03-03: Task orchestrator — spawn fleet agents, track execution status
- [ ] 03-04: Linear issue creation with project routing

### Phase 4: Zoom Companion Panel UI
**Goal**: React sidebar app inside Zoom showing live tasks, agent status, quick actions
**Depends on**: Phase 1, Phase 3 (for WebSocket events)
**Requirements**: ZOM-01, ZOM-02, ZOM-03, PNL-01, PNL-02, PNL-03, PNL-04, PNL-05, ORC-03
**Success Criteria** (what must be TRUE):
  1. Zoom app registered as private Meeting Side Panel
  2. OAuth flow authenticates Julian's Zoom account
  3. Panel renders inside Zoom sidebar showing live task feed
  4. Status badges update in real-time via WebSocket
  5. Quick action buttons trigger fleet agents with meeting context
**Plans**: 4 plans

Plans:
- [ ] 04-01: Zoom App registration — private app, OAuth flow
- [ ] 04-02: Panel UI — task feed, status badges, completion indicators
- [ ] 04-03: WebSocket client — connect panel to engine for real-time events
- [ ] 04-04: Quick action buttons — Delegate Task, Create Proposal, Research This, Draft Email, Check Domain

### Phase 5: Meeting Intelligence
**Goal**: Internal/client detection, prior meeting context, follow-up emails
**Depends on**: Phase 2, Phase 3
**Requirements**: CTX-07, INT-01, PST-01, PST-02
**Success Criteria** (what must be TRUE):
  1. Meetings classified as internal or client based on attendee domains
  2. "Last time you discussed..." context surfaces at meeting start
  3. Post-meeting follow-up email auto-drafted with action items and decisions
  4. Post-meeting summary generation upgraded with project-aware context
**Plans**: 3 plans

Plans:
- [ ] 05-01: Internal vs client meeting detection
- [ ] 05-02: Prior meeting context surfacing
- [ ] 05-03: Post-meeting follow-up email via gws CLI

### Phase 6: Integration & Polish
**Goal**: Bridge watcher v2, deploy, end-to-end test full flow
**Depends on**: All previous phases
**Requirements**: (Integration — no new requirements, validates all prior)
**Success Criteria** (what must be TRUE):
  1. Meeting-watcher v2 bridges to copilot engine seamlessly
  2. Panel deployed on Vercel, engine deployed on VPS
  3. Full flow works: meeting detected → context loaded → intents extracted → agents spawned → panel shows progress
**Plans**: 3 plans

Plans:
- [ ] 06-01: Bridge meeting-watcher v2 to copilot engine
- [ ] 06-02: Vercel + VPS deployment
- [ ] 06-03: End-to-end testing — full meeting flow simulation

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scaffold & Infrastructure | 0/4 | Not started | - |
| 2. Context Engine | 0/5 | Not started | - |
| 3. Intent & Orchestration | 0/4 | Not started | - |
| 4. Zoom Panel UI | 0/4 | Not started | - |
| 5. Meeting Intelligence | 0/3 | Not started | - |
| 6. Integration & Polish | 0/3 | Not started | - |
