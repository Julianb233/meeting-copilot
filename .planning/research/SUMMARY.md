# Research Summary

**Project:** Meeting Copilot
**Researched:** 2026-03-20
**Sources:** 5 parallel research agents (Stack, Features, Architecture, Pitfalls, Transcript Sources)
**Overall Confidence:** MEDIUM-HIGH

---

## Executive Summary

Meeting Copilot is an AI-powered Zoom companion panel that **executes work during meetings**. Research confirms no competitor does real-time execution. The market stops at "extract action items."

### Critical Discoveries

1. **Fireflies rate limit (~50 req/day) makes polling unsustainable.** Use Zoom RTMS SDK ($0, native WebSocket) + Chrome Extension + Deepgram for Google Meet ($200 free credit).
2. **Vite over Next.js** — Zoom embeds as iframe, SSR is pointless. Half the bundle size.
3. **LiteLLM for multi-model fallback** — One `completion()` call handles Gemini/OpenAI/Claude routing.
4. **Zoom CSP is the silent killer** — Missing `connect-src wss://` silently blocks WebSocket.
5. **OAuth required even for private apps** — Must start registration immediately.
6. **Context window overflow at ~60 min** — Sliding window + running summary required.

## Recommended Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Panel UI | Vite + React 19 + Zustand + Tailwind | $0 |
| Zoom SDK | @zoom/appssdk 0.16.36 | $0 |
| Engine | FastAPI (Python) | $0 |
| AI Classification | LiteLLM + Gemini/OpenAI/Claude | $0 |
| Transcript (Zoom) | Zoom RTMS SDK | $0 |
| Transcript (Meet) | Chrome Extension + Deepgram | $0 for ~5 months |
| Transcript (fallback) | Self-hosted Whisper | $0 |
| Hosting (panel) | Vercel static | $0 |
| Hosting (engine) | VPS nginx proxy | $0 |
| **Total** | | **$0** |

## Transcript Source Strategy

| Platform | Source | Latency | Speaker ID |
|----------|--------|---------|------------|
| Zoom | RTMS SDK (WebSocket push) | ~1-2s | Yes |
| Google Meet | Chrome Extension + Deepgram | ~1s | Yes |
| Fallback | Self-hosted Whisper on VPS | ~3-5s | Basic |
| Post-meeting | Fireflies (summaries only) | N/A | Yes |

## Critical Pitfalls

| Pitfall | Severity | Prevention | Phase |
|---------|----------|------------|-------|
| CSP blocks WebSocket | CRITICAL | vercel.json CSP headers | 1 |
| OAuth complexity | CRITICAL | Start registration day 1 | 1 |
| Fireflies rate limits | CRITICAL | RTMS + Deepgram instead | 2 |
| Context overflow (60min) | HIGH | Sliding window + summary | 3 |
| Agent resource exhaustion | HIGH | Concurrency cap at 2 | 5 |

## Implications for Roadmap

### Phase 1: Foundation + Zoom App Registration
FastAPI engine, WebSocket server, TranscriptSource abstraction, RTMS integration, Zoom OAuth, CSP config

### Phase 2: Panel UI + WebSocket Bridge
Vite React panel, WebSocket connection, live task feed, connection status, meeting context display

### Phase 3: Intelligence Layer
LiteLLM multi-model fallback, intent detection upgrade, sliding window context, speaker ID

### Phase 4: Context Engine + Project Routing
Attendee identification, project association, prior meeting history, Linear auto-creation

### Phase 5: Agent Orchestration + Quick Actions
Fleet agent spawning (cap=2), task queue, quick action buttons, real-time progress

### Phase 6: Polish + Google Meet + SaaS Prep
Chrome Extension for Meet, Deepgram, post-meeting emails, SaaS multi-tenancy foundation

**Phase ordering:** OAuth has lead time (Phase 1) → Panel needs to exist to show results (Phase 2) → Classification before routing (Phase 3→4) → Context before execution (Phase 4→5) → Meet is secondary (Phase 6)

---
*Ready for: /gsd:define-requirements or /gsd:create-roadmap*
