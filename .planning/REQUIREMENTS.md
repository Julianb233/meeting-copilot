# Requirements: Meeting Copilot

## Version: v1.0

### Context Engine (CTX)

- **CTX-01**: On meeting start, load attendee identity from Google Contacts (People API) `v1`
- **CTX-02**: Load last 3 Fireflies transcripts for each attendee `v1`
- **CTX-03**: Load associated Linear projects for attendee's organization `v1`
- **CTX-04**: Load open Linear issues for matched projects `v1`
- **CTX-05**: Load client profile from Obsidian vault `v1`
- **CTX-06**: Load recent git activity for matched projects `v1`
- **CTX-07**: Surface prior meeting context — topics discussed, open items from last meeting `v1`

### Meeting Intelligence (INT)

- **INT-01**: Detect internal vs client meetings based on attendee email domains `v1`
- **INT-02**: Multi-project switching — detect conversation topic changes and re-route to correct project `v1`
- **INT-03**: Intent detection — understand actionable requests beyond sentence classification `v1`
- **INT-04**: Claude-powered classification with fallback chain (Claude → Gemini → OpenAI → Keywords) `v1`

### Project Routing (RTE)

- **RTE-01**: Route action items to correct Linear project based on meeting context `v1`
- **RTE-02**: Auto-create Linear project for new clients when no project exists `v1`
- **RTE-03**: Cross-reference attendee email with Google Contacts and Linear projects `v1`

### Real-Time Communication (COM)

- **COM-01**: WebSocket server for bidirectional engine ↔ panel communication (port 8900) `v1`
- **COM-02**: REST API for current meeting state snapshots (port 8901) `v1`
- **COM-03**: Real-time event streaming — tasks, completions, decisions, agent status `v1`

### Task Orchestration (ORC)

- **ORC-01**: Spawn fleet agents (agent1-4) to execute work during meetings `v1`
- **ORC-02**: Track agent task status and report completions back to panel `v1`
- **ORC-03**: Quick action buttons — Delegate Task, Create Proposal, Research This, Draft Email, Check Domain `v1`

### Zoom Integration (ZOM)

- **ZOM-01**: Register as Zoom Meeting Side Panel (private/internal app) `v1`
- **ZOM-02**: OAuth flow for Zoom authentication `v1`
- **ZOM-03**: Panel renders as iframe inside Zoom sidebar via HTTPS `v1`

### Panel UI (PNL)

- **PNL-01**: Live task feed with status badges (pending, running, completed, failed) `v1`
- **PNL-02**: Completed items section `v1`
- **PNL-03**: Decisions & notes log `v1`
- **PNL-04**: Agent status indicators `v1`
- **PNL-05**: Quick action buttons triggering fleet agents/skills `v1`

### Post-Meeting (PST)

- **PST-01**: Auto-draft follow-up email to attendees with action items, decisions, next steps `v1`
- **PST-02**: Post-meeting summary generation (upgrade existing) `v1`

## Out of Scope (v2+)

- Google Meet companion panel
- Video/screen analysis
- Mobile Zoom app panel
- Public marketplace listing
- Voice synthesis/response

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CTX-01 | Phase 2 | Pending |
| CTX-02 | Phase 2 | Pending |
| CTX-03 | Phase 2 | Pending |
| CTX-04 | Phase 2 | Pending |
| CTX-05 | Phase 2 | Pending |
| CTX-06 | Phase 2 | Pending |
| CTX-07 | Phase 5 | Pending |
| INT-01 | Phase 5 | Pending |
| INT-02 | Phase 3 | Pending |
| INT-03 | Phase 3 | Pending |
| INT-04 | Phase 3 | Pending |
| RTE-01 | Phase 3 | Pending |
| RTE-02 | Phase 3 | Pending |
| RTE-03 | Phase 2 | Pending |
| COM-01 | Phase 1 | Pending |
| COM-02 | Phase 1 | Pending |
| COM-03 | Phase 1 | Pending |
| ORC-01 | Phase 3 | Pending |
| ORC-02 | Phase 3 | Pending |
| ORC-03 | Phase 4 | Pending |
| ZOM-01 | Phase 4 | Pending |
| ZOM-02 | Phase 4 | Pending |
| ZOM-03 | Phase 4 | Pending |
| PNL-01 | Phase 4 | Pending |
| PNL-02 | Phase 4 | Pending |
| PNL-03 | Phase 4 | Pending |
| PNL-04 | Phase 4 | Pending |
| PNL-05 | Phase 4 | Pending |
| PST-01 | Phase 5 | Pending |
| PST-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 26 total (+ 4 implicit infra in Phase 1, Phase 6)
- Mapped to phases: 26
- Unmapped: 0
