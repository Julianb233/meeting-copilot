# Meeting Copilot

AI-powered Zoom companion panel that **executes work during meetings**.

Not just note-taking — the copilot detects what Julian and clients need, spawns fleet agents to build it, and shows live progress in a Zoom sidebar.

## Architecture

- **Zoom Side Panel** — React app inside Zoom showing live tasks, completions, quick actions
- **Copilot Engine** — Intent detection + task orchestration running on VPS
- **Multi-model fallback** — Gemini → OpenAI → Claude → Keywords
- **Fleet Integration** — Spawns agent1-4 to execute work in parallel during the call

## Stack

- Next.js 15 + React 19 (panel UI)
- Zoom Apps SDK (side panel integration)
- WebSocket (real-time bidirectional)
- Python (copilot engine on VPS)
- Fireflies API (live transcription)

## Status

Phase 0 complete — Meeting Watcher v2 running with:
- Auto-meeting detection (Zoom + Calendar + Fireflies)
- Live transcript classification
- Multi-model fallback (Gemini active)
- iMessage sidekick notifications
- Obsidian meeting notes
- Linear issue creation

Built by AI Acrobatics fleet agents.
