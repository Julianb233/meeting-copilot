# Domain Pitfalls

**Domain:** AI Meeting Companion Panel (Zoom Sidebar)
**Researched:** 2026-03-20

---

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Zoom iframe CSP Blocks WebSocket Connection

**What goes wrong:** Panel deploys to Vercel, loads in Zoom, but WebSocket connection to VPS fails silently. No error in panel, just "disconnected" forever.

**Why it happens:** Zoom's embedded browser enforces strict Content-Security-Policy. If your `connect-src` directive doesn't include `wss://your-vps-domain`, the WebSocket handshake is blocked. Vercel's default CSP headers don't include your custom WebSocket domain.

**Consequences:** Panel is completely non-functional. Zero real-time communication.

**Prevention:**
- Configure `vercel.json` headers with explicit CSP allowing `wss://copilot-api.yourdomain.com`
- Add `frame-ancestors *.zoom.us` to allow Zoom to embed the iframe
- Test CSP in a regular browser first (Chrome DevTools > Network > WS), then test inside Zoom
- Required CSP directives for Zoom: `connect-src wss://your-domain *.zoom.us; script-src 'self' *.zoom.us 'unsafe-eval'; worker-src 'blob:'`

**Detection:** WebSocket never connects. Panel shows "Disconnected" permanently. Browser console shows CSP violation error (but you can only see this in Zoom's dev tools, which are harder to access).

### Pitfall 2: Zoom App OAuth Complexity Underestimated

**What goes wrong:** You build the panel and engine, then discover Zoom app registration requires OAuth 2.0 server-side flow, redirect URIs, token storage, and scope approval — even for a private/internal app.

**Why it happens:** Zoom Apps SDK requires a registered app on marketplace.zoom.us. Even private apps need OAuth for `getMeetingContext()` to work. You can't just embed a URL in Zoom — the app must be registered and authorized.

**Consequences:** Multi-day delay while setting up Zoom OAuth flow, token endpoints, and app configuration.

**Prevention:**
- Register the Zoom app FIRST, before building anything else
- Set up OAuth token endpoint on the VPS (FastAPI route) early
- Use Server-to-Server OAuth for backend API calls (simpler, no user consent flow)
- Use standard OAuth 2.0 for the panel's Zoom App auth (user-facing)
- Read Zoom's app submission guide even for private apps — there are technical requirements

**Detection:** `getMeetingContext()` returns undefined or throws auth error when panel loads in Zoom.

### Pitfall 3: Fireflies Transcript Deduplication Across Bot Instances

**What goes wrong:** Fireflies bot joins the meeting 2-3 times (known issue from Phase 0). Each instance generates a separate transcript. Your intent classifier processes the same utterance 2-3 times, creating duplicate tasks.

**Why it happens:** Fireflies sometimes spawns multiple bot instances per meeting. The `addToLiveMeeting` API doesn't check if a bot is already in the meeting. Auto-join and manual join can overlap.

**Consequences:** Duplicate Linear issues, duplicate emails, duplicate agent spawns. User sees 3x the actual work items.

**Prevention:**
- Hash each transcript sentence (speaker + text + approximate timestamp)
- Maintain a per-meeting dedup set of sentence hashes
- Use fuzzy matching (not just exact hash) because different bot instances may transcribe slightly differently
- Consider using transcript ID from Fireflies to identify unique transcripts vs duplicate bot instances
- Existing meeting-watcher.py has basic dedup — port and improve this logic

**Detection:** Same action item appears multiple times in the task feed within a few seconds of each other.

---

## Moderate Pitfalls

Mistakes that cause delays or technical debt.

### Pitfall 4: WebSocket Reconnection Not Handling Zoom iframe Suspend/Resume

**What goes wrong:** User closes the Zoom panel sidebar, then reopens it 10 minutes later. WebSocket is dead. Panel shows stale state from 10 minutes ago. No reconnection happens.

**Why it happens:** Zoom may fully unload the iframe when the panel is hidden. When reopened, it's a fresh page load but the React state from the previous session is gone. If your WebSocket hook doesn't auto-reconnect with state sync, the panel is stuck.

**Prevention:**
- `react-use-websocket` has built-in reconnection (`shouldReconnect: () => true`)
- Engine must send full state on every new WebSocket connection (Pattern 2 from ARCHITECTURE.md)
- Test by closing/reopening the panel repeatedly during a meeting
- Do NOT rely on localStorage or sessionStorage for state persistence in Zoom iframe

**Detection:** Panel shows "Connected" but task feed is empty after reopening the sidebar.

### Pitfall 5: LiteLLM Fallback Chain Silently Falling to Keyword Matcher

**What goes wrong:** Gemini rate limits (15 RPM free tier), OpenAI key is rate-limited, Claude has no credits. Every classification silently falls through to the keyword matcher, which has much lower accuracy. User doesn't know classification quality has degraded.

**Why it happens:** LiteLLM handles fallback automatically, which is great — but there's no visibility into WHICH model actually handled the request. You need to instrument this.

**Prevention:**
- Log which model in the fallback chain actually served each request
- Broadcast model used as part of the intent classification message to the panel
- Add a subtle indicator in the panel showing classification confidence/model
- Monitor Gemini free tier usage (15 RPM, 1M TPD)
- Consider batching transcript chunks to reduce API calls (classify 3-4 sentences at once, not each individually)

**Detection:** Classification accuracy drops. Action items become vague or miscategorized. Check logs for which model is serving requests.

### Pitfall 6: Google OAuth Token Expiry During Meeting

**What goes wrong:** Google OAuth access token expires (1 hour lifetime) mid-meeting. Context engine can't refresh contacts, calendar, or send emails. No error surfaced to user.

**Why it happens:** Google access tokens expire after 3600 seconds. If you don't implement token refresh, all Google API calls fail silently after the first hour.

**Prevention:**
- Use `google-auth-oauthlib` with a refresh token stored securely
- Implement automatic token refresh in the HTTP client wrapper
- `google-api-python-client`'s `build()` with `Credentials` handles refresh automatically IF you provide a refresh token
- Store refresh tokens in `.env` or a secure file on the VPS
- Use a service account for Calendar/Contacts read access (simpler, no expiry)

**Detection:** Google API calls start returning 401 after ~1 hour of meeting time.

### Pitfall 7: Agent Subprocess Zombies

**What goes wrong:** Fleet agent subprocess is spawned but never completes (hangs on a long Claude Code prompt). It holds a slot in the agent pool forever. New tasks can't be dispatched.

**Why it happens:** Claude Code can hang on complex prompts, network issues, or API rate limits. `asyncio.create_subprocess_exec()` doesn't have a built-in timeout.

**Prevention:**
- Set a timeout on every subprocess (e.g., 5 minutes max per agent task)
- Use `asyncio.wait_for(proc.communicate(), timeout=300)`
- Implement a watchdog that checks for zombie processes every 60 seconds
- Kill and report failure for any subprocess that exceeds timeout
- Report agent status back to panel: "Agent 2: timed out on task X"

**Detection:** Agent status shows "working" for 10+ minutes on a task that should take 1-2 minutes.

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable.

### Pitfall 8: Zoom Panel Width Assumption

**What goes wrong:** UI looks fine in browser dev tools at 400px width. Inside actual Zoom, it's narrower (sometimes 280px) and elements overflow or get cut off.

**Prevention:**
- Design for 280px minimum width
- Test inside actual Zoom client, not just browser simulation
- Use `min-width: 280px` and test overflow behavior
- Avoid fixed widths; use percentages and flex/grid

### Pitfall 9: Fireflies API Rate Limit on addToLiveMeeting

**What goes wrong:** You call `addToLiveMeeting` too many times (e.g., on every meeting detection signal) and hit the 3-per-20-minutes rate limit.

**Prevention:**
- Track whether bot has already been added to current meeting
- Only call `addToLiveMeeting` once per meeting, with a guard
- If Fireflies auto-joins via settings, don't call the API at all

### Pitfall 10: Meeting Detection False Positives

**What goes wrong:** Engine detects a "meeting" from a calendar event that's actually a reminder or all-day event. Fires up the full pipeline for nothing.

**Prevention:**
- Filter calendar events: must have videoconference link AND attendees AND be 15-120 minutes
- Don't rely solely on Zoom process detection (could be viewing a recording)
- Require at least 2 of 3 signals: Calendar event + Zoom process + Fireflies detection

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Zoom App Registration | OAuth complexity, redirect URI setup, scope requirements | Register app first, before building panel. Read full docs. |
| WebSocket Server | CSP blocks connection from Zoom iframe | Configure nginx + Vercel CSP headers. Test in Zoom early. |
| Fireflies Integration | Duplicate bot instances, transcript dedup | Port existing dedup logic from meeting-watcher.py, add fuzzy matching |
| Intent Classification | Rate limits on free tiers cause silent degradation | Instrument which model serves each request, batch transcript chunks |
| Agent Spawning | Zombie subprocesses, no timeout, pool exhaustion | Mandatory timeouts, watchdog process, status reporting |
| Google APIs | Token expiry mid-meeting | Use service account OR implement refresh token flow |
| Panel UI | Width narrower than expected in Zoom | Design for 280px min, test in real Zoom client |
| Post-meeting Email | Sending email to wrong people, wrong tone for client vs internal | Always show draft before sending. Detect internal vs client meeting type. |

---

## Sources

- [Zoom CSP requirements](https://devforum.zoom.us/t/what-is-an-appropiate-content-security-policy-csp-for-embedding-an-application-on-the-zoom-client/73158) -- CSP directives needed
- [Fireflies addToLiveMeeting](https://docs.fireflies.ai/graphql-api/mutation/add-to-live) -- Rate limit: 3/20min
- [LiteLLM docs](https://docs.litellm.ai/) -- Fallback configuration
- PROJECT.md -- Known issues from Phase 0
- [Google OAuth token refresh](https://developers.google.com/identity/protocols/oauth2) -- Token lifecycle
