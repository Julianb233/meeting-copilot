# Research Summary: Meeting Copilot

**Domain:** AI-powered Zoom companion panel with real-time agent orchestration
**Researched:** 2026-03-20
**Overall confidence:** MEDIUM-HIGH

---

## Executive Summary

The Meeting Copilot is architecturally a two-part system: a thin React SPA panel embedded in Zoom's sidebar iframe, and a Python engine on the VPS that does all the heavy lifting. The panel and engine communicate via WebSocket over TLS. This is a well-understood architecture pattern — real-time dashboards backed by a WebSocket server — with the unique wrinkle of Zoom's iframe embedding requirements (CSP headers, OAuth app registration, constrained viewport).

The technology landscape is mature and well-suited to this project. FastAPI provides first-class WebSocket support for the engine. Vite + React is the standard SPA stack for 2025/2026 (NOT Next.js, because SSR is wasted inside an iframe). LiteLLM is the correct abstraction for the multi-model fallback chain, handling Gemini/OpenAI/Claude routing with 8ms P95 overhead. The Fireflies, Linear, and Google APIs all have stable, well-documented interfaces with generous free tiers.

The biggest risk is not the technology — it's the Zoom App registration and OAuth flow. Even private/internal Zoom apps require OAuth 2.0, redirect URIs, and proper scoping. This must be done first because it gates everything: without a registered app, the panel cannot load in Zoom, `getMeetingContext()` won't work, and there's no way to test the real integration. The second biggest risk is CSP configuration — Zoom's embedded browser enforces strict Content-Security-Policy, and a misconfigured `connect-src` will silently block the WebSocket connection.

The $0 budget constraint is achievable. Vercel free tier handles the static panel, the VPS is already paid for, Gemini free tier provides 15 RPM / 1M tokens per day (sufficient for one user's meetings), and all other APIs (Fireflies, Linear, Google) are within free tier limits.

## Key Findings

**Stack:** Vite + React 19 + TypeScript (panel), FastAPI + LiteLLM + asyncio (engine), WebSocket over nginx+TLS
**Architecture:** Thin client (panel) + smart server (engine). All business logic on VPS. Panel is display + commands only.
**Critical pitfall:** Zoom iframe CSP will silently block WebSocket if headers aren't configured correctly on both Vercel and nginx.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Foundation + Zoom App Registration** - Set up both codebases AND register the Zoom app. This must be first because Zoom OAuth gates all panel testing.
   - Addresses: Vite scaffold, FastAPI scaffold, Zoom app registration, OAuth endpoints
   - Avoids: Pitfall 2 (OAuth complexity underestimated)

2. **WebSocket Pipeline + Basic Panel** - Get real-time communication working end-to-end. Panel connects to engine, engine broadcasts mock events, panel displays them.
   - Addresses: WebSocket server, WebSocket client, nginx TLS proxy, CSP headers, connection status UI
   - Avoids: Pitfall 1 (CSP blocks WebSocket), Pitfall 4 (reconnection handling)

3. **Transcript + Classification Integration** - Connect Fireflies transcript polling to intent classification. Port existing meeting-watcher.py logic into the FastAPI engine.
   - Addresses: Fireflies polling, LiteLLM fallback chain, deduplication, live task feed
   - Avoids: Pitfall 3 (dedup), Pitfall 5 (silent fallback degradation)

4. **Context Engine + Project Routing** - Load attendee context on meeting start. Route intents to correct Linear projects.
   - Addresses: Google Contacts, Calendar, Linear project lookup, Obsidian profiles, internal vs client detection
   - Avoids: Pitfall 6 (Google token expiry)

5. **Agent Orchestration + Quick Actions** - Spawn fleet agents for task execution. Add quick action buttons to panel.
   - Addresses: Task orchestrator, subprocess spawning, agent status display, quick action buttons
   - Avoids: Pitfall 7 (zombie subprocesses)

6. **Polish + Post-Meeting** - Follow-up emails, meeting summaries, prior meeting context, edge case handling.
   - Addresses: Post-meeting summary, follow-up email, prior meeting context, Linear auto-creation

**Phase ordering rationale:**
- Phase 1 must be first: Zoom OAuth registration has a setup lead time and gates all in-Zoom testing
- Phase 2 must be second: WebSocket is the backbone — nothing works without it
- Phase 3 before Phase 4: Classification can work without context (using basic intent detection), but context without classification has nothing to route
- Phase 5 depends on Phase 3-4: Agents need classified intents + project context to execute meaningful work
- Phase 6 is polish: All core features exist, now add convenience and quality-of-life features

**Research flags for phases:**
- Phase 1: NEEDS RESEARCH — Zoom app registration process, OAuth flow specifics, required scopes
- Phase 2: Standard patterns, well-documented. Unlikely to need additional research.
- Phase 3: Partially researched. Fireflies API is documented. LiteLLM fallback config needs testing.
- Phase 4: NEEDS RESEARCH — Zoom `getMeetingContext()` may not return attendee emails directly. Cross-reference with Calendar API.
- Phase 5: Standard patterns (subprocess management). Fleet agent CLI interface needs documentation.
- Phase 6: Standard patterns. Gmail send API is well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified via official sources. Versions current. |
| Features | HIGH | Derived directly from PROJECT.md requirements + domain knowledge. |
| Architecture | HIGH | Standard real-time dashboard pattern. Well-understood. |
| Pitfalls | MEDIUM | CSP and OAuth pitfalls are well-documented. Agent subprocess management is based on general async patterns, not Zoom-specific experience. |
| Zoom SDK specifics | MEDIUM | SDK version verified (0.16.36). Side panel capabilities confirmed. But exact `getMeetingContext()` return shape and attendee data availability needs hands-on testing. |
| Cost/free tier | HIGH | All free tier limits verified against official docs. |

## Gaps to Address

- **Zoom App registration flow**: Exact steps, required scopes, OAuth redirect setup — needs hands-on research during Phase 1
- **`getMeetingContext()` attendee data**: Does it return emails, or just participant IDs? May need Calendar API cross-reference
- **react-use-websocket React 19 compatibility**: v4.13.0 was published before React 19 stable. Likely works but unverified.
- **Fleet agent CLI interface**: How exactly to spawn Claude Code agents via subprocess with task prompts. Document the `claude --print` interface.
- **Fireflies real-time latency**: 30s polling interval is the minimum documented. Actual latency of transcript availability after speech may be longer.

---

## Sources

See individual research files for detailed source lists:
- STACK.md — Technology recommendations with versions and rationale
- FEATURES.md — Feature landscape (table stakes, differentiators, anti-features)
- ARCHITECTURE.md — System structure, component boundaries, data flow
- PITFALLS.md — Domain pitfalls with prevention strategies
