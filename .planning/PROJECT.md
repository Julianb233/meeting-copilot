# Meeting Copilot

## What This Is

A Zoom companion panel app that acts as an AI agent in the room during meetings. It listens to the live transcript, understands who Julian is meeting with, loads all relevant project context, and **executes work in real-time** — creating Linear issues, spawning fleet agents to build things, drafting proposals and emails — all while the meeting is still happening. Shows live progress in a Zoom sidebar.

## Core Value

The copilot must **know who Julian is talking to, what projects are relevant, and route every action to the right place** — so Julian never has to manually create tasks, write follow-ups, or context-switch after a meeting. The meeting IS the work.

## Requirements

### Validated

- Meeting Watcher v2 running — auto-detects meetings via Zoom process, Calendar, Fireflies API
- Live transcript polling from Fireflies (30s intervals)
- Multi-model classification fallback chain (Gemini → OpenAI → Claude → Keywords)
- Deduplication across multiple Fireflies bot instances
- Auto-add Fireflies bot to meetings (via `addToLiveMeeting` API)
- Obsidian meeting notes auto-generated
- iMessage sidekick notifications during meetings
- Post-meeting summary generation
- Google Calendar integration with attendee extraction

### Active

- [ ] **Context Engine** — On meeting start, load attendee identity (Google Contacts), meeting history (last 3 Fireflies transcripts), associated Linear projects, open issues, client profile from Obsidian, and recent git activity
- [ ] **Project-Aware Routing** — Action items route to the correct Linear project based on meeting context. "Fix the login page" during a Better Together meeting → Better Together project in Linear, not a generic inbox
- [ ] **Internal vs Client Detection** — Recognize whether this is an internal team meeting (Hitesh, other devs) or a client meeting. Internal = can reference all projects, multi-project switching. Client = scoped to their project, professional tone
- [ ] **Multi-Project Switching** — During internal meetings, detect when conversation switches projects ("Now about the copilot...") and re-route subsequent actions to the correct project
- [ ] **WebSocket Server** — Real-time bidirectional event stream between VPS engine and Zoom panel (port 8900)
- [ ] **REST API** — Snapshot endpoint for current meeting state, context, active tasks (port 8901)
- [ ] **Intent Detector** — Upgrade from sentence classification to intent understanding. "We need a landing page with booking" → spawn agent to scaffold it, not just log it as an action item
- [ ] **Task Orchestrator** — Spawn fleet agents (agent1-4) to execute work in parallel during the meeting. Track status, report completions back to panel
- [ ] **Zoom App Registration** — Register as Meeting Side Panel on Zoom Marketplace. Internal/private app (no marketplace review). OAuth for Zoom auth
- [ ] **Companion Panel UI** — React app rendered inside Zoom sidebar showing: live task feed with status badges, completed items, decisions & notes log, agent status, quick action buttons
- [ ] **Quick Action Buttons** — Panel buttons: Delegate Task, Create Proposal, Research This, Draft Email, Check Domain. Each triggers the corresponding fleet agent or skill
- [ ] **Prior Meeting Context** — When meeting starts, surface "Last time you met with Hitesh, you discussed: [topics]. Open items: [list]"
- [ ] **Post-Meeting Follow-Up Email** — Auto-draft and send follow-up email to attendees with action items, decisions, and next steps
- [ ] **Linear Project Auto-Creation** — For new client meetings where no project exists, auto-create a Linear project with the client name and populate initial issues from the meeting
- [ ] **Claude-Powered Classification** — When Anthropic credits are available, use Claude Haiku for higher-accuracy classification. Fallback chain: Claude → Gemini → OpenAI → Keywords

### Out of Scope

- Google Meet companion panel — Zoom only for v1 (Meet support planned for v2)
- Video/screen analysis — transcript only, no visual AI
- Mobile Zoom app panel — desktop Zoom only
- Public marketplace listing — internal/private app only
- Voice synthesis/response — agent doesn't speak in the meeting

## Context

### What Exists (Phase 0 — Running)

Meeting Watcher v2 at `/opt/agency-workspace/scripts/meeting-watcher.py`:
- Auto-detects meetings via 3 signals (Zoom process on MacBook Pro, Google Calendar events, Fireflies active meetings)
- Polls Fireflies live transcript every 30 seconds
- Multi-model fallback: Gemini (active, free) → OpenAI (rate limited) → Claude (no credits) → keyword matching
- Creates Obsidian meeting notes at `/opt/agency-workspace/obsidian-vault/meetings/`
- Sends iMessage sidekick digests via `mac send`
- Deduplicates across multiple bot instances
- Post-meeting summary triggers on meeting end

### Known Issues from Phase 0

- Fireflies bot sometimes joins multiple times (2-3 instances) creating duplicate transcript entries
- Anthropic API key has zero credits (Gemini handles all classification currently)
- OpenAI rate limited on current key
- Deduplication works by text hash but some near-duplicates still slip through (slightly different transcriptions)
- Linear issue creation needs team ID + project routing (currently hardcoded to one team)
- No attendee context — treats every meeting the same regardless of who's in it

### Infrastructure

- **VPS**: Hetzner, 48-core, 252GB RAM, Ubuntu — runs all agents
- **Mac Mini**: macOS 26 (Tahoe) via Tailscale (100.108.83.124) — iMessage, Chrome automation
- **MacBook Pro**: Julian's daily driver via Tailscale (100.89.189.37) — where Zoom runs
- **Fleet Agents**: agent1-4 + dev, each with own Claude Code instance
- **Existing APIs**: Fireflies, Linear, Gmail (gws), Google Calendar, Contacts, Vercel, GitHub, 1Password

### Client & Contact Data Sources

- Google Contacts (4,886 contacts via People API)
- Obsidian vault client profiles at `/opt/agency-workspace/client-profiles/`
- Linear projects and issues
- Fireflies meeting history
- Gmail correspondence

## Constraints

- **Zoom Apps SDK**: Panel runs as an iframe inside Zoom — must be a web app hosted on HTTPS
- **Hosting**: Panel UI on Vercel (free tier), engine on VPS
- **WebSocket**: Must proxy through nginx on VPS with TLS
- **Fireflies API**: Live transcript polling only (no push/webhook), 30s minimum interval
- **Zoom Private App**: No marketplace review needed, but must register on marketplace.zoom.us with developer account
- **Cost**: $0 budget — all free tiers (Zoom Marketplace, Vercel, Gemini API, VPS already paid)
- **Chrome Profile**: Default to Profile 5 (aiacrobatics.com) on MacBook Pro when opening URLs
- **iMessage**: Route to julianb233@gmail.com (not phone number) for delivery from Mac Mini

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Gemini as primary classifier | Free, fast, accurate enough. Claude/OpenAI as fallbacks | -- Pending |
| Zoom-only for v1 | Julian primarily uses Zoom. Google Meet support v2 | -- Pending |
| Private/internal Zoom app | No marketplace review, instant deploy, only Julian uses it | -- Pending |
| React + Next.js for panel | Same stack as other projects, Vercel hosting, fast iteration | -- Pending |
| Python for engine | Meeting watcher already Python, Fireflies/Linear API clients exist | -- Pending |
| WebSocket for real-time | Bidirectional, low latency, panel ↔ engine communication | -- Pending |
| Context loading at meeting start | Pull all relevant data once, inject into classifier prompt | -- Pending |
| Project detection by attendee email | Linear API search + Google Contacts cross-reference | -- Pending |
| Fleet agent spawning for execution | Leverage existing agent1-4 infrastructure for parallel work | -- Pending |

---
*Last updated: 2026-03-20 after initialization*
